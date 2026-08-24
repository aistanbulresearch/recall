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
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from collections.abc import Mapping
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
# Posture changed 2026-08-25 on owner authorization, after the external
# auditor ruled option (a) unconditional.
#
# Old: INGRESS_TRAFFIC_INTERNAL_ONLY. That was invisibility, not authentication.
# It evaluated no credentials: from outside the perimeter every request got an
# identical 404 in under half a second whether it carried no token, a garbage
# bearer, or nothing at all. Worse, it left NO vantage point from which the
# refusal path could be observed -- the agents are the only in-perimeter
# callers and they always present their own correct identity, so the
# authorization path was untestable in principle rather than merely untested.
#
# New: INGRESS_TRAFFIC_ALL with IAM as the sole enforcement. Cloud Run checks
# the caller's identity before a request reaches the container, so refusals are
# now reasoned and observable. The security claim was always identity-based;
# this makes it testable instead of merely asserted.
#
# The cost is real and is why the checks below got stricter: network isolation
# is gone, so IAM is load bearing alone. Two consequences that were previously
# masked now matter operationally, and verify reports both.
REQUIRED_INGRESS = "INGRESS_TRAFFIC_ALL"
PREVIOUS_INGRESS = "INGRESS_TRAFFIC_INTERNAL_ONLY"
PUBLIC_PRINCIPALS = frozenset({"allUsers", "allAuthenticatedUsers"})
INVOKER_ROLE = "roles/run.invoker"
# Every sensitive value reaches the container as a Secret Manager reference.
# None of them appears in this repository, in a deploy config, on a command line,
# or in a report. An earlier revision of this file carried the NCBI contact
# address as a literal, which is exactly what this arrangement removes.
CAPABILITY_SECRET_ID = "recall-tool-capability-key"
NCBI_TOOL_SECRET_ID = "recall-ncbi-tool"
NCBI_EMAIL_SECRET_ID = "recall-ncbi-email"

SECRET_ENV: Mapping[str, str] = {
    "RECALL_TOOL_CAPABILITY_SECRET_B64": CAPABILITY_SECRET_ID,
    "RECALL_NCBI_TOOL": NCBI_TOOL_SECRET_ID,
    "RECALL_NCBI_EMAIL": NCBI_EMAIL_SECRET_ID,
}

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
    """Bind this deployment to the contract document it was built against.

    The contract is prose, not configuration: the agents lane publishes it as
    Markdown and the deployment values are read by a human from it. An earlier
    draft of this function parsed it as JSON, which was simply wrong about what
    the file is.

    What is mechanically useful is provenance. Record the document's digest so a
    deployment report names the exact contract revision it satisfied, and stop if
    the document is absent, because a deployment that cannot name its contract
    cannot claim to meet it.
    """

    if not path.is_file():
        raise PlatformError("gateway_contract_missing", str(path))
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    required = [
        marker
        for marker in (b"/v1/tools/", b"RECALL_TOOL_GATEWAY_AUDIENCE", b"run.invoker")
        if marker not in body
    ]
    if required:
        raise PlatformError(
            "gateway_contract_unrecognised",
            ",".join(marker.decode() for marker in required),
        )
    return {"path": str(path), "sha256": digest, "bytes": len(body)}


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
            "contract_sha256": contract["sha256"],
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
    body = _service_body(config, args.image, audience=args.audience)
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


def _account_email(config: PlatformConfig, account_id: str) -> str:
    return next(
        identity.email(config.project_id)
        for identity in SERVICE_IDENTITIES
        if identity.account_id == account_id
    )


def _capability_secret_version(session: Any, config: PlatformConfig) -> str:
    """Resolve which capability-key version `latest` currently points at."""

    url = (
        "https://secretmanager.googleapis.com/v1/projects/"
        f"{config.project_id}/secrets/{CAPABILITY_SECRET_ID}/versions/latest"
    )
    response = session.get(url, timeout=60)
    if response.status_code != 200:
        raise PlatformError("gateway_secret_version_unreadable", str(response.status_code))
    return str(response.json().get("name", "")).rsplit("/", 1)[-1]


