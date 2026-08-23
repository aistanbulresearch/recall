# Apply the mandatory lane labels to an Agent Engine.
# `vertexai.agent_engines.create()` has no labels parameter in aiplatform 1.165, so
# labels are applied by a PATCH after create and then read back.
# Usage: .\infra\scripts\label_agent_engine.ps1 -ResourceName projects/.../reasoningEngines/123 -Component runtime-smoke
param(
    [Parameter(Mandatory = $true)][string]$ResourceName,
    [Parameter(Mandatory = $true)][string]$Component
)

$ErrorActionPreference = "Stop"

if ($ResourceName -notmatch '^projects/[^/]+/locations/([^/]+)/reasoningEngines/[^/]+$') {
    throw "runtime_resource_name_invalid"
}
$location = $Matches[1]
$token = (gcloud auth print-access-token)
if ($LASTEXITCODE -ne 0) { throw "auth_token_failed" }

$headers = @{ Authorization = "Bearer $token" }
$uri = "https://$location-aiplatform.googleapis.com/v1/$ResourceName"
$body = @{ labels = @{ lane = "l1"; component = $Component } } | ConvertTo-Json -Compress

Invoke-RestMethod -Method Patch -Uri "$uri`?updateMask=labels" -Headers $headers `
    -ContentType "application/json" -Body $body | Out-Null

Write-Output "read-back labels:"
$current = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
if (-not $current.labels.lane) { throw "runtime_label_read_back_missing" }
$current.labels | ConvertTo-Json -Compress
