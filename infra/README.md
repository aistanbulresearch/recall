# L1 platform infrastructure

Lane L1 owns every Google Cloud resource Recall creates. This directory holds the
inventory and the create/delete scripts for those resources.

## Rules this directory enforces

1. Every resource name starts with `recall-`.
2. Every resource carries the labels `lane=l1` and `component=<component>`.
3. Every created resource is recorded in `resources.json` in the same change.
4. Every resource has a single-command delete path in `scripts/`.
5. No project id, billing id, account address, or token value is committed here.
   Environment-specific values live in a local, git-ignored `infra/env.local.ps1`
   derived from `env.example.ps1`.

## Environment

```powershell
. .\infra\env.example.ps1   # copy to env.local.ps1 and fill in, then dot-source that
```

| Variable | Meaning |
|---|---|
| `RECALL_GCP_PROJECT` | Target project id |
| `RECALL_AGENT_ENGINE_LOCATION` | Agent Engine region, currently `us-central1` |
| `RECALL_MODEL` | `gemini-3.7-flash` |
| `RECALL_MODEL_LOCATION` | `global` — the only location that serves `gemini-3.7-flash` |
| `RECALL_STAGING_BUCKET` | `gs://recall-agent-engine-staging-<suffix>` |

`gemini-3.7-flash` returns HTTP 404 in `us-central1` and HTTP 200 at `global`, so
deployed agents run in `us-central1` while their model calls target the global
endpoint through `GOOGLE_CLOUD_LOCATION=global`.

## Tooling virtual environment

`pyproject.toml` and `uv.lock` belong to lane L2, so the Vertex AI Agent Engine
SDK is not added to the project dependency set by this lane. Smoke scripts run
from a separate interpreter outside the repository:

```powershell
uv venv --python 3.12 C:\Users\<user>\recall-platform-tooling\.venv
uv pip install --python C:\Users\<user>\recall-platform-tooling\.venv\Scripts\python.exe "google-cloud-aiplatform[adk,agent_engines]" google-adk
```

`src/recall/platform` itself imports the Vertex SDK lazily, so the deterministic
core and `tests/platform` run on the project interpreter with no cloud package.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/create_staging_bucket.ps1` | Create the labelled Agent Engine staging bucket |
| `scripts/delete_staging_bucket.ps1` | Remove that bucket |
| `scripts/list_resources.ps1` | Read back every `lane=l1` resource |
| `scripts/list_agent_engines.ps1` | Read back Agent Engines in one location |
| `scripts/label_agent_engine.ps1` | Apply and read back the lane labels on an Agent Engine |
| `scripts/delete_agent_engine.ps1` | Delete one Agent Engine by resource name |
| `scripts/apply_identity.py` | `plan` / `apply` / `verify` / `observe` / `destroy` the role service accounts |
| `scripts/observe_registry.py` | Read-only Agent Registry catalog observation |
| `smoke/hello_agent_engine.py` | Day-zero deploy, invoke, receipt, delete smoke |

`apply_identity.py verify` and `observe_registry.py catalogued` exit non-zero when
the live state does not match, so a missing grant or an uncatalogued agent fails a
script rather than passing quietly.

## Service identities

`src/recall/platform/identity.py` is the single source of truth for the five role
accounts and their grants; `infra/iam_inventory.json` is generated from it and
holds `<project>` placeholders rather than real addresses. Agents hold
`roles/aiplatform.user` plus `roles/storage.objectViewer` on the staging bucket
only; `roles/datastore.user` belongs to `recall-sa-controller` alone, so no agent
can reach the ledger.

Deploying an Agent Engine under one of these accounts needs
`iam.serviceAccounts.actAs` on the target account for the deploying principal.

## Agent Registry

Agent Registry v1 has no `agents.create`. An agent is catalogued because the
platform publishes it, or because its endpoint is registered through
`services.create`. `engine_is_catalogued` answers the question from the catalog
listing; a deployment call returning success is not evidence of cataloguing.
