# Lane L1 smoke environment. Source before running infra/smoke/*.py.
# Holds no project id: the project is read from the active gcloud configuration
# file rather than from `gcloud config get-value`, because the CLI blocks on an
# interactive reauth prompt when its credential has expired and that would stall
# every script that only needs the project name.
_recall_config="${APPDATA}/gcloud/configurations/config_default"
RECALL_GCP_PROJECT="$(sed -n 's/^project *= *//p' "$_recall_config" 2>/dev/null | head -1)"
export RECALL_GCP_PROJECT
unset _recall_config
export RECALL_AGENT_ENGINE_LOCATION=us-central1
export RECALL_MODEL=gemini-3.7-flash
export RECALL_MODEL_LOCATION=global
export RECALL_STAGING_BUCKET=gs://recall-agent-engine-staging-68a6850a
export RECALL_PLATFORM_PYTHON="C:/Users/oacav/recall-platform-tooling/.venv/Scripts/python.exe"
