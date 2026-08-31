from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
import os
from pathlib import Path

from recall.connectors import PubMedConnector, RefetchAdapter, ReplayConnector
from recall.contracts import AgentRole
from recall.controller.tool_capability import ToolCapabilityCodec
from recall.controller.tool_gateway import ToolGateway
from recall.controller.tool_gateway_identity import GoogleOidcVerifier
from recall.controller.tool_gateway_store import GatewayInvocationStore
from recall.ledger import LedgerPort


RCL205_MANIFEST_SHA256 = (
    "eb846f3a082fa4f0530caaf41bc7d67698cb3bcd1f0df54c3c2ba54af89437e8"
)


def load_frozen_replay_connector(
    repository_root: Path,
    manifest_path: Path,
    *,
    expected_manifest_sha256: str = RCL205_MANIFEST_SHA256,
) -> ReplayConnector:
    try:
        body = manifest_path.read_bytes()
    except OSError as exc:
        raise RuntimeError("replay_manifest_unavailable") from exc
    if sha256(body).hexdigest() != expected_manifest_sha256:
        raise RuntimeError("replay_manifest_hash_mismatch")
    connector = ReplayConnector(repository_root, manifest_path)
    connector.verify_manifest()
    return connector


def build_tool_gateway_from_environment(
    *,
    ledger: LedgerPort,
    invocation_store: GatewayInvocationStore,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    environment: Mapping[str, str] | None = None,
) -> ToolGateway:
    env = dict(os.environ if environment is None else environment)
    required = (
        "RECALL_TOOL_GATEWAY_AUDIENCE",
        "RECALL_TOOL_CAPABILITY_SECRET_B64",
        "RECALL_REPLAY_ROOT",
        "RECALL_REPLAY_MANIFEST",
        "RECALL_NCBI_TOOL",
        "RECALL_NCBI_EMAIL",
        "RECALL_WATCHER_PRINCIPAL",
        "RECALL_ASSESSOR_PRINCIPAL",
        "RECALL_AUDITOR_PRINCIPAL",
    )
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise RuntimeError(f"tool_gateway_environment_missing:{','.join(missing)}")
    try:
        secret = base64.b64decode(
            env["RECALL_TOOL_CAPABILITY_SECRET_B64"], validate=True
        )
    except (ValueError, TypeError) as exc:
        raise RuntimeError("tool_capability_secret_invalid") from exc
    replay = load_frozen_replay_connector(
        Path(env["RECALL_REPLAY_ROOT"]), Path(env["RECALL_REPLAY_MANIFEST"])
    )
    return ToolGateway(
        ledger=ledger,
        replay_connector=replay,
        pubmed_connector=PubMedConnector(
            tool=env["RECALL_NCBI_TOOL"], email=env["RECALL_NCBI_EMAIL"]
        ),
        refetch_adapter=RefetchAdapter(),
        capability_codec=ToolCapabilityCodec(secret, clock=clock),
        identity_verifier=GoogleOidcVerifier(),
        expected_audience=env["RECALL_TOOL_GATEWAY_AUDIENCE"],
        role_principals={
            AgentRole.EVIDENCE_WATCHER: env["RECALL_WATCHER_PRINCIPAL"],
            AgentRole.EVIDENCE_ASSESSOR: env["RECALL_ASSESSOR_PRINCIPAL"],
            AgentRole.CITATION_AUDITOR: env["RECALL_AUDITOR_PRINCIPAL"],
        },
        invocation_store=invocation_store,
        clock=clock,
    )