def _service_body(
    config: PlatformConfig,
    image: str,
    *,
    audience: str | None,
    capability_secret_version: str | None = None,
) -> dict[str, Any]:
    """The service definition, with the capability key as a reference only.

    The signing key is mounted from Secret Manager by Cloud Run. It is never read
    by this script, never passed on a command line, and never written to the
    inventory or a report.
    """

    env: list[dict[str, Any]] = [
        {
            "name": "RECALL_WATCHER_PRINCIPAL",
            "value": _account_email(config, "recall-sa-watcher"),
        },
        {
            "name": "RECALL_ASSESSOR_PRINCIPAL",
            "value": _account_email(config, "recall-sa-assessor"),
        },
        {
            "name": "RECALL_AUDITOR_PRINCIPAL",
            "value": _account_email(config, "recall-sa-auditor"),
        },
    ]
    for variable, secret_id in sorted(SECRET_ENV.items()):
        env.append(
            {
                "name": variable,
                "valueSource": {
                    "secretKeyRef": {"secret": secret_id, "version": "latest"}
                },
            }
        )
    if audience:
        env.append({"name": "RECALL_TOOL_GATEWAY_AUDIENCE", "value": audience})
    template: dict[str, Any] = {
        "serviceAccount": _account_email(config, "recall-sa-controller"),
        "containers": [{"image": image, "env": env}],
    }
    # Ingress is SERVICE metadata, so changing it does not by itself cut a new
    # revision. Stamping the posture onto the revision template does two things:
    # it satisfies the owner's "new revision" condition honestly rather than by
    # forcing a cosmetic change, and it makes every revision carry the posture
    # it was deployed under, so revision history answers "when did this become
    # publicly reachable" without anyone reconstructing it from audit logs.
    annotations = {"recall.dev/ingress-posture": REQUIRED_INGRESS}
    if capability_secret_version:
        # Records which key version this revision was built against, and makes a
        # rotation produce a new revision. Cloud Run creates no revision when the
        # spec is byte-identical, so rotating the secret behind an unchanged spec
        # would leave the old revision serving with the old key and look like a
        # deploy that did nothing.
        annotations["recall.dev/capability-secret-version"] = capability_secret_version
    template["annotations"] = annotations
    return {
        "labels": resource_labels(GATEWAY_COMPONENT),
        "ingress": REQUIRED_INGRESS,
        "template": template,
    }


def _await_ready(session: Any, config: PlatformConfig, attempts: int = 40) -> dict[str, Any]:
    """Wait for a revision to become ready, reporting the failure if it does not."""

    for attempt in range(attempts):
        service = session.get(_base(config), timeout=60).json()
        if service.get("latestReadyRevision"):
            return service
        failed = [
            c
            for c in service.get("conditions", [])
            if c.get("state") == "CONDITION_FAILED"
        ]
        if failed and attempt > 2:
            raise PlatformError(
                "gateway_revision_failed",
                str(failed[0].get("message", ""))[:160],
            )
        time.sleep(10)
    raise PlatformError("gateway_revision_not_ready", f"{attempts * 10}s")



def _current_audience(session: Any, config: PlatformConfig) -> str | None:
    """Read the audience currently configured on the running service."""

    read = session.get(_base(config), timeout=60)
    if read.status_code != 200:
        return None
    containers = (
        read.json().get("template", {}).get("containers")
        or read.json().get("spec", {}).get("template", {}).get("containers")
        or []
    )
    for container in containers:
        for entry in container.get("env", []):
            if entry.get("name") == "RECALL_TOOL_GATEWAY_AUDIENCE":
                return entry.get("value")
    return None


