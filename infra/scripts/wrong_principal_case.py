"""The authorization row: a valid token from a principal without run.invoker.

This is the only negative-auth case that exercises AUTHORIZATION rather than
authentication. The other three — no token, wrong audience, wrong issuer — all
ask whether a credential can be verified. This one asks whether a PERFECTLY
GOOD credential is refused because its principal has no grant.

It matters more than completeness. On 2026-08-25 we measured that Cloud Run
admits on identity and does NOT decide on audience, so the question of what IAM
actually enforces stopped being rhetorical.

Requires roles/iam.serviceAccountTokenCreator on recall-sa-controller, which is
a deliberate temporary privilege increase and is revoked immediately after the
capture. `--revoke` performs the revocation and PROVES it by reading the policy
back, because a delete call returning success is not evidence of absence.

    python infra/scripts/wrong_principal_case.py --capture
    python infra/scripts/wrong_principal_case.py --revoke

The principal is recall-sa-controller: it holds secret access but has NO
run.invoker binding on the gateway, which is exactly the shape this row needs.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.redaction import redact_json  # noqa: E402

PRINCIPAL_ID = "recall-sa-controller"
TOKEN_CREATOR_ROLE = "roles/iam.serviceAccountTokenCreator"
INVOKE_PATH = "/v1/tools/evidence_connector:invoke"


def _resolve(executable: str) -> str:
    """Resolve an executable to a real path so it can run WITHOUT a shell.

    gcloud is a .cmd on Windows, which is why shell=True is tempting here. It is
    also unsafe: this script passes a JSON body to curl, full of braces and
    quotes, and a shell would interpret them. shutil.which is the fix this
    project already adopted once; using shell=True was a regression of it.
    """

    found = shutil.which(executable)
    if not found:
        raise SystemExit(f"executable_not_found:{executable}")
    return found


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    resolved = [_resolve(cmd[0]), *cmd[1:]]
    return subprocess.run(resolved, capture_output=True, text=True, timeout=timeout)


def _sa_email(config: PlatformConfig) -> str:
    return f"{PRINCIPAL_ID}@{config.project_id}.iam.gserviceaccount.com"


def _mint(config: PlatformConfig, audience: str) -> str:
    """Mint an audience-correct identity token AS recall-sa-controller.

    A failure here must stop the run. Falling back to the developer's own
    credentials would silently substitute a principal that HOLDS invoke through
    roles/owner, and the case would report a pass for the opposite of what it
    claims to test. That is the exact failure mode this suite exists to catch,
    so it is refused loudly rather than handled gracefully.
    """

    result = _run([
        "gcloud", "auth", "print-identity-token",
        f"--impersonate-service-account={_sa_email(config)}",
        f"--audiences={audience}",
    ])
    token = result.stdout.strip()
    if not token or token.count(".") != 2:
        raise SystemExit(
            "wrong_principal_token_unavailable: could not mint as "
            f"{PRINCIPAL_ID}. Refusing to continue -- falling back to any other "
            "principal would test the wrong thing.\n" + result.stderr.strip()[:400]
        )
    return token


def _token_principal(token: str) -> dict[str, Any]:
    """Read back WHOSE token this is instead of trusting the mint command.

    An impersonated ID token carries NO email claim; the principal is the
    sub, which is the service account's numeric uniqueId. Looking for an
    email and finding none reads as "wrong principal" and is simply the
    wrong field -- that misread cost me a detour. The artifact now records
    the sub and the uniqueId side by side and states whether they match,
    because a prose claim that a token is the right one is not evidence.
    """

    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return {"sub": claims.get("sub"), "aud": claims.get("aud"), "iss": claims.get("iss")}


def _capture(config: PlatformConfig, gateway_url: str) -> int:
    audience = gateway_url
    token = _mint(config, audience)
    claims = _token_principal(token)
    unique_id = _run([
        "gcloud", "iam", "service-accounts", "describe", _sa_email(config),
        "--format=value(uniqueId)",
    ]).stdout.strip()
    request_id = str(uuid.uuid4())
    body = json.dumps({
        "protocol_version": "1.0",
        "request_id": request_id,
        "capability": "not-a-valid-capability",
        "arguments": {},
    })
    result = _run([
        "curl", "-s", "-o", "-", "-w", "\n%{http_code}",
        "--max-time", "25", "-X", "POST",
        gateway_url.rstrip("/") + INVOKE_PATH,
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "-d", body,
    ])
    text = result.stdout.strip()
    code = text.rsplit("\n", 1)[-1].strip()
    payload = text[: -len(code)].strip() if code else text

    expected = "403"
    doc: dict[str, Any] = {
        "case": "wrong_principal_authorization",
        "question": "does IAM refuse a valid credential whose principal has no grant?",
        "principal": f"{PRINCIPAL_ID} (secret access, NO run.invoker on the gateway)",
        "token": {
            "iss": claims["iss"],
            "aud": claims["aud"],
            "sub": claims["sub"],
            "service_account_unique_id": unique_id,
            "principal_confirmed": claims["sub"] == unique_id,
            "audience_correct": claims["aud"] == audience,
        },
        "request": "well-formed body, deliberately invalid capability",
        "request_id": request_id,
        "expected_http": expected,
        "observed_http": code,
        "expected_reason": "forbidden (authenticated, no grant for this principal)",
        "observed_reason": {
            "403": "forbidden (authenticated, no grant for this principal)",
            "401": "unauthenticated (credential could not be verified)",
        }.get(code, f"unexpected:{code}"),
        "reason_matches": code == expected,
        "answered_by": "Cloud Run IAM" if not payload.startswith("{") else "our container",
        "body_excerpt": payload[:240],
        "never_200": code != "200",
        "never_404": code != "404",
    }
    doc["verdict"] = (
        "PASS"
        if doc["reason_matches"]
        and doc["never_200"]
        and doc["token"]["principal_confirmed"]
        and doc["token"]["audience_correct"]
        else "FAIL"
    )

    out = Path("artifacts/evidence/gateway-negative-auth/wrong-principal-case.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(redact_json(doc, config.project_id), indent=2), encoding="utf-8")
    print(json.dumps(redact_json(doc, config.project_id), indent=2))
    print(f"\nartifact: {out}")
    print("NEXT: revoke the role with --revoke and state the revocation in the report.")
    return 0 if doc["verdict"] == "PASS" else 1


def _revoke(config: PlatformConfig) -> int:
    """Remove the grant and PROVE it is gone by reading the policy back."""

    email = _sa_email(config)
    account = _run(["gcloud", "config", "get-value", "account"]).stdout.strip()
    _run([
        "gcloud", "iam", "service-accounts", "remove-iam-policy-binding", email,
        f"--member=user:{account}", f"--role={TOKEN_CREATOR_ROLE}",
    ])
    read_back = _run([
        "gcloud", "iam", "service-accounts", "get-iam-policy", email, "--format=json"
    ])
    policy = json.loads(read_back.stdout or "{}")
    holders = [
        member
        for binding in policy.get("bindings", [])
        if binding.get("role") == TOKEN_CREATOR_ROLE
        for member in binding.get("members", [])
    ]
    still_granted = any(account and account in holder for holder in holders)
    doc = {
        "action": "revoke_token_creator",
        "service_account": PRINCIPAL_ID,
        "role": TOKEN_CREATOR_ROLE,
        "token_creator_holders_after": holders,
        "revoked": not still_granted,
        "proof": "read back from get-iam-policy; a remove call returning success is not evidence",
    }
    print(json.dumps(redact_json(doc, config.project_id), indent=2))
    return 0 if not still_granted else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--url", default=None)
    args = parser.parse_args()
    config = PlatformConfig.from_env()
    if args.revoke:
        return _revoke(config)
    if args.capture:
        import os

        url = args.url or os.environ.get("RECALL_TOOL_GATEWAY_URL", "")
        if not url:
            raise SystemExit("gateway url unresolved")
        return _capture(config, url)
    parser.error("choose --capture or --revoke")
    return 2


if __name__ == "__main__":
    sys.exit(main())
