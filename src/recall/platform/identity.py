"""Per-role service identities and their narrowest IAM grants.

Every agent role runs under its own service account so a compromised or
misbehaving agent cannot reach another role's data. Agents never receive
Firestore access; only the Controller writes the ledger.

The declared inventory carries account ids and roles, never project ids or
addresses. `reconcile` compares the declaration against a live IAM policy and
reports drift; a missing grant is drift, not an empty result.

The Agent Identity surface is regional. `accessSummaries.list` answers HTTP 200
in a supported region and HTTP 403 for `global`; an unreachable listing is a
DEGRADED observation and never an empty-and-fine one.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from recall.contracts.enums import AgentRole

from .config import RESOURCE_PREFIX, PlatformConfig, require_resource_prefix
from .errors import PlatformError

logger = logging.getLogger(__name__)

AGENT_PROJECT_ROLES = ("roles/aiplatform.user",)
AGENT_BUCKET_ROLES = ("roles/storage.objectViewer",)
CONTROLLER_PROJECT_ROLES = ("roles/aiplatform.user", "roles/datastore.user")

SERVICE_ACCOUNT_DOMAIN = "iam.gserviceaccount.com"
PROJECT_PLACEHOLDER = "<project>"


@dataclass(frozen=True, slots=True)
class ServiceIdentity:
    """One role, one service account, and the grants that role actually needs."""

    account_id: str
    display_name: str
    project_roles: tuple[str, ...]
    bucket_roles: tuple[str, ...]
    agent_role: AgentRole | None

    def email(self, project_id: str) -> str:
        if not project_id:
            raise PlatformError("identity_project_missing", self.account_id)
        return f"{self.account_id}@{project_id}.{SERVICE_ACCOUNT_DOMAIN}"

    def member(self, project_id: str) -> str:
        return f"serviceAccount:{self.email(project_id)}"

    def redacted_email(self) -> str:
        """Email shape safe to commit: the project segment stays a placeholder."""

        return f"{self.account_id}@{PROJECT_PLACEHOLDER}.{SERVICE_ACCOUNT_DOMAIN}"


def _identity(
    suffix: str,
    display_name: str,
    project_roles: Sequence[str],
    bucket_roles: Sequence[str],
    agent_role: AgentRole | None,
) -> ServiceIdentity:
    return ServiceIdentity(
        account_id=require_resource_prefix(f"{RESOURCE_PREFIX}sa-{suffix}", suffix),
        display_name=display_name,
        project_roles=tuple(project_roles),
        bucket_roles=tuple(bucket_roles),
        agent_role=agent_role,
    )


SERVICE_IDENTITIES: tuple[ServiceIdentity, ...] = (
    _identity(
        "coordinator",
        "Recall Fleet Coordinator",
        AGENT_PROJECT_ROLES,
        AGENT_BUCKET_ROLES,
        AgentRole.FLEET_COORDINATOR,
    ),
    _identity(
        "watcher",
        "Recall Evidence Watcher",
        AGENT_PROJECT_ROLES,
        AGENT_BUCKET_ROLES,
        AgentRole.EVIDENCE_WATCHER,
    ),
    _identity(
        "assessor",
        "Recall Evidence Assessor",
        AGENT_PROJECT_ROLES,
        AGENT_BUCKET_ROLES,
        AgentRole.EVIDENCE_ASSESSOR,
    ),
    _identity(
        "auditor",
        "Recall Citation Auditor",
        AGENT_PROJECT_ROLES,
        AGENT_BUCKET_ROLES,
        AgentRole.CITATION_AUDITOR,
    ),
    _identity(
        "controller",
        "Recall Controller",
        CONTROLLER_PROJECT_ROLES,
        (),
        None,
    ),
)

BY_ACCOUNT_ID: Mapping[str, ServiceIdentity] = {
    identity.account_id: identity for identity in SERVICE_IDENTITIES
}


def identity_for_role(role: AgentRole) -> ServiceIdentity:
    for identity in SERVICE_IDENTITIES:
        if identity.agent_role is role:
            return identity
    raise PlatformError("identity_role_unmapped", str(role))


def agents_hold_no_ledger_access() -> bool:
    """Ledger access belongs to the Controller alone."""

    return all(
        "roles/datastore.user" not in identity.project_roles
        for identity in SERVICE_IDENTITIES
        if identity.agent_role is not None
    )


def declared_inventory() -> dict[str, Any]:
    """Commit-safe IAM declaration: account ids and roles, no project identifiers."""

    if not agents_hold_no_ledger_access():
        raise PlatformError("identity_agent_holds_ledger_access")
    return {
        "project": PROJECT_PLACEHOLDER,
        "service_accounts": [
            {
                "account_id": identity.account_id,
                "display_name": identity.display_name,
                "email": identity.redacted_email(),
                "agent_role": (
                    identity.agent_role.value if identity.agent_role else None
                ),
                "project_roles": list(identity.project_roles),
                "staging_bucket_roles": list(identity.bucket_roles),
            }
            for identity in SERVICE_IDENTITIES
        ],
    }


@dataclass(frozen=True, slots=True)
class IdentityDrift:
    """Difference between the declaration and the live IAM policy."""

    account_id: str
    missing_roles: tuple[str, ...]
    unexpected_roles: tuple[str, ...]

    def to_wire(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "missing_roles": list(self.missing_roles),
            "unexpected_roles": list(self.unexpected_roles),
        }


def _reconcile(
    live_member_roles: Mapping[str, Iterable[str]],
    project_id: str,
    scope: str,
) -> dict[str, Any]:
    drifts: list[IdentityDrift] = []
    for identity in SERVICE_IDENTITIES:
        held = set(live_member_roles.get(identity.member(project_id), ()))
        declared = set(
            identity.project_roles if scope == "project" else identity.bucket_roles
        )
        missing = tuple(sorted(declared - held))
        unexpected = tuple(sorted(held - declared))
        if missing or unexpected:
            drifts.append(IdentityDrift(identity.account_id, missing, unexpected))
    return {
        "scope": scope,
        "status": "MATCHED" if not drifts else "DRIFTED",
        "checked_accounts": len(SERVICE_IDENTITIES),
        "drifts": [drift.to_wire() for drift in drifts],
    }


def reconcile_project_policy(
    live_member_roles: Mapping[str, Iterable[str]], project_id: str
) -> dict[str, Any]:
    """Compare declared project grants against a live IAM policy.

    `live_member_roles` maps an IAM member string to the roles it holds. A member
    absent from the policy reports every declared role as missing; it is never
    treated as satisfied.
    """

    return _reconcile(live_member_roles, project_id, "project")


def reconcile_bucket_policy(
    live_member_roles: Mapping[str, Iterable[str]], project_id: str
) -> dict[str, Any]:
    """Compare declared staging-bucket grants against a live bucket IAM policy.

    An identity that declares no bucket role must hold none; a stray grant is
    reported as drift rather than tolerated.
    """

    return _reconcile(live_member_roles, project_id, "staging_bucket")


class AgentIdentityClient(Protocol):
    """Read-only Agent Identity surface used by this lane."""

    def list_access_summaries(self, location: str) -> Mapping[str, Any]: ...

    def list_auth_providers(self, location: str) -> Mapping[str, Any]: ...


def observe_agent_identity(
    client: AgentIdentityClient, location: str
) -> dict[str, Any]:
    """Record what Agent Identity actually reports, including an empty catalog.

    An empty listing is recorded as `EMPTY`, a reachable non-empty listing as
    `OBSERVED`, and any transport or permission failure as `DEGRADED` with the
    reason. No branch reports a healthy default.
    """

    observation: dict[str, Any] = {"location": location}
    for key, call in (
        ("access_summaries", client.list_access_summaries),
        ("auth_providers", client.list_auth_providers),
    ):
        try:
            payload = call(location)
        except PlatformError as exc:
            observation[key] = {
                "status": "DEGRADED",
                "reason_code": exc.code,
                "detail": exc.detail,
            }
            continue
        items = _listed_items(payload)
        observation[key] = {
            "status": "EMPTY" if not items else "OBSERVED",
            "count": len(items),
        }
    return observation


def _listed_items(payload: Mapping[str, Any]) -> list[Any]:
    for key in ("accessSummaries", "authProviders"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


class RestAgentIdentityClient:
    """Agent Identity client over REST, authenticated with application default credentials."""

    BASE = "https://agentidentity.googleapis.com/v1"

    def __init__(self, config: PlatformConfig) -> None:
        self._project = config.project_id
        self._session = self._authorised_session()

    @staticmethod
    def _authorised_session() -> Any:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise PlatformError("identity_sdk_unavailable", str(exc)) from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def _get(self, location: str, resource: str) -> Mapping[str, Any]:
        url = f"{self.BASE}/projects/{self._project}/locations/{location}/{resource}"
        response = self._session.get(url, timeout=30)
        if response.status_code != 200:
            raise PlatformError(
                "identity_listing_unavailable", f"{resource}:{response.status_code}"
            )
        return response.json()

    def list_access_summaries(self, location: str) -> Mapping[str, Any]:
        return self._get(location, "accessSummaries")

    def list_auth_providers(self, location: str) -> Mapping[str, Any]:
        return self._get(location, "authProviders")
