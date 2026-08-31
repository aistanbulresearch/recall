# Read back every Agent Engine in one location. Absence is proven here, never by a
# delete call returning success.
# Usage: .\infra\scripts\list_agent_engines.ps1 [-Location us-central1]
param(
    [string]$Location = "us-central1",
    [string]$Project = $env:RECALL_GCP_PROJECT
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\gcloud_token.ps1"
# Read the project from the configuration file rather than asking gcloud:
# `config get-value project` is the call that hung, and it is on the
# milestone path. A call that never happens cannot hang.
if (-not $Project) { $Project = Get-RecallProject }
# Bounded: a bare print-access-token can wait forever on a reauth prompt
# that no one can answer in a non-interactive session.
$token = Get-RecallAccessToken

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
