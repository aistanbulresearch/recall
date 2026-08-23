# Read back every Agent Engine in one location. Absence is proven here, never by a
# delete call returning success.
# Usage: .\infra\scripts\list_agent_engines.ps1 [-Location us-central1]
param(
    [string]$Location = "us-central1",
    [string]$Project = $env:RECALL_GCP_PROJECT
)

$ErrorActionPreference = "Stop"

if (-not $Project) { $Project = (gcloud config get-value project 2>$null) }
if (-not $Project) { throw "platform_config_missing:RECALL_GCP_PROJECT" }

$token = (gcloud auth print-access-token)
if ($LASTEXITCODE -ne 0) { throw "auth_token_failed" }

$uri = "https://$Location-aiplatform.googleapis.com/v1/projects/$Project/locations/$Location/reasoningEngines"
$response = Invoke-RestMethod -Method Get -Uri $uri -Headers @{ Authorization = "Bearer $token" }

if (-not $response.reasoningEngines) {
    Write-Output "reasoningEngines: none in $Location"
    return
}
$response.reasoningEngines | ForEach-Object {
    [pscustomobject]@{
        name        = $_.name
        displayName = $_.displayName
        updateTime  = $_.updateTime
    }
} | Format-Table -AutoSize
