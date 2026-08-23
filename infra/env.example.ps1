# Copy to infra\env.local.ps1, fill in, and dot-source it. env.local.ps1 is git-ignored.
# Never commit a project id, billing id, account address, or token value.

$env:RECALL_GCP_PROJECT           = "<project>"
$env:RECALL_AGENT_ENGINE_LOCATION = "us-central1"
$env:RECALL_MODEL                 = "gemini-3.7-flash"
$env:RECALL_MODEL_LOCATION        = "global"
$env:RECALL_STAGING_BUCKET        = "gs://recall-agent-engine-staging-<suffix>"

# Interpreter that carries the Vertex AI Agent Engine SDK. pyproject.toml belongs
# to lane L2, so this lane keeps the SDK outside the project dependency set.
$env:RECALL_PLATFORM_PYTHON       = "C:\Users\<user>\recall-platform-tooling\.venv\Scripts\python.exe"
