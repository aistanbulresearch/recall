<#
.SYNOPSIS
    Answers the question the freeze depends on: does the MERGED result build.

.DESCRIPTION
    A clean merge is not a working merge. `git merge-tree` exiting 0 proves only
    that the texts combine, not that the combination compiles or passes. This
    script materialises the merged tree and runs the gate against it.

    It never touches a branch. The merged tree is committed as a DANGLING commit
    reachable from no ref, checked out in a detached temporary worktree, and the
    worktree is removed afterwards; the dangling commit is later collected. There
    is deliberately no `git merge` and therefore no reset to get wrong.

    It reports what it ran AND what it did not. A lane whose changes do not touch
    web/ gets no web figures, and the report says so rather than implying a suite
    was green when it never executed.

.PARAMETER Lane
    Branch to probe. Defaults to the current branch.

.PARAMETER Target
    Integration target. Defaults to feature/rcl-3xx-core.

.NOTES
    Exit codes. Only 0 means the merged tree was built and passed; every other
    code requires the caller to decide rather than inherit a verdict.

        0  READY         merged, built, every affected suite passed
        1  NOT READY     the merge conflicts, or an affected suite failed
        2  INCONCLUSIVE  a suite this lane affects could not be run at all
        3  NOTHING BUILT the merge is clean but no suite was affected

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\evidence\integration-probe.ps1
#>
[CmdletBinding()]
param(
    [string]$Lane = '',
    [string]$Target = 'feature/rcl-3xx-core',
    # Empty by default: it is derived per lane below. A FIXED path would mean two
    # lanes probing the same evening share a directory, and this script clears
    # that directory on entry, so one lane would delete the other's probe
    # mid-run. The nightly practice makes concurrent probes the normal case.
    [string]$ProbeRoot = '',
    # The probe worktree has no venv of its own. Point at the checkout's
    # interpreter so a missing dependency cannot read as a lane failure.
    [string]$PythonExe = 'C:\Users\oacav\OneDrive\Desktop\recall project\.venv\Scripts\python.exe'
)

Set-StrictMode -Version Latest
# Deliberately Continue, not Stop. In Windows PowerShell 5.1 a native command's
# stderr becomes ErrorRecords, so Stop would abort on `git worktree add` merely
# announcing "Preparing worktree" on stderr. Failure here is detected by exit
# code, which Invoke-Git checks explicitly.
$ErrorActionPreference = 'Continue'

function Invoke-Git {
    # Deliberately a SIMPLE function using $args. Declaring a parameter would make
    # this an advanced function, and PowerShell would then bind git's own -p as an
    # abbreviation of the common -PipelineVariable parameter.
    $output = & git $args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($args -join ' ') failed with exit code $LASTEXITCODE"
    }
    return $output
}

function Remove-ProbeTree {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    # robocopy /MIR from an empty directory clears paths that Remove-Item cannot.
    $empty = "$Path-empty"
    New-Item -ItemType Directory -Force -Path $empty | Out-Null
    robocopy $empty $Path /MIR /NFL /NDL /NJH /NJS /NC /NS | Out-Null
    Remove-Item -Recurse -Force $Path -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $empty -ErrorAction SilentlyContinue
}

if ([string]::IsNullOrWhiteSpace($Lane)) {
    $Lane = (Invoke-Git rev-parse --abbrev-ref HEAD).Trim()
}

if ([string]::IsNullOrWhiteSpace($ProbeRoot)) {
    # Short root by design: node_modules under a long temp path exceeds MAX_PATH
    # and cleanup then fails with "Filename too long".
    $slug = ($Lane -replace '[^A-Za-z0-9]', '-')
    $ProbeRoot = "C:\Users\oacav\AppData\Local\Temp\rp-$slug"
}

$laneHead = (Invoke-Git rev-parse --short $Lane).Trim()
$targetHead = (Invoke-Git rev-parse --short $Target).Trim()
$mergeBase = (Invoke-Git merge-base $Lane $Target).Trim()

Write-Host "Lane   : $Lane @ $laneHead"
Write-Host "Target : $Target @ $targetHead"
Write-Host "Base   : $($mergeBase.Substring(0,8))"
Write-Host ("Drift  : lane adds {0}, target added {1}" -f `
    (Invoke-Git rev-list --count "$Target..$Lane"), (Invoke-Git rev-list --count "$Lane..$Target"))

# ---------------------------------------------------------------- 1. does it merge
$mergeOutput = & git merge-tree --write-tree --name-only $Target $Lane
$mergeExit = $LASTEXITCODE
if ($mergeExit -ne 0) {
    Write-Host ''
    Write-Host 'NOT READY: the merge conflicts.' -ForegroundColor Red
    $mergeOutput | Select-Object -Skip 1 | ForEach-Object { Write-Host "  conflict: $_" }
    exit 1
}
$mergedTree = ($mergeOutput | Select-Object -First 1).Trim()
Write-Host "Merged tree: $($mergedTree.Substring(0,8)) (no conflicts)"

# ---------------------------------------------------------------- 2. does it build
$probeCommit = (Invoke-Git commit-tree $mergedTree -p $Target -p $Lane `
    -m "integration probe of $Lane into $Target, reachable from no ref").Trim()

Remove-ProbeTree -Path $ProbeRoot
Invoke-Git worktree add --detach $ProbeRoot $probeCommit | Out-Null

