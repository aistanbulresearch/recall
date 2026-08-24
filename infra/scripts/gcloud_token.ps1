# Bounded access-token retrieval for the infra scripts.
#
# `gcloud auth print-access-token` does not always fail when credentials lapse.
# It can try to open an interactive reauthentication prompt, and in a
# non-interactive session there is nowhere to show it, so the process never
# returns. Two such processes were measured on 2026-08-23 still running after 49
# and 28 hours, holding 2.2 GB and 1.3 GB and burning CPU the whole time. The
# caller had written `|| echo failed`; that branch never ran, because a process
# that never exits never yields an exit code.
#
# So the timeout is the protection, not the exit code. Two measured details this
# encodes:
#
#   * `Get-Command gcloud` resolves to gcloud.ps1, which Process.Start cannot
#     launch. The .cmd shim next to it is what runs.
#   * Neither `--quiet` nor CLOUDSDK_CORE_DISABLE_PROMPTS was shown to prevent
#     the hang. Measured against a credential-less config all three variants
#     exited 1 in 5 to 7 seconds, which is the wrong failure to learn from. The
#     env var is still set because it is free, but nothing here relies on it.
#
# Dot-source it:
#     . "$PSScriptRoot\gcloud_token.ps1"
#     $token = Get-RecallAccessToken
#
# Failures are typed and distinct, so a timeout is never mistaken for a
# credential problem:
#     recall_token_timeout:<seconds>      the call was cut off at the limit
#     recall_token_auth_failed:<exitcode> gcloud answered, and refused
#     recall_token_empty                  gcloud exited 0 with no token
#     recall_token_gcloud_missing         no gcloud.cmd on PATH

# No Set-StrictMode here on purpose. This file is dot-sourced, so a strict mode
# set at file scope leaks into the caller's session and changes the semantics of
# code this helper knows nothing about.

function Resolve-RecallGcloudCommand {
    <#
        .SYNOPSIS
        Locate gcloud.cmd, the shim Process.Start can actually launch.
    #>
    $command = Get-Command gcloud -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "recall_token_gcloud_missing" }
    $candidate = Join-Path (Split-Path $command.Source -Parent) 'gcloud.cmd'
    if (-not (Test-Path -LiteralPath $candidate)) { throw "recall_token_gcloud_missing" }
    return $candidate
}

function Stop-RecallProcessTree {
    <#
        .SYNOPSIS
        Terminate a started process and its descendants.

        .DESCRIPTION
        gcloud.cmd spawns python, so stopping only the launched process leaves
        the child running: that is exactly how the measured orphans survived.

        The root id is validated first. A null or system id is refused rather
        than walked, because enumerating children of pid 0 reaches kernel
        processes, and asking to stop those is never something this helper
        should do.
    #>
    param([Parameter(Mandatory = $true)][AllowNull()][System.Nullable[int]]$RootId)

    if ($null -eq $RootId -or $RootId -le 4) { return 0 }

    $snapshot = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Select-Object ProcessId, ParentProcessId
    $ids = New-Object System.Collections.Generic.List[int]
    $ids.Add([int]$RootId)
    $index = 0
    while ($index -lt $ids.Count) {
        $current = $ids[$index]
        foreach ($entry in $snapshot) {
            if ($entry.ParentProcessId -eq $current -and -not $ids.Contains([int]$entry.ProcessId)) {
                if ([int]$entry.ProcessId -gt 4) { $ids.Add([int]$entry.ProcessId) }
            }
        }
        $index++
    }

    $stopped = 0
    foreach ($id in ($ids | Sort-Object -Descending)) {
        try {
            Stop-Process -Id $id -Force -ErrorAction Stop
            $stopped++
        } catch {
            # Already gone, or not ours to stop. Counted as not stopped.
        }
    }
    return $stopped
}