def cmd_update_image(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Roll the service onto a new image and wait for the revision to serve."""

    session = _session()
    version = _capability_secret_version(session, config)
    # Preserve the audience already on the service unless one is passed.
    #
    # _service_body omits the audience env var when it is falsy, so a PATCH that
    # did not intend to touch the audience DELETED it. That happened on
    # 2026-08-25: revision 00006 came up without RECALL_TOOL_GATEWAY_AUDIENCE
    # and died with HealthCheckContainerError, because the server validates its
    # environment at import. A partial update must never silently drop
    # configuration it was not asked to change.
    #
    # The container failing to start is the good half of that story: an audience
    # -less gateway would either reject every agent call or skip audience
    # validation entirely, and it refused to serve instead.
    audience = args.audience or _current_audience(session, config)
    if not audience:
        raise PlatformError("gateway_audience_unresolved", SERVICE_ID)
    response = session.patch(
        _base(config),
        json=_service_body(
            config,
            args.image,
            audience=audience,
            capability_secret_version=version,
        ),
        timeout=300,
    )
    if response.status_code not in (200, 201):
        raise PlatformError("gateway_patch_failed", str(response.status_code))
    service = _await_ready(session, config)
    _emit(
        {
            "image": args.image,
            "uri": service.get("uri"),
            "ready_revision": (service.get("latestReadyRevision") or "").rsplit("/", 1)[-1],
        },
        config.project_id,
        args.redact,
    )
    return 0


def cmd_set_audience(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Set the audience to the service's own URL, then confirm it took.

    The contract pins the audience to the exact service URL, which Cloud Run only
    assigns at create time. So the URL is read back and written in rather than
    predicted; a predicted URL that turned out wrong would mint tokens no one
    accepts.
    """

    session = _session()
    read = session.get(_base(config), timeout=60)
    if read.status_code != 200:
        raise PlatformError("gateway_read_back_failed", str(read.status_code))
    uri = read.json().get("uri")
    if not uri:
        raise PlatformError("gateway_uri_unassigned")
    response = session.patch(
        _base(config),
        json=_service_body(config, args.image, audience=uri),
        timeout=180,
    )
    if response.status_code not in (200, 201):
        raise PlatformError("gateway_patch_failed", str(response.status_code))
    _emit({"audience_set_to": uri}, config.project_id, args.redact)
    return 0


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



def _inherited_invokers(session: Any, config: PlatformConfig) -> list[dict[str, Any]]:
    """Project-level principals that can invoke regardless of the service binding.

    The service IAM policy lists three service accounts, and reporting that as
    "exactly three principals can call this" is false: any project-level role
    containing run.routes.invoke confers it on every service. Under internal
    ingress the network hid this. It does not any more.
    """

    url = (
        "https://cloudresourcemanager.googleapis.com/v1/projects/"
        f"{config.project_id}:getIamPolicy"
    )
    response = session.post(url, json={}, timeout=60)
    if response.status_code != 200:
        return [{"role": "<unreadable>", "detail": str(response.status_code)}]
    carriers = []
    for binding in response.json().get("bindings", []):
        role = binding.get("role", "")
        detail = session.get(
            f"https://iam.googleapis.com/v1/{role}"
            if role.startswith("roles/")
            else f"https://iam.googleapis.com/v1/projects/{config.project_id}/roles/{role}",
            timeout=60,
        )
        if detail.status_code != 200:
            continue
        if "run.routes.invoke" in detail.json().get("includedPermissions", []):
            carriers.append({"role": role, "members": sorted(binding.get("members", []))})
    return carriers


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
    # Checked in BOTH directions. The gate previously computed only what was
    # absent, so a fourth invoker added by anyone would have passed it. Under
    # internal ingress that asymmetry was cushioned by the network; with IAM as
    # the only enforcement it is the whole attack surface.
    unexpected = sorted(invoker_members - expected)
    inherited = _inherited_invokers(session, config)
    ingress = service.get("ingress")
    findings: list[str] = []
    if ingress != REQUIRED_INGRESS:
        findings.append(f"ingress:{ingress}")
    if public_holders:
        findings.append("public_binding:" + ",".join(sorted(public_holders)))
    if missing:
        findings.append("missing_invoker:" + ",".join(m.split(":")[1] for m in missing))
    if unexpected:
        findings.append("unexpected_invoker:" + ",".join(unexpected))

    report = {
        "service_id": SERVICE_ID,
        "ingress": ingress,
        "ingress_ok": ingress == REQUIRED_INGRESS,
        "public_principals": sorted(public_holders),
        "invoker_members": sorted(invoker_members),
        "missing_invokers": missing,
        "unexpected_invokers": unexpected,
        # Not a finding by itself: a project owner can invoke anything, and
        # saying so is honest rather than alarming. It is REPORTED because
        # "exactly three principals can call the gateway" was never true and
        # the service-level binding alone cannot show it.
        "inherited_project_invokers": inherited,
        "previous_ingress": PREVIOUS_INGRESS,
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
    deploy.add_argument("--audience", default=None)
    deploy.set_defaults(handler=cmd_deploy)

    update = sub.add_parser("update-image", parents=[common])
    update.add_argument("--image", required=True)
    update.add_argument("--audience", default=None)
    update.set_defaults(handler=cmd_update_image)

    audience = sub.add_parser("set-audience", parents=[common])
    audience.add_argument("--image", required=True)
    audience.set_defaults(handler=cmd_set_audience)

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
