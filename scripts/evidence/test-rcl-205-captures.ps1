[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$verifierPath = Join-Path $PSScriptRoot 'verify-rcl-205-captures.ps1'
$manifestRelativePath = 'docs\evaluation\HISTORICAL_REPLAY_SOURCE_MANIFEST.json'
$captureRelativePath = 'artifacts\evidence\rcl-205'

if (-not (Test-Path -LiteralPath $verifierPath -PathType Leaf)) {
    throw 'verifier_missing: verify-rcl-205-captures.ps1 is required'
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("recall-rcl205-{0}" -f [guid]::NewGuid())))

if (-not $tempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "unsafe_temp_path: $tempRoot"
}

try {
    $tempManifest = Join-Path $tempRoot $manifestRelativePath
    $tempCaptureRoot = Join-Path $tempRoot $captureRelativePath

    New-Item -ItemType Directory -Force -Path (Split-Path $tempManifest -Parent) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $tempCaptureRoot -Parent) | Out-Null
    Copy-Item -LiteralPath (Join-Path $repositoryRoot $manifestRelativePath) -Destination $tempManifest
    Copy-Item -LiteralPath (Join-Path $repositoryRoot $captureRelativePath) -Destination $tempCaptureRoot -Recurse

    $cleanResult = & $verifierPath -RepositoryRoot $tempRoot -ManifestPath $manifestRelativePath
    if ($cleanResult.status -ne 'PASS' -or $cleanResult.verified_captures -ne 10) {
        throw 'clean_copy_failed: expected PASS with 10 verified captures'
    }

    $mutationTarget = Join-Path $tempRoot 'artifacts\evidence\rcl-205\pubmed\PMID39779848.esummary.json'
    $stream = [IO.File]::Open($mutationTarget, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $firstByte = $stream.ReadByte()
        if ($firstByte -lt 0) {
            throw 'mutation_target_empty'
        }
        $stream.Position = 0
        $stream.WriteByte($firstByte -bxor 1)
        $stream.Flush()
    }
    finally {
        $stream.Dispose()
    }

    $mutationRejected = $false
    try {
        $null = & $verifierPath -RepositoryRoot $tempRoot -ManifestPath $manifestRelativePath
    }
    catch {
        if ($_.Exception.Message -match 'hash_mismatch') {
            $mutationRejected = $true
        }
        else {
            throw
        }
    }

    if (-not $mutationRejected) {
        throw 'mutation_not_rejected: changed bytes passed verification'
    }

    $stream = [IO.File]::Open($mutationTarget, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.WriteByte($firstByte)
        $stream.Flush()
    }
    finally {
        $stream.Dispose()
    }

    $tempManifestObject = Get-Content -LiteralPath $tempManifest -Raw | ConvertFrom-Json
    $tempManifestObject.captured_sources[0].capture_path = 'artifacts/evidence/rcl-205/../escape.html'
    $tempManifestObject | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $tempManifest -Encoding UTF8

    $pathTraversalRejected = $false
    try {
        $null = & $verifierPath -RepositoryRoot $tempRoot -ManifestPath $manifestRelativePath
    }
    catch {
        if ($_.Exception.Message -match 'capture_path_outside_root') {
            $pathTraversalRejected = $true
        }
        else {
            throw
        }
    }

    if (-not $pathTraversalRejected) {
        throw 'path_traversal_not_rejected: capture escaped declared root'
    }

    [pscustomobject]@{
        status = 'PASS'
        clean_copy_verified = $true
        verified_captures = $cleanResult.verified_captures
        mutated_byte_rejected = $true
        path_traversal_rejected = $true
        network_calls = 0
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw "refuse_cleanup_outside_temp: $resolvedTempRoot"
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}
