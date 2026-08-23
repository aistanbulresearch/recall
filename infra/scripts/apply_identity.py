"""Create, verify, and remove the per-role service accounts and their IAM grants.

`src/recall/platform/identity.py` is the single source of truth for the roster and
its grants; this script only drives gcloud from that declaration, so the shell
path and the Python path can never disagree.

    python infra/scripts/apply_identity.py plan
    python infra/scripts/apply_identity.py apply
    python infra/scripts/apply_identity.py verify --redact
    python infra/scripts/apply_identity.py destroy

`verify` reads the live IAM policy back and reports drift. It exits non-zero when
the live policy does not match the declaration, so a missing grant fails loudly.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.errors import PlatformError  # noqa: E402
from recall.platform.identity import (  # noqa: E402
    SERVICE_IDENTITIES,
    RestAgentIdentityClient,
    assert_additive_policy_write,
    declared_inventory,
    observe_agent_identity,
    parse_policy_document,
    reconcile_bucket_policy,
    reconcile_project_policy,
)
from recall.platform.redaction import redact_identifiers  # noqa: E402

logger = logging.getLogger("recall.platform.identity")

INVENTORY_PATH = REPO_ROOT / "infra" / "iam_inventory.json"
GCLOUD_TIMEOUT_SECONDS = 120


def _gcloud_executable() -> str:
    # On Windows gcloud is a .cmd shim, which CreateProcess will not resolve from
    # the bare name. Resolve it once through PATH/PATHEXT instead.
    resolved = shutil.which("gcloud")
    if resolved is None:
        raise PlatformError("gcloud_not_on_path")
    return resolved


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    logger.info("gcloud %s", " ".join(args[1:3]))
    # Cap every call: an expired credential makes gcloud wait on an interactive
    # reauth prompt that never arrives, which would otherwise hang the script.
    try:
        result = subprocess.run(
            [_gcloud_executable(), *args[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=GCLOUD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise PlatformError(
            "gcloud_timeout", f"{' '.join(args[1:3])}:{GCLOUD_TIMEOUT_SECONDS}s"
        ) from exc
    if check and result.returncode != 0:
        raise PlatformError("gcloud_failed", result.stderr.strip()[:400])
    return result


def _redact(text: str, project_id: str, enabled: bool) -> str:
    return redact_identifiers(text, project_id) if enabled else text


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(_redact(rendered, project_id, redact))


def _write_inventory() -> None:
    INVENTORY_PATH.write_text(
        json.dumps(declared_inventory(), indent=2) + "\n", encoding="utf-8"
    )


def cmd_plan(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Render the declaration. Needs no credentials: the declaration is local."""

    if args.write:
        _write_inventory()
        print(f"declaration written to {INVENTORY_PATH.relative_to(REPO_ROOT)}")
    _emit(declared_inventory(), config.project_id, True)
    return 0


def cmd_apply(args: argparse.Namespace, config: PlatformConfig) -> int:
    project = config.project_id
    bucket = config.staging_bucket
    for identity in SERVICE_IDENTITIES:
        existing = _run(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "describe",
                identity.email(project),
                "--format=value(email)",
            ],
            check=False,
        )
        if existing.returncode != 0:
            _run(
                [
                    "gcloud",
                    "iam",
                    "service-accounts",
                    "create",
                    identity.account_id,
                    f"--display-name={identity.display_name}",
                    f"--project={project}",
                ]
            )
        for role in identity.bucket_roles:
            _run(
                [
                    "gcloud",
                    "storage",
                    "buckets",
                    "add-iam-policy-binding",
                    bucket,
                    f"--member={identity.member(project)}",
                    f"--role={role}",
                    "--format=none",
                ]
            )
    _apply_project_bindings(project)
    _write_inventory()
    print(f"declared inventory written to {INVENTORY_PATH.relative_to(REPO_ROOT)}")
    return cmd_verify(args, config)


