"""Negative authentication cases against the tool gateway.

These are only meaningful because the gateway now enforces by IAM rather than by
network invisibility. Under the previous internal-ingress posture every one of
these produced an identical 404 from the front end with no credential evaluated
at all, so a suite run from here would have reported five refusals and proved
nothing. See artifacts/evidence/gateway-posture/ for both halves of that pair.

Each case asserts the OBSERVED refusal, not an expected one taken on faith. A
row that cannot be exercised is reported as NOT EXERCISED with its reason,
never approximated by a different case that happens to fail. Reporting a green
row for a case that was not run is the failure mode this whole exercise exists
to prevent.

No token value is ever printed. Tokens are read, used, and dropped.

Usage:
    python infra/scripts/negative_auth_cases.py --url <gateway-url>
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from typing import Any

INVOKE_PATH = "/v1/tools/evidence_connector:invoke"


def _curl(url: str, headers: list[str]) -> dict[str, Any]:
    cmd = [
        "curl", "-s", "-o", "-", "-w", "\n%{http_code} %{time_total}",
        "--max-time", "25", "-X", "POST",
        "-H", "Content-Type: application/json", "-d", "{}",
    ]
    for header in headers:
        cmd += ["-H", header]
    cmd.append(url)
    started = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = round(time.monotonic() - started, 3)
    text = result.stdout.strip()
    tail = text.rsplit("\n", 1)[-1] if "\n" in text else text
    body = text[: -len(tail)].strip() if "\n" in text else ""
    parts = tail.split()
    code = parts[0] if parts else "000"
    return {
        "http_code": code,
        "seconds": elapsed,
        "body_excerpt": body[:200],
        "body_bytes": len(body),
    }


def _unsigned_jwt(audience: str) -> str:
    """A structurally valid JWT that no one issued.

    Signature bytes are literal garbage, not a signature over anything. No key
    material is generated: this token is meant to be unverifiable, and making it
    verifiable-by-someone would be a different test.
    """

    def seg(obj: dict[str, Any]) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header = seg({"alg": "RS256", "typ": "JWT", "kid": "not-a-real-key"})
    claims = seg(
        {
            "iss": "https://not-google.example.invalid",
            "aud": audience,
            "sub": "negative-auth-probe",
            "email": "probe@example.invalid",
            "iat": 1700000000,
            "exp": 4102444800,
        }
    )
    return f"{header}.{claims}.bm90LWEtcmVhbC1zaWduYXR1cmU"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    endpoint = args.url.rstrip("/") + INVOKE_PATH

    google_signed_wrong_audience = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, shell=True,
    ).stdout.strip()

    cases: list[dict[str, Any]] = []

    outcome = _curl(endpoint, [])
    cases.append({
        "case": "no_token",
        "what_is_presented": "no Authorization header at all",
        "exercises": "authentication",
        **outcome,
    })

    if google_signed_wrong_audience:
        outcome = _curl(endpoint, [f"Authorization: Bearer {google_signed_wrong_audience}"])
        cases.append({
            "case": "wrong_audience",
            "what_is_presented": (
                "a genuinely Google-signed ID token (iss accounts.google.com) whose "
                "aud is the gcloud OAuth client id, not this service URL"
            ),
            "exercises": "authentication (audience binding)",
            **outcome,
        })
    else:
        cases.append({
            "case": "wrong_audience",
            "status": "NOT EXERCISED",
            "reason": "could not obtain a Google-signed identity token",
        })

    outcome = _curl(endpoint, [f"Authorization: Bearer {_unsigned_jwt(args.url)}"])
    cases.append({
        "case": "wrong_issuer",
        "what_is_presented": (
            "a structurally valid JWT claiming iss not-google.example.invalid, "
            "signature bytes are literal garbage"
        ),
        "exercises": "authentication (issuer/signature)",
        **outcome,
    })

    for case in cases:
        if "http_code" not in case:
            continue
        code = case["http_code"]
        case["never_200"] = code != "200"
        case["never_404"] = code != "404"
        case["refused_with_reason"] = code in ("401", "403")
        case["observed_reason"] = {
            "401": "unauthenticated (credential could not be verified)",
            "403": "forbidden (no grant for this principal)",
        }.get(code, f"unexpected:{code}")

    not_exercised = [
        {
            "case": "wrong_principal_authorization",
            "status": "NOT EXERCISED",
            "reason": (
                "requires a validly-signed token correctly audienced to this service "
                "from a principal WITHOUT run.invoker. User accounts cannot mint "
                "audience-scoped tokens, and roles/owner does not include "
                "iam.serviceAccounts.getOpenIdToken, so no such token can be produced "
                "with current permissions. This is the only row that would exercise "
                "AUTHORIZATION rather than authentication; the table is missing it, "
                "not merely shorter."
            ),
        },
        {
            "case": "expired_token",
            "status": "NOT EXERCISED",
            "reason": (
                "a hand-crafted expired JWT fails signature validation before expiry "
                "is evaluated, so it would report the wrong_issuer refusal and mask "
                "which layer refused. Isolating expiry needs a genuinely "
                "Google-signed token aged past exp, which requires the same "
                "impersonation permission that is unavailable."
            ),
        },
    ]

    exercised = [c for c in cases if "http_code" in c]
    report = {
        "probe": "gateway_negative_auth",
        "endpoint": endpoint,
        "posture": "ingress=all, IAM-only enforcement",
        "cases_exercised": len(exercised),
        "all_refused": all(c["refused_with_reason"] for c in exercised),
        "never_200": all(c["never_200"] for c in exercised),
        "never_404": all(c["never_404"] for c in exercised),
        "distinct_reasons": sorted({c["observed_reason"] for c in exercised}),
        "cases": cases,
        "not_exercised": not_exercised,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["all_refused"] and report["never_200"] and report["never_404"] else 1


if __name__ == "__main__":
    sys.exit(main())