$results = [ordered]@{}
$notRun = [Collections.Generic.List[string]]::new()
# Suites this lane affects that could not be run at all. Distinct from $notRun,
# which is suites the lane does not affect.
$blocked = [Collections.Generic.List[string]]::new()
$failed = $false
try {
    # Only run a suite when the merge actually affects it. A green reported for a
    # suite that never ran is worse than no figure at all.
    $webTouched = (& git diff --name-only "$Target...$Lane" -- web/) -ne $null
    # scripts/ is included deliberately. Leaving it out once let a changed
    # Python file pass under a report that said the python suite was unaffected.
    $srcTouched = (& git diff --name-only "$Target...$Lane" -- src/ tests/ scripts/) -ne $null

    if ($webTouched -and (Test-Path (Join-Path $ProbeRoot 'web\package.json'))) {
        Push-Location (Join-Path $ProbeRoot 'web')
        try {
            & pnpm install --offline --frozen-lockfile 2>&1 | Out-Null
            $results['web install'] = $LASTEXITCODE
            & pnpm run web:build 2>&1 | Out-Null
            $results['web build'] = $LASTEXITCODE
            $testOutput = (& pnpm test 2>&1 | Out-String)
            $results['web tests'] = $LASTEXITCODE
            $counted = $testOutput | Select-String -Pattern 'Tests\s+(\d+) passed' | Select-Object -First 1
            if ($counted) { Write-Host "  web tests: $($counted.Matches[0].Groups[1].Value) passed" }
            & pnpm run check:no-preset 2>&1 | Out-Null
            $results['web preset scan'] = $LASTEXITCODE
        } finally { Pop-Location }
    } else {
        $notRun.Add('web suite (the lane does not change web/)')
    }

    if ($srcTouched -and (Test-Path (Join-Path $ProbeRoot 'pyproject.toml'))) {
        if (-not (Test-Path $PythonExe)) {
            # A suite that IS affected but CANNOT run is not the same as a suite
            # that is unaffected. Reporting it as merely "not run" would hand back
            # a green covering only the suites that happened to be runnable.
            $blocked.Add("python suite is affected by this lane but the interpreter was not found at $PythonExe")
        } else {
            # tests/ledger/test_firestore_ledger.py is FAIL-LOUD by design: with no
            # RECALL_FIRESTORE_TEST_MODE it errors rather than skipping, so that a
            # missing environment can never pass as a green. That is correct for
            # the suite and wrong for this probe, which would report a lane
            # failure that is really an unprovisioned environment. It is excluded
            # BY NAME and the exclusion is printed, never silently dropped.
            $firestoreGate = 'tests/ledger/test_firestore_ledger.py'
            $pytestArgs = @()
            if ($env:FIRESTORE_EMULATOR_HOST) {
                $env:RECALL_FIRESTORE_TEST_MODE = 'emulator'
            } else {
                $pytestArgs += @('--ignore', $firestoreGate)
                $notRun.Add("$firestoreGate (fail-loud env gate, needs RECALL_FIRESTORE_TEST_MODE=emulator or live; this probe provisions neither)")
            }
            Push-Location $ProbeRoot
            try {
                $pyOutput = (& $PythonExe -m pytest @pytestArgs 2>&1 | Out-String)
                $results['python tests'] = $LASTEXITCODE
                $pyCount = $pyOutput | Select-String -Pattern '(\d+) passed' | Select-Object -Last 1
                if ($pyCount) { Write-Host "  python tests: $($pyCount.Matches[0].Groups[1].Value) passed" }
            } finally { Pop-Location }
        }
    } else {
        $notRun.Add('python suite (the lane changes no python under src/, tests/ or scripts/)')
    }
}
finally {
    & git worktree remove --force $ProbeRoot 2>&1 | Out-Null
    Remove-ProbeTree -Path $ProbeRoot
    # Prune can fail on stale worktrees this script did not create; that is not
    # a probe result and must not change the verdict.
    & git worktree prune 2>&1 | Out-Null
}

# ---------------------------------------------------------------- 3. report
Write-Host ''
foreach ($key in $results.Keys) {
    $code = $results[$key]
    if ($code -ne 0) { $failed = $true }
    Write-Host ("  {0,-18} exit {1}" -f $key, $code)
}
foreach ($skipped in $notRun) { Write-Host "  not run: $skipped" }
foreach ($stuck in $blocked) { Write-Host "  BLOCKED: $stuck" -ForegroundColor Yellow }

Write-Host ''
if ($blocked.Count -gt 0) {
    Write-Host "INCONCLUSIVE: a suite this lane affects could not be run." -ForegroundColor Yellow
    Write-Host "This is not a pass and not a failure. Fix the environment and re-probe."
    exit 2
}
if ($results.Count -eq 0) {
    Write-Host "MERGES CLEAN, NOTHING BUILT: no suite was affected by this lane." -ForegroundColor Yellow
    Write-Host "That is not a build result. Do not report it as one."
    # Exit 3, NOT 0. The warning above addresses a human; the exit code addresses
    # a machine, and returning 0 here would let any automated caller inherit a
    # green for a lane where nothing was tested. That is the vacuous green this
    # instrument exists to refuse, so it must not emit one itself.
    exit 3
}
if ($failed) {
    Write-Host "NOT READY: the merged tree does not pass." -ForegroundColor Red
    exit 1
}
Write-Host "READY: $Lane merges into $Target @ $targetHead and the merged tree passes." -ForegroundColor Green
Write-Host "Expires if either branch moves. Re-probe rather than reusing this result."
exit 0
