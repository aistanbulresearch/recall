# Kill switch: delete one Agent Engine (reasoningEngine) by full resource name.
# gcloud has no `ai reasoning-engines` group in SDK 580, so this calls the REST API
# directly and needs no Python SDK.
# Usage: .\infra\scripts\delete_agent_engine.ps1 -ResourceName projects/.../locations/us-central1/reasoningEngines/123
param(
    [Parameter(Mandatory = $true)][string]$ResourceName,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if ($ResourceName -notmatch '^projects/[^/]+/locations/([^/]+)/reasoningEngines/[^/]+$') {
    throw "runtime_resource_name_invalid"
}
$location = $Matches[1]
. "$PSScriptRoot\gcloud_token.ps1"
# Bounded: a bare print-access-token can wait forever on a reauth prompt
# that no one can answer in a non-interactive session.
$token = Get-RecallAccessToken

$uri = "https://$location-aiplatform.googleapis.com/v1/$ResourceName"
if ($Force) { $uri = "$uri`?force=true" }

Write-Output "deleting $ResourceName"
Invoke-RestMethod -Method Delete -Uri $uri -Headers @{ Authorization = "Bearer $token" } | ConvertTo-Json -Depth 6

Write-Output "read-back after delete:"
& "$PSScriptRoot\list_agent_engines.ps1" -Location $location
