[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$verifierPath = Join-Path $PSScriptRoot 'verify-rcl-205-captures.ps1'
$manifestRelativePath = 'docs\evaluation\HISTORICAL_REPLAY_SOURCE_MANIFEST.json'
$captureRelativePath = 'artifacts\evidence\rcl-205'

function New-TestCase {
    param([string]$Name)

    $caseRoot = Join-Path $tempRoot $Name
    $caseManifest = Join-Path $caseRoot $manifestRelativePath
    $caseCaptureRoot = Join-Path $caseRoot $captureRelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $caseManifest -Parent) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $caseCaptureRoot -Parent) | Out-Null
    Copy-Item -LiteralPath (Join-Path $repositoryRoot $manifestRelativePath) -Destination $caseManifest
    Copy-Item -LiteralPath (Join-Path $repositoryRoot $captureRelativePath) -Destination $caseCaptureRoot -Recurse
    return $caseRoot
}

function Assert-Rejected {
    param(
        [string]$CaseRoot,
        [string]$ExpectedCode,
        [string]$ForbiddenCode = ''
    )

    try {
        $null = & $verifierPath -RepositoryRoot $CaseRoot -ManifestPath $manifestRelativePath
    }
    catch {
        $message = $_.Exception.Message
        if ($message -notmatch [regex]::Escape($ExpectedCode)) {
            throw "unexpected_rejection: expected=${ExpectedCode}:actual=${message}"
        }
        if (-not [string]::IsNullOrWhiteSpace($ForbiddenCode) -and
            $message -match [regex]::Escape($ForbiddenCode)) {
            throw "unsafe_processing_after_rejection: forbidden=${ForbiddenCode}:actual=${message}"
        }
        return
    }
    throw "expected_rejection_missing:$ExpectedCode"
}

function Update-CaptureIntegrity {
    param(
        [string]$CaseRoot,
        [string]$SourceId
    )

    $caseManifest = Join-Path $CaseRoot $manifestRelativePath
    $manifestObject = Get-Content -LiteralPath $caseManifest -Raw | ConvertFrom-Json
    $source = @($manifestObject.captured_sources | Where-Object { $_.source_id -eq $SourceId })
    if ($source.Count -ne 1) {
        throw "test_source_not_unique:$SourceId"
    }
    $capture = Join-Path $CaseRoot ([string]$source[0].capture_path)
    $source[0].bytes = (Get-Item -LiteralPath $capture).Length
    $source[0].sha256 = (Get-FileHash -LiteralPath $capture -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $caseManifest -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $verifierPath -PathType Leaf)) {
    throw 'verifier_missing: verify-rcl-205-captures.ps1 is required'
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("recall-rcl205-{0}" -f [guid]::NewGuid())))

if (-not $tempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "unsafe_temp_path: $tempRoot"
}

