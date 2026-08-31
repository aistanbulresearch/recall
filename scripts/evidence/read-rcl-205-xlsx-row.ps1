[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$XlsxPath,

    [Parameter(Mandatory = $true)]
    [string]$AminoAcidChange,

    [Parameter(Mandatory = $true)]
    [string]$TranscriptHgvs,

    [Parameter(Mandatory = $true)]
    [string]$GenomicHgvs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-ZipEntryText {
    param(
        [object]$Archive,
        [string]$Name
    )

    $entry = $Archive.GetEntry($Name)
    if ($null -eq $entry) {
        throw "zip_entry_missing:$Name"
    }
    $reader = [IO.StreamReader]::new($entry.Open())
    try {
        return $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
}

$xlsxFull = [IO.Path]::GetFullPath($XlsxPath)
if (-not (Test-Path -LiteralPath $xlsxFull -PathType Leaf)) {
    throw "xlsx_missing:$xlsxFull"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($xlsxFull)
try {
    [xml]$sharedXml = Read-ZipEntryText $archive 'xl/sharedStrings.xml'
    $sharedNs = [Xml.XmlNamespaceManager]::new($sharedXml.NameTable)
    $sharedNs.AddNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
    $sharedStrings = @(
        $sharedXml.SelectNodes('//x:si', $sharedNs) | ForEach-Object {
            ($_.SelectNodes('.//x:t', $sharedNs) | ForEach-Object { $_.'#text' }) -join ''
        }
    )

    [xml]$sheetXml = Read-ZipEntryText $archive 'xl/worksheets/sheet1.xml'
    $sheetNs = [Xml.XmlNamespaceManager]::new($sheetXml.NameTable)
    $sheetNs.AddNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
    $matches = [Collections.Generic.List[object]]::new()

    foreach ($row in $sheetXml.SelectNodes('//x:sheetData/x:row', $sheetNs)) {
        $values = @(
            $row.SelectNodes('./x:c', $sheetNs) | ForEach-Object {
                $valueNode = $_.SelectSingleNode('./x:v', $sheetNs)
                if ($_.GetAttribute('t') -eq 's') {
                    $sharedStrings[[int]$valueNode.InnerText]
                }
                elseif ($null -ne $valueNode) {
                    $valueNode.InnerText
                }
                else {
                    ''
                }
            }
        )

        if ($values.Count -ge 9 -and
            $values[3] -eq $AminoAcidChange -and
            $values[4] -eq $TranscriptHgvs -and
            $values[5] -eq $GenomicHgvs) {
            $matches.Add([pscustomobject]@{
                row_number = [int]$row.GetAttribute('r')
                exon = [string]$values[0]
                codon_change = [string]$values[1]
                nucleotide_change = [string]$values[2]
                amino_acid_change = [string]$values[3]
                transcript_hgvs = [string]$values[4]
                genomic_hgvs = [string]$values[5]
                source_classification = [string]$values[6]
                function_score = [string]$values[7]
                probability = [string]$values[8]
            })
        }
    }

    if ($matches.Count -ne 1) {
        throw "exact_row_count_invalid:$($matches.Count)"
    }
    return $matches[0]
}
finally {
    $archive.Dispose()
}
