# Create the labelled Agent Engine staging bucket for lane L1.
# Usage: .\infra\scripts\create_staging_bucket.ps1 -Suffix a1b2c3d4
param(
    [Parameter(Mandatory = $true)][string]$Suffix,
    [string]$Location = "us-central1"
)

$ErrorActionPreference = "Stop"

$bucket = "recall-agent-engine-staging-$Suffix"
Write-Output "creating gs://$bucket in $Location"

gcloud storage buckets create "gs://$bucket" `
    --location=$Location `
    --uniform-bucket-level-access `
    --public-access-prevention
if ($LASTEXITCODE -ne 0) { throw "bucket_create_failed" }

# Quote the label list: an unquoted comma makes PowerShell pass an array, which
# gcloud receives as one space-joined label value and rejects.
gcloud storage buckets update "gs://$bucket" "--update-labels=lane=l1,component=agent-engine-staging"
if ($LASTEXITCODE -ne 0) { throw "bucket_label_failed" }

Write-Output "read-back:"
gcloud storage buckets describe "gs://$bucket" --format="value(name,location,labels)"
if ($LASTEXITCODE -ne 0) { throw "bucket_read_back_failed" }