try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

    $cleanRoot = New-TestCase 'clean'
    $cleanResult = & $verifierPath -RepositoryRoot $cleanRoot -ManifestPath $manifestRelativePath
    $expectedSemanticCheckIds = @(
        'clinvar_v1_aggregate_vus',
        'clinvar_v4_aggregate_vus',
        'clinvar_v5_aggregate_conflicting',
        'clinvar_v5_ambry_citation',
        'clinvar_v5_ambry_submission',
        'geo_current_linked_pmid',
        'nature_excerpt_word_count',
        'nature_full_article_not_captured',
        'nature_geo_accession',
        'nature_publication_doi',
        'nature_publication_pmid',
        'sahu_publication_doi'
    ) | Sort-Object
    $expectedRightsCheckIds = @(
        'captured:clinvar_negative_missense',
        'captured:clinvar_negative_splice',
        'captured:clinvar_positive_v1',
        'captured:clinvar_positive_v4',
        'captured:clinvar_positive_v5',
        'captured:geo_gse248438_metadata',
        'captured:geo_gse248438_results_xlsx',
        'captured:huang_pubmed_esummary',
        'captured:nature_sahu_data_availability_linkage',
        'captured:sahu_pubmed_esummary',
        'live:clinvar_positive_current_xml'
    ) | Sort-Object
    $semanticSetDiff = @(Compare-Object $expectedSemanticCheckIds @($cleanResult.source_semantic_check_ids | Sort-Object))
    $rightsSetDiff = @(Compare-Object $expectedRightsCheckIds @($cleanResult.rights_metadata_check_ids | Sort-Object))
    $expectedLiveSpecCheckIds = @('live_spec:clinvar_positive_current_xml')
    $liveSpecSetDiff = @(Compare-Object $expectedLiveSpecCheckIds @($cleanResult.live_connector_spec_check_ids | Sort-Object))
    if ($cleanResult.status -ne 'PASS' -or
        $cleanResult.verified_captures -ne 10 -or
        $cleanResult.chronology_checks -ne 7 -or
        $cleanResult.source_semantic_checks -ne 12 -or
        $cleanResult.rights_metadata_checks -ne 11 -or
        $cleanResult.live_connector_spec_checks -ne 1 -or
        $cleanResult.live_public_sources -ne 1 -or
        $semanticSetDiff.Count -ne 0 -or
        $rightsSetDiff.Count -ne 0 -or
        $liveSpecSetDiff.Count -ne 0 -or
        $cleanResult.exact_xlsx_rows -ne 1) {
        throw 'clean_copy_failed: expected exact capture, chronology, semantic, rights, and row check sets'
    }

    $byteRoot = New-TestCase 'byte-mutation'
    $mutationTarget = Join-Path $byteRoot 'artifacts\evidence\rcl-205\pubmed\PMID39779848.esummary.json'
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

    Assert-Rejected $byteRoot 'hash_mismatch'

    $traversalRoot = New-TestCase 'capture-traversal'
    $traversalManifest = Join-Path $traversalRoot $manifestRelativePath
    $traversalObject = Get-Content -LiteralPath $traversalManifest -Raw | ConvertFrom-Json
    $traversalObject.captured_sources[0].capture_path = 'artifacts/evidence/rcl-205/../escape.html'
    $traversalObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $traversalManifest -Encoding UTF8
    Assert-Rejected $traversalRoot 'capture_path_outside_root'

    $absoluteRoot = New-TestCase 'absolute-root'
    $absoluteManifest = Join-Path $absoluteRoot $manifestRelativePath
    $absoluteObject = Get-Content -LiteralPath $absoluteManifest -Raw | ConvertFrom-Json
    $absoluteObject.capture_root = Join-Path $absoluteRoot $captureRelativePath
    $absoluteObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $absoluteManifest -Encoding UTF8
    Assert-Rejected $absoluteRoot 'capture_root_absolute' 'hash_mismatch'

    $parentRoot = New-TestCase 'parent-root'
    $parentManifest = Join-Path $parentRoot $manifestRelativePath
    $parentObject = Get-Content -LiteralPath $parentManifest -Raw | ConvertFrom-Json
    $parentObject.capture_root = '..'
    $parentObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $parentManifest -Encoding UTF8
    Assert-Rejected $parentRoot 'capture_root_outside_repository' 'capture_missing'

    $clinvarRoot = New-TestCase 'clinvar-semantic'
    $clinvarCapture = Join-Path $clinvarRoot 'artifacts\evidence\rcl-205\clinvar\VCV002895953.5.printable.html'
    $clinvarText = Get-Content -LiteralPath $clinvarCapture -Raw
    $clinvarText = $clinvarText.Replace('39779848', '39779857')
    Set-Content -LiteralPath $clinvarCapture -Value $clinvarText -Encoding UTF8 -NoNewline
    Update-CaptureIntegrity $clinvarRoot 'clinvar_positive_v5'
    Assert-Rejected $clinvarRoot 'clinvar_cited_pmid_mismatch'

    $natureRoot = New-TestCase 'nature-word-count'
    $natureCapture = Join-Path $natureRoot 'artifacts\evidence\rcl-205\nature\PMID39779848.data-availability-linkage.json'
    $natureObject = Get-Content -LiteralPath $natureCapture -Raw | ConvertFrom-Json
    $natureObject.verbatim_excerpt = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive twentysix'
    $natureObject | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $natureCapture -Encoding UTF8
    Update-CaptureIntegrity $natureRoot 'nature_sahu_data_availability_linkage'
    Assert-Rejected $natureRoot 'nature_excerpt_word_count_mismatch'

    $rightsRoot = New-TestCase 'rights-profile'
    $rightsManifest = Join-Path $rightsRoot $manifestRelativePath
    $rightsObject = Get-Content -LiteralPath $rightsManifest -Raw | ConvertFrom-Json
    $rightsObject.captured_sources[0].rights_profile = 'missing_profile'
    $rightsObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $rightsManifest -Encoding UTF8
    Assert-Rejected $rightsRoot 'rights_profile_invalid'

    $liveRightsRoot = New-TestCase 'live-rights-profile'
    $liveRightsManifest = Join-Path $liveRightsRoot $manifestRelativePath
    $liveRightsObject = Get-Content -LiteralPath $liveRightsManifest -Raw | ConvertFrom-Json
    $liveRightsObject.live_public_sources[0].rights_profile = 'missing_profile'
    $liveRightsObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $liveRightsManifest -Encoding UTF8
    Assert-Rejected $liveRightsRoot 'rights_profile_invalid'

    $liveRuleRoot = New-TestCase 'live-runtime-rule'
    $liveRuleManifest = Join-Path $liveRuleRoot $manifestRelativePath
    $liveRuleObject = Get-Content -LiteralPath $liveRuleManifest -Raw | ConvertFrom-Json
    $liveRuleObject.live_public_sources[0].integrity_rule = ''
    $liveRuleObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $liveRuleManifest -Encoding UTF8
    Assert-Rejected $liveRuleRoot 'live_integrity_rule_invalid'

    $liveDuplicateRoot = New-TestCase 'live-duplicate'
    $liveDuplicateManifest = Join-Path $liveDuplicateRoot $manifestRelativePath
    $liveDuplicateObject = Get-Content -LiteralPath $liveDuplicateManifest -Raw | ConvertFrom-Json
    $duplicateLiveSource = $liveDuplicateObject.live_public_sources[0] | ConvertTo-Json -Depth 20 | ConvertFrom-Json
    $liveDuplicateObject.live_public_sources = @($liveDuplicateObject.live_public_sources[0], $duplicateLiveSource)
    $liveDuplicateObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $liveDuplicateManifest -Encoding UTF8
    Assert-Rejected $liveDuplicateRoot 'source_id_duplicate'

    $hashRoleRoot = New-TestCase 'hash-role'
    $hashRoleManifest = Join-Path $hashRoleRoot $manifestRelativePath
    $hashRoleObject = Get-Content -LiteralPath $hashRoleManifest -Raw | ConvertFrom-Json
    $hashRoleObject.captured_sources[0].raw_sha256 = ('0' * 64)
    $hashRoleObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $hashRoleManifest -Encoding UTF8
    Assert-Rejected $hashRoleRoot 'capture_hash_role_mismatch'

    $junctionRoot = New-TestCase 'junction-escape'
    $junctionPubmed = Join-Path $junctionRoot 'artifacts\evidence\rcl-205\pubmed'
    $outsidePubmed = Join-Path $tempRoot 'junction-outside-pubmed'
    Copy-Item -LiteralPath $junctionPubmed -Destination $outsidePubmed -Recurse
    Remove-Item -LiteralPath $junctionPubmed -Recurse -Force
    $junction = New-Item -ItemType Junction -Path $junctionPubmed -Target $outsidePubmed
    if ($null -eq $junction -or -not ($junction.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'junction_test_setup_failed'
    }
    Assert-Rejected $junctionRoot 'capture_path_reparse_point' 'hash_mismatch'

    [pscustomobject]@{
        status = 'PASS'
        clean_copy_verified = $true
        verified_captures = $cleanResult.verified_captures
        mutated_byte_rejected = $true
        path_traversal_rejected = $true
        absolute_capture_root_rejected = $true
        parent_capture_root_rejected = $true
        clinvar_semantic_mutation_rejected = $true
        nature_word_count_mutation_rejected = $true
        rights_profile_mutation_rejected = $true
        live_rights_profile_mutation_rejected = $true
        live_runtime_rule_mutation_rejected = $true
        live_duplicate_rejected = $true
        hash_role_mutation_rejected = $true
        junction_escape_rejected = $true
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
