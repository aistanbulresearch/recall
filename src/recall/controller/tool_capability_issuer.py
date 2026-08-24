from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import re
from uuid import uuid4

from recall.agents.config import ROLE_TOOL_IDS
from recall.contracts import AgentRole, DataMode
from recall.controller.tool_capability import (
    ROLE_ARTIFACT_SCHEMA_NAMES,
    RefetchGrant,
    RunToolCapability,
    ToolCapabilityCodec,
)
from recall.ledger import LedgerPort


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ToolCapabilityIssuer:
    """Issue signed grants only after resolving their scope from the ledger."""

    def __init__(self, ledger: LedgerPort, codec: ToolCapabilityCodec) -> None:
        self._ledger = ledger
        self._codec = codec

    def issue(
        self,
        *,
        role: AgentRole,
        case_id: str,
        run_id: str,
        data_mode: DataMode,
        expires_at: datetime,
        allowed_artifact_ids: Sequence[str] = (),
        allowed_artifact_schema_names: Sequence[str] = (),
        allowed_replay_stages: Sequence[str] = (),
        refetch_claims: Mapping[str, str] | None = None,
        capability_id: str | None = None,
        issued_at: datetime | None = None,
    ) -> str:
        issued = issued_at or self._codec.now()
        artifact_ids = tuple(sorted(set(allowed_artifact_ids)))
        schema_names = tuple(sorted(set(allowed_artifact_schema_names)))
        if set(schema_names) - set(ROLE_ARTIFACT_SCHEMA_NAMES[role]):
            raise ValueError("tool_capability_schema_not_role_allowed")
        for artifact_id in artifact_ids:
            artifact = self._ledger.get_artifact(artifact_id)
            if artifact is None:
                raise ValueError("capability_artifact_missing")
            if artifact["case_id"] != case_id:
                raise ValueError("capability_artifact_case_mismatch")
            if artifact["run_id"] != run_id:
                raise ValueError("capability_artifact_run_mismatch")
            if artifact["schema_name"] not in schema_names:
                raise ValueError("capability_artifact_schema_not_granted")
            if artifact["data_mode"] != data_mode.value:
                raise ValueError("capability_artifact_data_mode_mismatch")
        grants = [
            self._derive_refetch_grant(claim_id, source_artifact_id)
            for claim_id, source_artifact_id in (refetch_claims or {}).items()
        ]
        capability = RunToolCapability(
            capability_id=capability_id or str(uuid4()),
            role=role,
            case_id=case_id,
            run_id=run_id,
            data_mode=data_mode,
            allowed_tool_ids=tuple(sorted(ROLE_TOOL_IDS[role])),
            allowed_artifact_ids=artifact_ids,
            allowed_artifact_schema_names=schema_names,
            allowed_replay_stages=tuple(sorted(set(allowed_replay_stages))),
            refetch_grants=tuple(sorted(grants, key=lambda item: item.claim_id)),
            issued_at=issued,
            expires_at=expires_at,
        )
        return self._codec.issue(capability)

    def _derive_refetch_grant(
        self, claim_id: str, source_artifact_id: str
    ) -> RefetchGrant:
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError("capability_refetch_claim_invalid")
        artifact = self._ledger.get_artifact(source_artifact_id)
        if artifact is None:
            raise ValueError("capability_source_artifact_missing")
        if artifact["schema_name"] != "EvidenceObservation":
            raise ValueError("capability_refetch_source_schema_invalid")
        structured = artifact.get("structured_fields")
        if not isinstance(structured, Mapping):
            raise ValueError("capability_refetch_metadata_missing")
        metadata = structured.get("citation_metadata")
        fields = frozenset({"identifier", "title", "locator", "content_hash"})
        if (
            not isinstance(metadata, Mapping)
            or set(metadata) != fields
            or any(
                not isinstance(metadata[field], str) or not metadata[field]
                for field in fields
            )
        ):
            raise ValueError("capability_refetch_metadata_invalid")
        content_hash = metadata["content_hash"]
        if not isinstance(content_hash, str) or not _SHA256.fullmatch(content_hash):
            raise ValueError("capability_refetch_content_hash_invalid")
        return RefetchGrant(
            claim_id=claim_id,
            source_artifact_id=source_artifact_id,
            source_artifact_content_hash=str(artifact["content_hash"]),
            identifier=metadata["identifier"],
            title=metadata["title"],
            locator=metadata["locator"],
            content_hash=content_hash,
            data_mode=DataMode(str(artifact["data_mode"])),
        )
