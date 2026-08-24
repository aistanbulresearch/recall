"""ASGI entrypoint for the internal Tool Gateway Cloud Run service.

The agents lane owns the gateway behaviour and publishes
`docs/platform/CONTROLLER_TOOL_GATEWAY_CONTRACT.md`; this module owns only the
process that hosts it. Every path, hash and variable name here comes from that
contract.

The application is built at import time so a misconfigured revision fails during
startup rather than on the first agent call. Cloud Run reports a revision that
cannot start, and a gateway that is not serving is visible; a gateway that starts
and then refuses every tool call looks like an agent problem.

Startup order matters and is deliberate:

1. Required environment is checked by `build_tool_gateway_from_environment`,
   which names every missing variable at once.
2. The replay manifest hash is verified against the value the contract pins,
   before any client is constructed, so a wrong image never reaches a backend.
3. Firestore clients are constructed last, because they are the only step that
   needs credentials.

The capability signing key is read from the environment by the gateway builder
and never by this module. It is not logged, echoed, or held in a local name.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from recall.controller.tool_gateway_asgi import ToolGatewayAsgiApp
from recall.controller.tool_gateway_runtime import build_tool_gateway_from_environment
from recall.controller.tool_gateway_store import FirestoreGatewayInvocationStore
from recall.ledger.firestore import FirestoreLedger

logger = logging.getLogger("recall.gateway")

# Pinned by docs/platform/CONTROLLER_TOOL_GATEWAY_CONTRACT.md. Startup requires
# this exact manifest before ReplayConnector verifies the ten capture hashes.
REQUIRED_MANIFEST_SHA256 = (
    "eb846f3a082fa4f0530caaf41bc7d67698cb3bcd1f0df54c3c2ba54af89437e8"
)


def verify_replay_manifest(manifest_path: Path) -> str:
    """Fail startup unless the manifest is byte-for-byte the pinned one.

    An image carrying different frozen evidence would still serve, and its
    results would look plausible, so the mismatch has to stop the process here.
    """

    if not manifest_path.is_file():
        raise RuntimeError(f"gateway_replay_manifest_missing:{manifest_path}")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest != REQUIRED_MANIFEST_SHA256:
        raise RuntimeError(
            "gateway_replay_manifest_mismatch:"
            f"expected_{REQUIRED_MANIFEST_SHA256[:12]}_got_{digest[:12]}"
        )
    return digest


def _firestore_client() -> object:
    from google.cloud import firestore

    return firestore.Client()


def build_application() -> ToolGatewayAsgiApp:
    """Construct the ASGI application, or fail the revision trying."""

    manifest = Path(os.environ.get("RECALL_REPLAY_MANIFEST", ""))
    digest = verify_replay_manifest(manifest)
    logger.info("replay manifest verified: %s", digest[:12])

    client = _firestore_client()
    gateway = build_tool_gateway_from_environment(
        ledger=FirestoreLedger(client),
        invocation_store=FirestoreGatewayInvocationStore(client),
    )
    logger.info("tool gateway ready")
    return ToolGatewayAsgiApp(gateway)


app = build_application()
