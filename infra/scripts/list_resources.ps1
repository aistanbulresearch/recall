# Read back every lane L1 cloud resource. Run before and after any smoke test so the
# inventory in infra\resources.json can be reconciled against reality.
# Usage: .\infra\scripts\list_resources.ps1 [-Location us-central1]
param(
    [string]$Location = "us-central1"
)

$ErrorActionPreference = "Continue"

Write-Output "== storage buckets (lane=l1) =="
gcloud storage buckets list --format="value(name,location,labels)" --filter="labels.lane=l1"

Write-Output ""
Write-Output "== service accounts (recall- prefix) =="
gcloud iam service-accounts list --format="value(email,displayName)" --filter="email:recall-*"

Write-Output ""
Write-Output "== agent engines ($Location) =="
& "$PSScriptRoot\list_agent_engines.ps1" -Location $Location

Write-Output ""
Write-Output "== model armor templates ($Location) =="
gcloud model-armor templates list --location=$Location --format="value(name)" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Output "model armor: listing unavailable through gcloud in this SDK build" }
