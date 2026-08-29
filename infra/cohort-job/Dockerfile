# Managed cohort day-N job image.
#
# Runs `python -m recall.scheduler.entrypoint`, the only command L2's contract
# exposes (docs/platform/COHORT_JOB_ENTRYPOINT.md). L1 owns everything else:
# this file, the job, the schedule, the IAM.
#
# NO CREDENTIAL MATERIAL ENTERS THIS IMAGE. The contract is explicit: the job
# uses its service account through workload ADC, and no user ADC, HMAC key or
# RECALL_PRIVACY_SIGNING_KEY may be baked in or set on the job. Nothing here
# copies a key, and nothing here sets one.

# Pinned by digest so a rebuild cannot silently pick up a different base.
# Same base the gateway image resolved on 2026-08-24; re-resolve deliberately
# rather than editing the tag by hand.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

ARG RECALL_SOURCE_COMMIT
ARG RECALL_SOURCE_TREE
LABEL org.opencontainers.image.revision=${RECALL_SOURCE_COMMIT} \
      org.opencontainers.image.recall-source-tree=${RECALL_SOURCE_TREE}

COPY pyproject.toml uv.lock ./
COPY infra/cohort-job/dependency_inventory.py /app/infra/cohort-job/dependency_inventory.py
RUN pip install --no-cache-dir --no-deps \
      "https://files.pythonhosted.org/packages/8d/c4/97fdd4fca11d06633bb500849f70e4e6b201bcba3833894732e709be2d60/uv-0.12.3-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl#sha256=1482d1462b1aecd18ee33627363fe1c63d6a194f12d40d37efc446d9e0d800a1" \
    && uv sync --locked --no-dev --no-install-project \
    && /app/.venv/bin/python -m ensurepip \
    && /app/.venv/bin/python -m pip check \
    && /app/.venv/bin/python /app/infra/cohort-job/dependency_inventory.py write \
         --lock=/app/uv.lock \
         --manifest=/app/infra/cohort-job/dependency_inventory.json

COPY src/ /app/src/
COPY infra/cohort-job/runtime_contract.py /app/infra/cohort-job/runtime_contract.py
COPY infra/cohort-job/build_context_manifest.json /app/infra/cohort-job/build_context_manifest.json

# The files the entrypoint actually reads, derived from the code rather than
# guessed:
#   preparation.py  DEFAULT_BUNDLE_PATH  -> the bundle, sha256-verified on load
#   cohort.py       SOURCE_MANIFEST      -> the replay manifest
#   cohort.py       REPLAY_ANCHORS       -> five capture files, each sha256-verified
# Every one of these is hash-checked at runtime, so a wrong or truncated copy
# fails loudly at startup rather than producing a subtly wrong selection.
COPY artifacts/evidence/cohort-preparation-v1/preparation-bundle.json \
     /app/artifacts/evidence/cohort-preparation-v1/preparation-bundle.json
COPY docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json \
     /app/docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json
COPY artifacts/evidence/rcl-205/clinvar/ /app/artifacts/evidence/rcl-205/clinvar/
#   history.py      DAY1_EVIDENCE_PATH   -> the committed day-1 evidence blob
# Added when the DAY1_HISTORY literal was replaced by a receipt derived from this
# file. Its sha256 is declared in history.py as DAY1_EVIDENCE_SHA256 and checked
# on load, so a missing or altered copy fails at startup instead of silently
# producing a day-1 history that nothing wrote.
COPY artifacts/evidence/day1-manual-20260825-a7f31c9d/first.json \
     /app/artifacts/evidence/day1-manual-20260825-a7f31c9d/first.json
#   compressed_plan.py         PLAN_PATH                       -> the committed plan
#   compressed_preparation.py  DEFAULT_COMPRESSED_BUNDLE_PATH  -> the v2 bundle
# Both sha256-verified on load (the plan sha is additionally cross-checked
# against the bundle), so a wrong or stale copy refuses at startup by name.
COPY artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json /app/artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json
COPY artifacts/evidence/cohort-compression/preparation-bundle-v2.json /app/artifacts/evidence/cohort-compression/preparation-bundle-v2.json

# repo_root defaults to Path.cwd(), so WORKDIR is the repo root as far as the
# entrypoint is concerned, and every path above is resolved relative to it.
ENV PYTHONPATH=/app/src

# Run unprivileged. The job writes to Firestore, never to its own filesystem.
RUN useradd --create-home --uid 10001 cohort && chown -R cohort:cohort /app
USER 10001

# Real mode takes no arguments and derives the date from the UTC clock; the
# preview surface is reached by appending --preview-date YYYY-MM-DD as a job
# argument override, which is how deployment is verified without a second
# selection run.
ENTRYPOINT ["/app/.venv/bin/python", "-m", "recall.scheduler.entrypoint"]
