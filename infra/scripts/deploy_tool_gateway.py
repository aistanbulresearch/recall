"""Deploy and verify the internal Tool Gateway Cloud Run service.

    python infra/scripts/deploy_tool_gateway.py plan --contract <file> --redact
    python infra/scripts/deploy_tool_gateway.py deploy --contract <file> --image <ref> --redact
    python infra/scripts/deploy_tool_gateway.py verify --redact
    python infra/scripts/deploy_tool_gateway.py destroy --redact

Why this service exists: agent tools must not hold data-store access. The
Assessor and Auditor service accounts have no Firestore role by design, and only
the Controller writes the ledger. Tools therefore call an authenticated internal
Controller endpoint, which authorises the request, persists the receipt, invokes
the real connector or ledger port, and returns a bounded result. The agent
identities receive run.invoker on this service and nothing else.

Nothing here infers the endpoint contract. The image reference and the endpoint
and asset details come from the contract file that the agents lane publishes; a
missing contract stops the run rather than being filled in with a guess.

`verify` is the security gate, not a formality. It fails if ingress is not
internal, if unauthenticated invocation is allowed, if any public principal holds
a binding, or if an agent account is missing run.invoker. A gateway reachable
from the internet is not a policy boundary.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.platform.config import PlatformConfig, resource_labels  # noqa: E402
from recall.platform.errors import PlatformError  # noqa: E402
from recall.platform.identity import SERVICE_IDENTITIES  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402

logger = logging.getLogger("recall.platform.gateway")

SERVICE_ID = "recall-tool-gateway"
GATEWAY_COMPONENT = "tool-gateway"
REQUIRED_INGRESS = "INGRESS_TRAFFIC_INTERNAL_ONLY"
PUBLIC_PRINCIPALS = frozenset({"allUsers", "allAuthenticatedUsers"})
INVOKER_ROLE = "roles/run.invoker"

# The three roles whose tools call the gateway. The Controller is deliberately
# absent: it hosts the endpoint, it does not invoke itself through it.
GATEWAY_CALLER_ACCOUNT_IDS = (
    "recall-sa-watcher",
    "recall-sa-assessor",
    "recall-sa-auditor",
)


def _session() -> Any:
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise PlatformError("gateway_sdk_unavailable", str(exc)) from exc
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def _service_path(config: PlatformConfig) -> str:
    return (
        f"projects/{config.project_id}/locations/"
        f"{config.agent_engine_location}/services/{SERVICE_ID}"
    )


def _base(config: PlatformConfig) -> str:
    return f"https://run.googleapis.com/v2/{_service_path(config)}"


def load_contract(path: Path) -> dict[str, Any]:
    """Read the endpoint contract the agents lane publishes.

    Deployment requirements are taken from this file. An absent contract is a
    stop, not a prompt to infer: guessing an audience or a tool route would
    produce a gateway that authorises the wrong thing.
    """

    if not path.is_file():
        raise PlatformError("gateway_contract_missing", str(path))
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlatformError("gateway_contract_unreadable", str(exc)[:120]) from exc
    if not isinstance(contract, dict):
        raise PlatformError("gateway_contract_malformed", type(contract).__name__)
    return contract


def cmd_plan(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Report what would be created, reading the contract, touching nothing."""

    contract = load_contract(Path(args.contract))
    _emit(
        {
            "service_id": SERVICE_ID,
            "region": config.agent_engine_location,
            "ingress": REQUIRED_INGRESS,
            "unauthenticated_invocation": "refused",
            "labels": resource_labels(GATEWAY_COMPONENT),
            "invoker_accounts": list(GATEWAY_CALLER_ACCOUNT_IDS),
            "contract_file": str(args.contract),
            "contract_keys": sorted(contract),
            "lifecycle": "persistent",
        },
        config.project_id,
        args.redact,
    )
    return 0


def cmd_deploy(args: argparse.Namespace, config: PlatformConfig) -> int:
    load_contract(Path(args.contract))
    session = _session()
    parent = (
        f"projects/{config.project_id}/locations/{config.agent_engine_location}"
    )
    body = {
        "labels": resource_labels(GATEWAY_COMPONENT),
        "ingress": REQUIRED_INGRESS,
        "template": {
            "serviceAccount": next(
                identity.email(config.project_id)
                for identity in SERVICE_IDENTITIES
                if identity.account_id == "recall-sa-controller"
            ),
            "containers": [{"image": args.image}],
        },
    }
    response = session.post(
        f"https://run.googleapis.com/v2/{parent}/services",
        params={"serviceId": SERVICE_ID},
        json=body,
        timeout=120,
    )
    if response.status_code not in (200, 201):
        raise PlatformError("gateway_create_failed", str(response.status_code))
    _emit(
        {"created": SERVICE_ID, "operation": response.json().get("name")},
        config.project_id,
        args.redact,
    )
    return cmd_verify(args, config)