function Get-RecallAccessToken {
    <#
        .SYNOPSIS
        Return an access token, or fail within the time limit.

        .PARAMETER TimeoutSeconds
        Upper bound on the whole call. Default 30.

        .PARAMETER GcloudPath
        Override the executable. Used by the tests to substitute a stub.
    #>
    param(
        [int]$TimeoutSeconds = 30,
        [string]$GcloudPath
    )

    if ($TimeoutSeconds -le 0) { throw "recall_token_timeout_invalid:$TimeoutSeconds" }
    if ([string]::IsNullOrWhiteSpace($GcloudPath)) { $GcloudPath = Resolve-RecallGcloudCommand }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $GcloudPath
    $psi.Arguments = 'auth print-access-token --quiet'
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    # Free if it helps, relied on if it does not.
    $psi.EnvironmentVariables['CLOUDSDK_CORE_DISABLE_PROMPTS'] = '1'

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    # Read both streams asynchronously. A synchronous read before exit can block
    # once a pipe buffer fills, which would reintroduce the hang this prevents.
    $stdout = New-Object System.Text.StringBuilder
    $stderr = New-Object System.Text.StringBuilder
    $outEvent = Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action {
        if ($null -ne $EventArgs.Data) { [void]$Event.MessageData.Append($EventArgs.Data) }
    } -MessageData $stdout
    $errEvent = Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action {
        if ($null -ne $EventArgs.Data) { [void]$Event.MessageData.AppendLine($EventArgs.Data) }
    } -MessageData $stderr

    $startedId = $null
    try {
        if (-not $process.Start()) { throw "recall_token_gcloud_missing" }
        $startedId = $process.Id
        $process.BeginOutputReadLine()
        $process.BeginErrorReadLine()

        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $stopped = Stop-RecallProcessTree -RootId $startedId
            Write-Verbose "recall_token_timeout: stopped $stopped process(es) rooted at $startedId"
            throw "recall_token_timeout:$TimeoutSeconds"
        }

        $exitCode = $process.ExitCode
        Start-Sleep -Milliseconds 50   # let the async handlers drain
        if ($exitCode -ne 0) { throw "recall_token_auth_failed:$exitCode" }

        $token = $stdout.ToString().Trim()
        if ([string]::IsNullOrWhiteSpace($token)) { throw "recall_token_empty" }
        return $token
    }
    finally {
        Unregister-Event -SourceIdentifier $outEvent.Name -ErrorAction SilentlyContinue
        Unregister-Event -SourceIdentifier $errEvent.Name -ErrorAction SilentlyContinue
        if ($null -ne $startedId) {
            try {
                if (-not $process.HasExited) { [void](Stop-RecallProcessTree -RootId $startedId) }
            } catch {
                # The process object may already be released; nothing to stop.
            }
        }
        $process.Dispose()
    }
}

function Get-RecallProject {
    <#
        .SYNOPSIS
        Resolve the active project without launching gcloud.

        .DESCRIPTION
        `gcloud config get-value project` is the same call that hung for hours
        when credentials lapsed, and it does not run unbounded during a
        milestone. The value it prints is already on disk in the active gcloud
        configuration, so this reads the file and starts no process at all. A
        call that never happens cannot hang.

        Order: RECALL_GCP_PROJECT, then the active configuration file. An
        unresolved project throws rather than returning empty, because an empty
        project silently builds a request against no project.

        .PARAMETER ConfigPath
        Override the configuration file. Used by the tests.
    #>
    param(
        [string]$ConfigPath
    )

    if (-not [string]::IsNullOrWhiteSpace($env:RECALL_GCP_PROJECT)) {
        return $env:RECALL_GCP_PROJECT
    }

    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        $root = if ($env:CLOUDSDK_CONFIG) { $env:CLOUDSDK_CONFIG } else { Join-Path $env:APPDATA 'gcloud' }
        $active = 'default'
        $activeFile = Join-Path $root 'active_config'
        if (Test-Path -LiteralPath $activeFile) {
            $named = (Get-Content -LiteralPath $activeFile -First 1).Trim()
            if (-not [string]::IsNullOrWhiteSpace($named)) { $active = $named }
        }
        $ConfigPath = Join-Path $root ("configurations\config_" + $active)
    }

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "recall_project_config_missing"
    }
    foreach ($line in Get-Content -LiteralPath $ConfigPath) {
        if ($line -match '^\s*project\s*=\s*(\S+)\s*$') { return $Matches[1] }
    }
    throw "recall_project_unresolved"
}
