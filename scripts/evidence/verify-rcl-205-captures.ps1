[CmdletBinding()]
param(
    [string]$RepositoryRoot = '',
    [string]$ManifestPath = 'docs\evaluation\HISTORICAL_REPLAY_SOURCE_MANIFEST.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$failures = [Collections.Generic.List[string]]::new()
$chronologyChecks = 0
$sourceSemanticCheckIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$rightsMetadataCheckIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$liveConnectorSpecCheckIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$exactXlsxRows = 0
$publicationDateFromSource = $null
$evaluatorDateFromSource = $null
$appearanceDateFromSource = $null
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

function Test-PathHasReparsePoint {
    param(
        [string]$Candidate,
        [string]$Boundary
    )

    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    $boundaryFull = [IO.Path]::GetFullPath($Boundary).TrimEnd('\', '/')
    $current = $candidateFull
    while ($current.Length -ge $boundaryFull.Length) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                $linkTypeProperty = $item.PSObject.Properties['LinkType']
                $targetProperty = $item.PSObject.Properties['Target']
                $linkType = if ($null -eq $linkTypeProperty) { '' } else { [string]$linkTypeProperty.Value }
                $target = if ($null -eq $targetProperty) { '' } else { [string]($targetProperty.Value -join ',') }
                if (-not [string]::IsNullOrWhiteSpace($linkType) -or
                    -not [string]::IsNullOrWhiteSpace($target)) {
                    return $true
                }
            }
        }
        if ($current.Equals($boundaryFull, [StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
    return $false
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

function Test-RightsBinding {
    param(
        [object]$Source,
        [string]$Context
    )

    $valid = $true
    $rightsProfileId = [string](Get-RequiredProperty $Source 'rights_profile' $Context)
    $profileProperty = $manifest.rights_profiles.PSObject.Properties[$rightsProfileId]
    if ([string]::IsNullOrWhiteSpace($rightsProfileId) -or $null -eq $profileProperty) {
        Add-Failure 'rights_profile_invalid' $Context
        $valid = $false
    }
    else {
        $rightsProfile = $profileProperty.Value
        $termsText = [string](Get-RequiredProperty $rightsProfile 'terms_url' $rightsProfileId)
        $termsUri = $null
        if (-not [Uri]::TryCreate($termsText, [UriKind]::Absolute, [ref]$termsUri) -or
            $termsUri.Scheme -ne 'https' -or $termsUri.Host -notin $allowedHosts) {
            Add-Failure 'rights_terms_url_invalid' $rightsProfileId
            $valid = $false
        }
        $rightsReviewDate = Convert-Date ([string](Get-RequiredProperty $rightsProfile 'terms_reviewed_at' $rightsProfileId)) 'yyyy-MM-dd' "${rightsProfileId}.terms_reviewed_at"
        if ($null -eq $rightsReviewDate) {
            $valid = $false
        }
        foreach ($permissionField in @('retention_permission', 'redistribution_permission', 'conditions')) {
            $permissionValue = [string](Get-RequiredProperty $rightsProfile $permissionField $rightsProfileId)
            if ([string]::IsNullOrWhiteSpace($permissionValue)) {
                Add-Failure 'rights_field_empty' "${rightsProfileId}.${permissionField}"
                $valid = $false
            }
        }
    }
    foreach ($sourceRightsField in @('known_rights_limitations', 'attribution_text')) {
        $sourceRightsValue = [string](Get-RequiredProperty $Source $sourceRightsField $Context)
        if ([string]::IsNullOrWhiteSpace($sourceRightsValue)) {
            Add-Failure 'rights_field_empty' "${Context}.${sourceRightsField}"
            $valid = $false
        }
    }
    return $valid
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
    throw [IO.InvalidDataException]::new("capture_root_absolute:$captureRootText")
}
$captureRootFull = [IO.Path]::GetFullPath((Join-Path $repositoryFull $captureRootText))
if (-not (Test-IsWithin $captureRootFull $repositoryFull)) {
    throw [IO.InvalidDataException]::new("capture_root_outside_repository:$captureRootFull")
}
if (-not (Test-Path -LiteralPath $captureRootFull -PathType Container)) {
    throw [IO.InvalidDataException]::new("capture_root_missing:$captureRootFull")
}
if (Test-PathHasReparsePoint $captureRootFull $repositoryFull) {
    throw [IO.InvalidDataException]::new("capture_root_reparse_point:$captureRootFull")
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
    if (-not (Test-IsWithin $captureFull $repositoryFull) -or
        -not (Test-IsWithin $captureFull $captureRootFull)) {
        Add-Failure 'capture_path_outside_root' $sourceId
        continue
    }
    if (Test-PathHasReparsePoint $captureFull $captureRootFull) {
        Add-Failure 'capture_path_reparse_point' $sourceId
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

    $rawHash = Get-RequiredProperty $source 'raw_sha256' $sourceId
    $normalizedHash = Get-RequiredProperty $source 'normalized_sha256' $sourceId
    if ($source.transformation -eq 'NONE') {
        if ([string]$rawHash -cne $expectedHash -or $null -ne $normalizedHash) {
            Add-Failure 'capture_hash_role_mismatch' "${sourceId}:expected_raw_capture"
        }
    }
    elseif ($null -ne $rawHash -or [string]$normalizedHash -cne $expectedHash) {
        Add-Failure 'capture_hash_role_mismatch' "${sourceId}:expected_normalized_capture"
    }

    if (Test-RightsBinding $source $sourceId) {
        $null = $rightsMetadataCheckIds.Add("captured:$sourceId")
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
    $sourceId = [string](Get-RequiredProperty $source 'source_id' 'live_public_sources')
    $liveSpecValid = $true
    if ([string]::IsNullOrWhiteSpace($sourceId)) {
        Add-Failure 'source_id_invalid' 'live_public_sources.empty'
        continue
    }
    if (-not $sourceIds.Add($sourceId)) {
        Add-Failure 'source_id_duplicate' "live:$sourceId"
        $liveSpecValid = $false
    }
    if ($source.data_mode -ne 'LIVE_PUBLIC') {
        Add-Failure 'live_data_mode_invalid' $sourceId
        $liveSpecValid = $false
    }
    if ($null -ne $source.capture_path -or $null -ne $source.expected_sha256) {
        Add-Failure 'live_source_frozen' $sourceId
        $liveSpecValid = $false
    }
    $liveRawHash = Get-RequiredProperty $source 'raw_sha256' $sourceId
    $liveNormalizedHash = Get-RequiredProperty $source 'normalized_sha256' $sourceId
    if ($null -ne $liveRawHash -or $null -ne $liveNormalizedHash) {
        Add-Failure 'live_source_frozen' "${sourceId}:byte_roles"
        $liveSpecValid = $false
    }
    if ($source.execution_status -ne 'UNEXECUTED_CONNECTOR_SPEC') {
        Add-Failure 'live_execution_status_invalid' $sourceId
        $liveSpecValid = $false
    }
    $liveLocatorText = [string](Get-RequiredProperty $source 'source_locator' $sourceId)
    $liveLocator = $null
    if (-not [Uri]::TryCreate($liveLocatorText, [UriKind]::Absolute, [ref]$liveLocator) -or
        $liveLocator.Scheme -ne 'https' -or $liveLocator.Host -notin $allowedHosts) {
        Add-Failure 'live_source_locator_invalid' $sourceId
        $liveSpecValid = $false
    }
    $liveSemanticAnchor = [string](Get-RequiredProperty $source 'semantic_anchor' $sourceId)
    if ([string]::IsNullOrWhiteSpace($liveSemanticAnchor)) {
        Add-Failure 'live_semantic_anchor_invalid' $sourceId
        $liveSpecValid = $false
    }
    $liveIntegrityRule = [string](Get-RequiredProperty $source 'integrity_rule' $sourceId)
    if ([string]::IsNullOrWhiteSpace($liveIntegrityRule)) {
        Add-Failure 'live_integrity_rule_invalid' $sourceId
        $liveSpecValid = $false
    }
    $runtimeContract = Get-RequiredProperty $source 'runtime_provenance_contract' $sourceId
    if ($null -eq $runtimeContract) {
        Add-Failure 'live_runtime_contract_invalid' $sourceId
        $liveSpecValid = $false
    }
    else {
        $requiredRuntimeFields = @(Get-RequiredProperty $runtimeContract 'required_fields' "${sourceId}.runtime_provenance_contract" | Sort-Object)
        $runtimeHashAlgorithm = [string](Get-RequiredProperty $runtimeContract 'hash_algorithm' "${sourceId}.runtime_provenance_contract")
        $runtimeDataMode = [string](Get-RequiredProperty $runtimeContract 'data_mode' "${sourceId}.runtime_provenance_contract")
        $runtimeComparison = [string](Get-RequiredProperty $runtimeContract 'captured_replay_hash_comparison' "${sourceId}.runtime_provenance_contract")
        $expectedRuntimeFields = @('data_mode', 'raw_sha256', 'retrieved_at', 'semantic_anchor', 'source_locator') | Sort-Object
        if (@(Compare-Object $expectedRuntimeFields $requiredRuntimeFields).Count -ne 0 -or
            $runtimeHashAlgorithm -ne 'SHA-256' -or
            $runtimeDataMode -ne 'LIVE_PUBLIC' -or
            $runtimeComparison -ne 'FORBIDDEN') {
            Add-Failure 'live_runtime_contract_invalid' $sourceId
            $liveSpecValid = $false
        }
    }
    if (Test-RightsBinding $source $sourceId) {
        $null = $rightsMetadataCheckIds.Add("live:$sourceId")
    }
    if ($liveSpecValid) {
        $null = $liveConnectorSpecCheckIds.Add("live_spec:$sourceId")
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
        elseif ($null -ne $geoPublicDate) {
            $chronologyChecks++
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
    elseif ($null -ne $geoSubmissionDate) {
        $chronologyChecks++
    }
    if ($null -ne $geoLastUpdateDate -and $geoLastUpdateDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.geo_last_update_date_as_captured) {
        Add-Failure 'chronology_mismatch' 'geo_last_update_date_as_captured'
    }
    elseif ($null -ne $geoLastUpdateDate) {
        $chronologyChecks++
    }
    if ($geoPmid -ne $manifest.chronology.geo_current_linked_pmid_as_captured) {
        Add-Failure 'chronology_mismatch' 'geo_current_linked_pmid_as_captured'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('geo_current_linked_pmid')
    }
}

if ($captureFiles.ContainsKey('sahu_pubmed_esummary')) {
    $pubmed = Get-Content -LiteralPath $captureFiles['sahu_pubmed_esummary'] -Raw | ConvertFrom-Json
    $record = $pubmed.result.PSObject.Properties['39779848'].Value
    $publicationDateFromSource = Convert-Date ([string]$record.epubdate) 'yyyy MMM d' 'qualifying_publication_date'
    if ($null -ne $publicationDateFromSource -and $publicationDateFromSource.ToString('yyyy-MM-dd') -ne $manifest.chronology.qualifying_publication_date) {
        Add-Failure 'chronology_mismatch' 'qualifying_publication_date'
    }
    elseif ($null -ne $publicationDateFromSource) {
        $chronologyChecks++
    }
    if ($record.elocationid -ne 'doi: 10.1038/s41586-024-08349-1') {
        Add-Failure 'publication_doi_mismatch' '39779848'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('sahu_publication_doi')
    }
}

if ($captureFiles.ContainsKey('clinvar_positive_v1')) {
    $clinvarV1 = Get-Content -LiteralPath $captureFiles['clinvar_positive_v1'] -Raw
    if ($clinvarV1 -notmatch '(?s)<div class="single-item-value">\s*Uncertain significance\s*</div>') {
        Add-Failure 'clinvar_aggregate_mismatch' 'clinvar_positive_v1'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('clinvar_v1_aggregate_vus')
    }
}

if ($captureFiles.ContainsKey('clinvar_positive_v4')) {
    $clinvarV4 = Get-Content -LiteralPath $captureFiles['clinvar_positive_v4'] -Raw
    if ($clinvarV4 -notmatch '(?s)<div class="single-item-value">\s*Uncertain significance\s*</div>') {
        Add-Failure 'clinvar_aggregate_mismatch' 'clinvar_positive_v4'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('clinvar_v4_aggregate_vus')
    }
    $v4UpdateMatch = [regex]::Match($clinvarV4, 'Record last updated (?<date>[A-Z][a-z]{2} \d{1,2}, \d{4})')
    if (-not $v4UpdateMatch.Success) {
        Add-Failure 'clinvar_date_missing' 'clinvar_positive_v4.record_last_updated'
    }
    else {
        $v4UpdateDate = Convert-Date $v4UpdateMatch.Groups['date'].Value 'MMM d, yyyy' 'clinvar_v4_update_date'
        if ($null -ne $v4UpdateDate -and $v4UpdateDate.ToString('yyyy-MM-dd') -ne $manifest.chronology.clinvar_v4_update_date) {
            Add-Failure 'chronology_mismatch' 'clinvar_v4_update_date'
        }
        elseif ($null -ne $v4UpdateDate) {
            $chronologyChecks++
        }
    }
}

if ($captureFiles.ContainsKey('clinvar_positive_v5')) {
    $clinvarV5 = Get-Content -LiteralPath $captureFiles['clinvar_positive_v5'] -Raw
    if ($clinvarV5 -notmatch '(?s)<div class="single-item-value">\s*Conflicting classifications of pathogenicity\s*<br />\s*Likely pathogenic \(1\); Uncertain significance \(2\)') {
        Add-Failure 'clinvar_aggregate_mismatch' 'clinvar_positive_v5'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('clinvar_v5_aggregate_conflicting')
    }

    $ambryMatch = [regex]::Match(
        $clinvarV5,
        '(?s)<div class="germline-submission".*?Likely pathogenic.*?\((?<evaluated>[A-Z][a-z]{2} \d{2}, \d{4})\).*?Accession:\s*SCV007552490\.1.*?First in ClinVar:\s*(?<first>[A-Z][a-z]{2} \d{2}, \d{4}).*?</tr>'
    )
    if (-not $ambryMatch.Success) {
        Add-Failure 'clinvar_submission_missing' 'SCV007552490.1'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('clinvar_v5_ambry_submission')
        $evaluatorDateFromSource = Convert-Date $ambryMatch.Groups['evaluated'].Value 'MMM dd, yyyy' 'later_evaluator_date'
        $appearanceDateFromSource = Convert-Date $ambryMatch.Groups['first'].Value 'MMM dd, yyyy' 'later_public_clinvar_appearance'
        if ($null -ne $evaluatorDateFromSource -and $evaluatorDateFromSource.ToString('yyyy-MM-dd') -ne $manifest.chronology.later_evaluator_date) {
            Add-Failure 'chronology_mismatch' 'later_evaluator_date'
        }
        elseif ($null -ne $evaluatorDateFromSource) {
            $chronologyChecks++
        }
        if ($null -ne $appearanceDateFromSource -and $appearanceDateFromSource.ToString('yyyy-MM-dd') -ne $manifest.chronology.later_public_clinvar_appearance) {
            Add-Failure 'chronology_mismatch' 'later_public_clinvar_appearance'
        }
        elseif ($null -ne $appearanceDateFromSource) {
            $chronologyChecks++
        }
    }

    if ($clinvarV5 -notmatch '(?s)Accession:\s*SCV007552490\.1.*?/pubmed/39779848/.*?</tr>' -or
        $clinvarV5.Contains('39779857')) {
        Add-Failure 'clinvar_cited_pmid_mismatch' 'SCV007552490.1:expected_only=39779848'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('clinvar_v5_ambry_citation')
    }
}

if ($captureFiles.ContainsKey('nature_sahu_data_availability_linkage')) {
    $linkage = Get-Content -LiteralPath $captureFiles['nature_sahu_data_availability_linkage'] -Raw | ConvertFrom-Json
    $excerptText = [string]$linkage.verbatim_excerpt
    $actualExcerptWordCount = if ([string]::IsNullOrWhiteSpace($excerptText)) {
        0
    }
    else {
        @($excerptText.Trim() -split '\s+').Count
    }
    if ($linkage.pmid -ne $manifest.chronology.qualifying_nature_pmid) {
        Add-Failure 'publication_geo_linkage_invalid' 'nature_publication_pmid'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('nature_publication_pmid')
    }
    if ($linkage.doi -ne '10.1038/s41586-024-08349-1') {
        Add-Failure 'publication_geo_linkage_invalid' 'nature_publication_doi'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('nature_publication_doi')
    }
    if ($linkage.geo_accession -ne 'GSE248438') {
        Add-Failure 'publication_geo_linkage_invalid' 'nature_geo_accession'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('nature_geo_accession')
    }
    if ($linkage.full_article_captured -ne $false) {
        Add-Failure 'publication_geo_linkage_invalid' 'nature_full_article_not_captured'
    }
    else {
        $null = $sourceSemanticCheckIds.Add('nature_full_article_not_captured')
    }
    if ($actualExcerptWordCount -ne [int]$linkage.excerpt_word_count -or
        $actualExcerptWordCount -gt 25) {
        Add-Failure 'nature_excerpt_word_count_mismatch' "stored=$($linkage.excerpt_word_count):actual=$actualExcerptWordCount"
    }
    else {
        $null = $sourceSemanticCheckIds.Add('nature_excerpt_word_count')
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
        $rowValid = $true
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
                $rowValid = $false
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
            $rowValid = $false
        }
        if ($actualProbability -ne [double]$manifest.exact_functional_row.probability) {
            Add-Failure 'exact_row_value_mismatch' 'probability'
            $rowValid = $false
        }
        if ($rowValid) {
            $exactXlsxRows++
        }
    }
    catch {
        Add-Failure 'xlsx_parse_failed' $_.Exception.Message
    }
}

if ($null -ne $publicationDateFromSource -and $null -ne $evaluatorDateFromSource -and
    ($evaluatorDateFromSource - $publicationDateFromSource).Days -ne [int]$manifest.positive_case.derived_days_to_evaluator_date) {
    Add-Failure 'derived_interval_mismatch' 'derived_days_to_evaluator_date'
}
if ($null -ne $publicationDateFromSource -and $null -ne $appearanceDateFromSource -and
    ($appearanceDateFromSource - $publicationDateFromSource).Days -ne [int]$manifest.positive_case.derived_days_to_public_appearance) {
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
    chronology_checks = $chronologyChecks
    source_semantic_checks = $sourceSemanticCheckIds.Count
    source_semantic_check_ids = @($sourceSemanticCheckIds | Sort-Object)
    rights_metadata_checks = $rightsMetadataCheckIds.Count
    rights_metadata_check_ids = @($rightsMetadataCheckIds | Sort-Object)
    live_connector_spec_checks = $liveConnectorSpecCheckIds.Count
    live_connector_spec_check_ids = @($liveConnectorSpecCheckIds | Sort-Object)
    exact_xlsx_rows = $exactXlsxRows
    live_public_sources = @($manifest.live_public_sources).Count
    network_calls = 0
}
