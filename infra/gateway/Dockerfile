# Internal Tool Gateway service image.
#
# Carries the Controller and the frozen replay assets at the exact
# repository-relative layout the agents lane contract requires, so
# RECALL_REPLAY_ROOT resolves the manifest and the captures without rewriting
# any path. Startup verifies the manifest hash before serving; see
# infra/gateway/server.py.
#
# The capability signing key is never baked in. It arrives at runtime from
# Secret Manager as RECALL_TOOL_CAPABILITY_SECRET_B64, and nothing in this image
# writes it to disk or to a log.

# Pinned by digest so a rebuild cannot silently pick up a different base.
# Resolved from registry-1.docker.io on 2026-08-24; refresh deliberately, never
# as a side effect of another change, and re-resolve rather than editing by hand.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so application edits do not invalidate the layer.
#
# Versions are the repository's own pins from pyproject.toml, not a hand-picked
# set. The first build installed only firestore and uvicorn and the container
# died on import with ModuleNotFoundError: No module named 'google.adk',
# because recall.controller.tool_gateway imports ADK types. The gateway needs
# the same runtime the Controller needs.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir \
      "google-adk==2.7.1" \
      "google-cloud-aiplatform[agent_engines]==1.165.1" \
      "google-cloud-firestore==2.28.1" \
      "uvicorn==0.32.1"

# The Controller and its contracts.
COPY src/ /app/src/

# Frozen evidence, at the exact paths the contract pins under one replay root.
COPY docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json \
     /app/replay/docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json
COPY artifacts/evidence/rcl-205/ /app/replay/artifacts/evidence/rcl-205/

# The ASGI process this lane owns.
COPY infra/gateway/server.py /app/gateway_server.py

ENV PYTHONPATH=/app/src \
    RECALL_REPLAY_ROOT=/app/replay \
    RECALL_REPLAY_MANIFEST=/app/replay/docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json

# Run unprivileged. The gateway needs no write access to its own filesystem.
RUN useradd --create-home --uid 10001 gateway && chown -R gateway:gateway /app
USER 10001

# Cloud Run supplies PORT.
#
# One worker is a throughput choice, NOT a correctness one. At-most-once does not
# depend on it: FirestoreGatewayInvocationStore reserves and completes under
# @firestore.transactional on a document keyed by request_id in a shared
# collection, so the guarantee holds across processes AND across Cloud Run
# instances. Instance scaling is therefore free and max-instances needs no
# artificial cap.
#
# The single worker is here because the bounded backends, one public source and
# one ledger, absorb no benefit from in-process concurrency.
ENV PORT=8080
CMD exec uvicorn gateway_server:app --host 0.0.0.0 --port ${PORT} --workers 1
