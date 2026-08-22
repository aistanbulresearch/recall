# Lane L1 smoke environment. Source before running infra/smoke/*.py.
# Holds no project id: the project comes from the active gcloud configuration.
export RECALL_GCP_PROJECT="$(gcloud config get-value project 2>/dev/null)"
export RECALL_AGENT_ENGINE_LOCATION=us-central1
export RECALL_MODEL=gemini-3.7-flash
export RECALL_MODEL_LOCATION=global
export RECALL_STAGING_BUCKET=gs://recall-agent-engine-staging-68a6850a
export RECALL_PLATFORM_PYTHON="C:/Users/oacav/recall-platform-tooling/.venv/Scripts/python.exe"
