[CmdletBinding()]
param(
    [string]$RepositoryRoot = '',
    [string]$ManifestPath = 'docs\evaluation\HISTORICAL_REPLAY_SOURCE_MANIFEST.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$failures = [Collections.Generic.List[string]]::new()
$allowedHosts = @(
    'www.ncbi.nlm.nih.gov',
    'eutils.ncbi.nlm.nih.gov',
    'www.nature.com'
)

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path $PSScriptRoot '..\..'
}

function Add-Failure {
    param(
        [string]$Code,
        [string]$Detail
    )

    $failures.Add("${Code}:$Detail")
}

function Test-IsWithin {
    param(
        [string]$Candidate,
        [string]$Parent
    )

    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    return $candidateFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)
}

function Get-RequiredProperty {
    param(
        [object]$Object,
        [string]$Name,
        [string]$Context
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        Add-Failure 'required_field_missing' "${Context}.${Name}"
        return $null
    }
    return $property.Value
}

function Convert-Date {
    param(
        [string]$Value,
        [string]$Format,
        [string]$Context
    )

    try {
        return [DateTime]::ParseExact(
            $Value,
            $Format,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::None
        )
    }
    catch {
        Add-Failure 'date_invalid' "${Context}:${Value}"
        return $null
    }
}

function Get-SoftValue {
    param(
        [string]$Text,
        [string]$Field
    )

    $match = [regex]::Match($Text, "(?m)^!${Field} = (?<value>.+?)\r?$")
    if (-not $match.Success) {
        Add-Failure 'soft_field_missing' $Field
        return $null
    }
    return $match.Groups['value'].Value.Trim()
}

$repositoryFull = [IO.Path]::GetFullPath($RepositoryRoot)
if (-not (Test-Path -LiteralPath $repositoryFull -PathType Container)) {
    throw "repository_missing:$repositoryFull"
}

$manifestFull = if ([IO.Path]::IsPathRooted($ManifestPath)) {
    [IO.Path]::GetFullPath($ManifestPath)
}
else {
    [IO.Path]::GetFullPath((Join-Path $repositoryFull $ManifestPath))
}

if (-not (Test-IsWithin $manifestFull $repositoryFull)) {
    throw "manifest_outside_repository:$manifestFull"
}
if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
    throw "manifest_missing:$manifestFull"
}

try {
    $manifest = Get-Content -LiteralPath $manifestFull -Raw | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "manifest_invalid_json:$($_.Exception.Message)"
}

if ($manifest.manifest_version -ne '1.0.1') {
    Add-Failure 'manifest_version_invalid' ([string]$manifest.manifest_version)
}
if ($manifest.integrity.algorithm -ne 'SHA-256') {
    Add-Failure 'hash_algorithm_invalid' ([string]$manifest.integrity.algorithm)
}

$captureRootText = [string]$manifest.capture_root
if ([IO.Path]::IsPathRooted($captureRootText)) {
    Add-Failure 'capture_root_absolute' $captureRootText
    $captureRootFull = [IO.Path]::GetFullPath($captureRootText)
}
else {
    $captureRootFull = [IO.Path]::GetFullPath((Join-Path $repositoryFull $captureRootText))
}
if (-not (Test-IsWithin $captureRootFull $repositoryFull)) {
    Add-Failure 'capture_root_outside_repository' $captureRootFull
}

$sourceIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$captureFiles = @{}
$verifiedBytes = [int64]0

