from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from recall.contracts import AgentRole


class IdentityVerifier(Protocol):
    def verify(self, token: str, audience: str) -> Mapping[str, object]: ...


class GoogleOidcVerifier:
    def verify(self, token: str, audience: str) -> Mapping[str, object]:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        return id_token.verify_oauth2_token(token, Request(), audience=audience)


def validate_gateway_identity_config(
    expected_audience: str,
    role_principals: Mapping[AgentRole, str],
) -> None:
    if not expected_audience.startswith("https://"):
        raise ValueError("gateway_https_audience_required")
    expected_roles = {
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    }
    principals = tuple(role_principals.values())
    if set(role_principals) != expected_roles or (
        any(
            not isinstance(principal, str)
            or not principal.endswith(".iam.gserviceaccount.com")
            for principal in principals
        )
        or len(set(principals)) != len(principals)
    ):
        raise ValueError("gateway_principal_map_invalid")


def validate_identity_claims(
    claims: Mapping[str, object],
    *,
    expected_audience: str,
    now: datetime,
) -> str | None:
    if claims.get("aud") != expected_audience:
        return "endpoint_audience_invalid"
    if claims.get("iss") not in {
        "accounts.google.com",
        "https://accounts.google.com",
    }:
        return "endpoint_issuer_invalid"
    if claims.get("email_verified") is not True:
        return "endpoint_email_unverified"
    email = claims.get("email")
    if not isinstance(email, str) or not email:
        return "endpoint_principal_missing"
    expiry = claims.get("exp")
    if not isinstance(expiry, (int, float)) or expiry <= now.timestamp():
        return "endpoint_token_expired"
    return None