def _apply_project_bindings(project: str) -> None:
    """Add every declared project grant in one read-modify-write.

    Per-role `add-iam-policy-binding` calls each re-read and re-write the whole
    policy, so a five-account roster contends with itself on the policy etag and
    can stall. One get, one merge, one set avoids that entirely.
    """

    policy_raw = _run(
        ["gcloud", "projects", "get-iam-policy", project, "--format=json"]
    ).stdout
    try:
        fetched = json.loads(policy_raw)
    except json.JSONDecodeError as exc:
        raise PlatformError("iam_policy_malformed", "not_json") from exc
    # Reject anything that is not a real policy before merging into it. A failed
    # fetch returns an error document, and merging into that then writing it back
    # would delete every binding on the project.
    original = parse_policy_document(fetched)
    policy = copy.deepcopy(dict(original))
    bindings = policy.setdefault("bindings", [])
    by_role = {binding.get("role"): binding for binding in bindings}
    for identity in SERVICE_IDENTITIES:
        member = identity.member(project)
        for role in identity.project_roles:
            binding = by_role.get(role)
            if binding is None:
                binding = {"role": role, "members": []}
                bindings.append(binding)
                by_role[role] = binding
            members = binding.setdefault("members", [])
            if member not in members:
                members.append(member)
    # Refuse a write that would drop any existing grant, ours or anyone else's.
    added_pairs = assert_additive_policy_write(original, policy)
    if not added_pairs:
        print("project bindings already complete")
        return
    added = len(added_pairs)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(policy, handle)
        policy_path = handle.name
    try:
        _run(
            [
                "gcloud",
                "projects",
                "set-iam-policy",
                project,
                policy_path,
                "--format=none",
            ]
        )
        print(f"added {added} project binding(s)")
    finally:
        Path(policy_path).unlink(missing_ok=True)


def _member_roles(policy: dict[str, Any]) -> dict[str, list[str]]:
    member_roles: dict[str, list[str]] = {}
    for binding in policy.get("bindings", []):
        role = binding.get("role")
        for member in binding.get("members", []):
            member_roles.setdefault(member, []).append(role)
    return member_roles


def _live_project_roles(project: str) -> dict[str, list[str]]:
    result = _run(["gcloud", "projects", "get-iam-policy", project, "--format=json"])
    return _member_roles(json.loads(result.stdout))


def _live_bucket_roles(bucket: str) -> dict[str, list[str]]:
    result = _run(
        ["gcloud", "storage", "buckets", "get-iam-policy", bucket, "--format=json"]
    )
    return _member_roles(json.loads(result.stdout))


def cmd_verify(args: argparse.Namespace, config: PlatformConfig) -> int:
    project = config.project_id
    accounts = _run(
        [
            "gcloud",
            "iam",
            "service-accounts",
            "list",
            f"--project={project}",
            "--filter=email:recall-sa-*",
            "--format=value(email)",
        ]
    )
    observed = sorted(line for line in accounts.stdout.split() if line)
    project_iam = reconcile_project_policy(_live_project_roles(project), project)
    bucket_iam = reconcile_bucket_policy(
        _live_bucket_roles(config.staging_bucket), project
    )
    report = {
        "service_accounts_found": len(observed),
        "service_accounts_expected": len(SERVICE_IDENTITIES),
        "emails": observed,
        "project_iam": project_iam,
        "staging_bucket_iam": bucket_iam,
    }
    _emit(report, project, args.redact)
    complete = (
        len(observed) == len(SERVICE_IDENTITIES)
        and project_iam["status"] == "MATCHED"
        and bucket_iam["status"] == "MATCHED"
    )
    return 0 if complete else 1


def cmd_observe(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Record what the Agent Identity surface reports, empty or degraded included."""

    client = RestAgentIdentityClient(config)
    observations = [
        observe_agent_identity(client, location)
        for location in (config.agent_engine_location, config.model_location)
    ]
    _emit(observations, config.project_id, args.redact)
    return 0


def cmd_destroy(args: argparse.Namespace, config: PlatformConfig) -> int:
    project = config.project_id
    for identity in SERVICE_IDENTITIES:
        for role in identity.bucket_roles:
            _run(
                [
                    "gcloud",
                    "storage",
                    "buckets",
                    "remove-iam-policy-binding",
                    config.staging_bucket,
                    f"--member={identity.member(project)}",
                    f"--role={role}",
                    "--format=none",
                ],
                check=False,
            )
        for role in identity.project_roles:
            _run(
                [
                    "gcloud",
                    "projects",
                    "remove-iam-policy-binding",
                    project,
                    f"--member={identity.member(project)}",
                    f"--role={role}",
                    "--condition=None",
                    "--format=none",
                ],
                check=False,
            )
        _run(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "delete",
                identity.email(project),
                f"--project={project}",
                "--quiet",
            ],
            check=False,
        )
    print("destroy issued; run verify to confirm removal")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", parents=[common])
    plan.add_argument(
        "--write",
        action="store_true",
        help="refresh infra/iam_inventory.json from the declaration",
    )
    plan.set_defaults(handler=cmd_plan)
    for name, handler in (
        ("apply", cmd_apply),
        ("verify", cmd_verify),
        ("observe", cmd_observe),
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