foreach ($source in @($manifest.captured_sources)) {
    $sourceId = [string](Get-RequiredProperty $source 'source_id' 'captured_sources')
    if ([string]::IsNullOrWhiteSpace($sourceId)) {
        Add-Failure 'source_id_invalid' 'empty'
        continue
    }
    if (-not $sourceIds.Add($sourceId)) {
        Add-Failure 'source_id_duplicate' $sourceId
    }
    if ($source.data_mode -ne 'CAPTURED_REPLAY') {
        Add-Failure 'data_mode_invalid' $sourceId
    }

    $capturePath = [string](Get-RequiredProperty $source 'capture_path' $sourceId)
    if ([IO.Path]::IsPathRooted($capturePath)) {
        Add-Failure 'capture_path_absolute' $sourceId
        continue
    }

    $captureFull = [IO.Path]::GetFullPath((Join-Path $repositoryFull $capturePath))
    if (-not (Test-IsWithin $captureFull $captureRootFull)) {
        Add-Failure 'capture_path_outside_root' $sourceId
        continue
    }
    if (-not (Test-Path -LiteralPath $captureFull -PathType Leaf)) {
        Add-Failure 'capture_missing' $sourceId
        continue
    }

    $file = Get-Item -LiteralPath $captureFull
    $captureValid = $true
    $expectedBytes = [int64](Get-RequiredProperty $source 'bytes' $sourceId)
    if ($file.Length -ne $expectedBytes) {
        Add-Failure 'byte_count_mismatch' "${sourceId}:expected=${expectedBytes}:actual=$($file.Length)"
        $captureValid = $false
    }

    $expectedHash = [string](Get-RequiredProperty $source 'sha256' $sourceId)
    if ($expectedHash -notmatch '^[0-9a-f]{64}$') {
        Add-Failure 'hash_format_invalid' $sourceId
        $captureValid = $false
    }
    $actualHash = (Get-FileHash -LiteralPath $captureFull -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $expectedHash) {
        Add-Failure 'hash_mismatch' "${sourceId}:expected=${expectedHash}:actual=${actualHash}"
        $captureValid = $false
    }

    $retrievedAtText = [string](Get-RequiredProperty $source 'retrieved_at' $sourceId)
    $retrievedAt = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse($retrievedAtText, [ref]$retrievedAt) -or $retrievedAt.Offset -ne [TimeSpan]::Zero) {
        Add-Failure 'retrieved_at_invalid' $sourceId
    }

    $locatorText = [string](Get-RequiredProperty $source 'source_locator' $sourceId)
    $locator = $null
    if (-not [Uri]::TryCreate($locatorText, [UriKind]::Absolute, [ref]$locator) -or
        $locator.Scheme -ne 'https' -or $locator.Host -notin $allowedHosts) {
        Add-Failure 'source_locator_invalid' $sourceId
    }

    foreach ($requiredTextField in @('semantic_anchor', 'media_type', 'transformation', 'redistribution_boundary')) {
        $value = [string](Get-RequiredProperty $source $requiredTextField $sourceId)
        if ([string]::IsNullOrWhiteSpace($value)) {
            Add-Failure 'required_text_empty' "${sourceId}.${requiredTextField}"
        }
    }

    if ($source.media_type -eq 'text/html') {
        $html = Get-Content -LiteralPath $captureFull -Raw
        if (-not $html.Contains([string]$source.semantic_anchor)) {
            Add-Failure 'semantic_anchor_missing' $sourceId
        }
    }

    if ($captureValid) {
        $captureFiles[$sourceId] = $captureFull
        $verifiedBytes += $file.Length
    }
}

$expectedCaptureCount = [int]$manifest.integrity.expected_capture_count
if (@($manifest.captured_sources).Count -ne $expectedCaptureCount) {
    Add-Failure 'capture_count_mismatch' "expected=${expectedCaptureCount}:manifest=$(@($manifest.captured_sources).Count)"
}

foreach ($source in @($manifest.live_public_sources)) {
    if ($source.data_mode -ne 'LIVE_PUBLIC') {
        Add-Failure 'live_data_mode_invalid' ([string]$source.source_id)
    }
    if ($null -ne $source.capture_path -or $null -ne $source.expected_sha256) {
        Add-Failure 'live_source_frozen' ([string]$source.source_id)
    }
}

if ($captureFiles.ContainsKey('geo_gse248438_metadata')) {
    $soft = Get-Content -LiteralPath $captureFiles['geo_gse248438_metadata'] -Raw
    $geoStatus = Get-SoftValue $soft 'Series_status'
    $geoSubmission = Get-SoftValue $soft 'Series_submission_date'
    $geoLastUpdate = Get-SoftValue $soft 'Series_last_update_date'
    $geoPmid = Get-SoftValue $soft 'Series_pubmed_id'

    if ($null -ne $geoStatus -and $geoStatus.StartsWith('Public on ')) {
        $geoPublicDate = Convert-Date $geoStatus.Substring(10) 'MMM d yyyy' 'geo_public_date'
        if ($null -ne $geoPublicDate -and $geoPublicDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.geo_public_date) {
            Add-Failure 'chronology_mismatch' 'geo_public_date'
        }
    }
    else {
        Add-Failure 'geo_status_invalid' ([string]$geoStatus)
    }

    $geoSubmissionDate = Convert-Date $geoSubmission 'MMM d yyyy' 'geo_submission_date'
    $geoLastUpdateDate = Convert-Date $geoLastUpdate 'MMM d yyyy' 'geo_last_update_date'
    if ($null -ne $geoSubmissionDate -and $geoSubmissionDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.geo_submission_date) {
        Add-Failure 'chronology_mismatch' 'geo_submission_date'
    }
    if ($null -ne $geoLastUpdateDate -and $geoLastUpdateDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.geo_last_update_date_as_captured) {
        Add-Failure 'chronology_mismatch' 'geo_last_update_date_as_captured'
    }
    if ($geoPmid -ne $manifest.chronology.geo_current_linked_pmid_as_captured) {
        Add-Failure 'chronology_mismatch' 'geo_current_linked_pmid_as_captured'
    }
}

