# Kill switch: remove the Agent Engine staging bucket and its contents.
# Usage: .\infra\scripts\delete_staging_bucket.ps1 -Suffix a1b2c3d4
param(
    [Parameter(Mandatory = $true)][string]$Suffix
)

$ErrorActionPreference = "Stop"

$bucket = "recall-agent-engine-staging-$Suffix"
Write-Output "deleting gs://$bucket"

gcloud storage rm --recursive "gs://$bucket"
if ($LASTEXITCODE -ne 0) { throw "bucket_delete_failed" }

Write-Output "read-back after delete (expect NOT_FOUND):"
gcloud storage buckets describe "gs://$bucket" --format="value(name)"