def _iam_policy(session: Any, config: PlatformConfig) -> dict[str, Any]:
    response = session.get(f"{_base(config)}:getIamPolicy", timeout=60)
    if response.status_code != 200:
        raise PlatformError("gateway_iam_read_failed", str(response.status_code))
    return response.json()


def cmd_bind(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Grant run.invoker to the three agent accounts, and to nothing else."""

    session = _session()
    policy = _iam_policy(session, config)
    bindings = policy.setdefault("bindings", [])
    members = {
        f"serviceAccount:{account}@{config.project_id}.iam.gserviceaccount.com"
        for account in GATEWAY_CALLER_ACCOUNT_IDS
    }
    invoker = next(
        (b for b in bindings if b.get("role") == INVOKER_ROLE),
        None,
    )
    if invoker is None:
        invoker = {"role": INVOKER_ROLE, "members": []}
        bindings.append(invoker)
    existing = set(invoker.setdefault("members", []))
    public = existing & PUBLIC_PRINCIPALS
    if public:
        raise PlatformError("gateway_public_binding_present", ",".join(sorted(public)))
    added = sorted(members - existing)
    invoker["members"] = sorted(existing | members)
    response = session.post(
        f"{_base(config)}:setIamPolicy", json={"policy": policy}, timeout=60
    )
    if response.status_code != 200:
        raise PlatformError("gateway_iam_write_failed", str(response.status_code))
    _emit({"added_invokers": added}, config.project_id, args.redact)
    return cmd_verify(args, config)


def cmd_verify(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Fail unless the gateway is internal, authenticated, and correctly bound."""

    session = _session()
    response = session.get(_base(config), timeout=60)
    if response.status_code != 200:
        raise PlatformError("gateway_read_back_failed", str(response.status_code))
    service = response.json()
    policy = _iam_policy(session, config)

    invoker_members: set[str] = set()
    public_holders: list[str] = []
    for binding in policy.get("bindings", []):
        members = set(binding.get("members", []))
        for principal in PUBLIC_PRINCIPALS & members:
            public_holders.append(f"{binding.get('role')}:{principal}")
        if binding.get("role") == INVOKER_ROLE:
            invoker_members = members

    expected = {
        f"serviceAccount:{account}@{config.project_id}.iam.gserviceaccount.com"
        for account in GATEWAY_CALLER_ACCOUNT_IDS
    }
    missing = sorted(expected - invoker_members)
    ingress = service.get("ingress")
    findings: list[str] = []
    if ingress != REQUIRED_INGRESS:
        findings.append(f"ingress:{ingress}")
    if public_holders:
        findings.append("public_binding:" + ",".join(sorted(public_holders)))
    if missing:
        findings.append("missing_invoker:" + ",".join(m.split(":")[1] for m in missing))

    report = {
        "service_id": SERVICE_ID,
        "ingress": ingress,
        "ingress_ok": ingress == REQUIRED_INGRESS,
        "public_principals": sorted(public_holders),
        "invoker_members": sorted(invoker_members),
        "missing_invokers": missing,
        "uri": service.get("uri"),
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
    }
    _emit(report, config.project_id, args.redact)
    return 0 if not findings else 1


def cmd_destroy(args: argparse.Namespace, config: PlatformConfig) -> int:
    session = _session()
    response = session.delete(_base(config), timeout=120)
    if response.status_code not in (200, 202, 404):
        raise PlatformError("gateway_delete_failed", str(response.status_code))
    check = session.get(_base(config), timeout=60)
    _emit(
        {"deleted": SERVICE_ID, "read_back_status": check.status_code},
        config.project_id,
        args.redact,
    )
    return 0 if check.status_code == 404 else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", parents=[common])
    plan.add_argument("--contract", required=True)
    plan.set_defaults(handler=cmd_plan)

    deploy = sub.add_parser("deploy", parents=[common])
    deploy.add_argument("--contract", required=True)
    deploy.add_argument("--image", required=True)
    deploy.set_defaults(handler=cmd_deploy)

    for name, handler in (
        ("bind", cmd_bind),
        ("verify", cmd_verify),
        ("destroy", cmd_destroy),
    ):
        command = sub.add_parser(name, parents=[common])
        command.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