if ($captureFiles.ContainsKey('sahu_pubmed_esummary')) {
    $pubmed = Get-Content -LiteralPath $captureFiles['sahu_pubmed_esummary'] -Raw | ConvertFrom-Json
    $record = $pubmed.result.PSObject.Properties['39779848'].Value
    $publicationDate = Convert-Date ([string]$record.epubdate) 'yyyy MMM d' 'qualifying_publication_date'
    if ($null -ne $publicationDate -and $publicationDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.qualifying_publication_date) {
        Add-Failure 'chronology_mismatch' 'qualifying_publication_date'
    }
    if ($record.elocationid -ne 'doi: 10.1038/s41586-024-08349-1') {
        Add-Failure 'publication_doi_mismatch' '39779848'
    }
}

if ($captureFiles.ContainsKey('nature_sahu_data_availability_linkage')) {
    $linkage = Get-Content -LiteralPath $captureFiles['nature_sahu_data_availability_linkage'] -Raw | ConvertFrom-Json
    if ($linkage.pmid -ne $manifest.chronology.qualifying_nature_pmid -or
        $linkage.doi -ne '10.1038/s41586-024-08349-1' -or
        $linkage.geo_accession -ne 'GSE248438' -or
        $linkage.full_article_captured -ne $false -or
        $linkage.excerpt_word_count -gt 25) {
        Add-Failure 'publication_geo_linkage_invalid' 'nature_sahu_data_availability_linkage'
    }
}

if ($captureFiles.ContainsKey('geo_gse248438_results_xlsx')) {
    $xlsxPath = $captureFiles['geo_gse248438_results_xlsx']
    $xlsxBytes = [IO.File]::ReadAllBytes($xlsxPath)
    if ($xlsxBytes.Length -lt 2 -or $xlsxBytes[0] -ne 0x50 -or $xlsxBytes[1] -ne 0x4b) {
        Add-Failure 'xlsx_signature_invalid' 'geo_gse248438_results_xlsx'
    }
    if ($manifest.exact_functional_row.source_id -ne 'geo_gse248438_results_xlsx' -or
        -not ([string]$manifest.exact_functional_row.status).StartsWith('AS_CAPTURED_')) {
        Add-Failure 'exact_row_boundary_invalid' 'exact_functional_row'
    }

    try {
        $rowReader = Join-Path $PSScriptRoot 'read-rcl-205-xlsx-row.ps1'
        $actualRow = & $rowReader `
            -XlsxPath $xlsxPath `
            -AminoAcidChange $manifest.exact_functional_row.amino_acid_change `
            -TranscriptHgvs $manifest.exact_functional_row.transcript_hgvs `
            -GenomicHgvs $manifest.exact_functional_row.genomic_hgvs

        foreach ($field in @(
            'exon',
            'codon_change',
            'nucleotide_change',
            'amino_acid_change',
            'transcript_hgvs',
            'genomic_hgvs',
            'source_classification'
        )) {
            if ([string]$actualRow.$field -cne [string]$manifest.exact_functional_row.$field) {
                Add-Failure 'exact_row_value_mismatch' $field
            }
        }

        $actualScore = [double]::Parse(
            [string]$actualRow.function_score,
            [Globalization.CultureInfo]::InvariantCulture
        )
        $actualProbability = [double]::Parse(
            [string]$actualRow.probability,
            [Globalization.CultureInfo]::InvariantCulture
        )
        if ($actualScore -ne [double]$manifest.exact_functional_row.function_score) {
            Add-Failure 'exact_row_value_mismatch' 'function_score'
        }
        if ($actualProbability -ne [double]$manifest.exact_functional_row.probability) {
            Add-Failure 'exact_row_value_mismatch' 'probability'
        }
    }
    catch {
        Add-Failure 'xlsx_parse_failed' $_.Exception.Message
    }
}

$publication = Convert-Date $manifest.positive_case.qualifying_publication_date 'yyyy-MM-dd' 'positive_case_publication'
$evaluator = Convert-Date $manifest.positive_case.later_evaluator_date 'yyyy-MM-dd' 'later_evaluator'
$appearance = Convert-Date $manifest.positive_case.later_public_classification_appearance 'yyyy-MM-dd' 'later_public_appearance'
if ($null -ne $publication -and $null -ne $evaluator -and
    ($evaluator - $publication).Days -ne [int]$manifest.positive_case.derived_days_to_evaluator_date) {
    Add-Failure 'derived_interval_mismatch' 'derived_days_to_evaluator_date'
}
if ($null -ne $publication -and $null -ne $appearance -and
    ($appearance - $publication).Days -ne [int]$manifest.positive_case.derived_days_to_public_appearance) {
    Add-Failure 'derived_interval_mismatch' 'derived_days_to_public_appearance'
}

if ($failures.Count -gt 0) {
    throw [IO.InvalidDataException]::new("verification_failed: $($failures -join '; ')")
}

[pscustomobject]@{
    status = 'PASS'
    manifest_version = $manifest.manifest_version
    verified_captures = @($manifest.captured_sources).Count
    verified_bytes = $verifiedBytes
    chronology_checks = 7
    exact_xlsx_rows = 1
    live_public_sources = @($manifest.live_public_sources).Count
    network_calls = 0
}
