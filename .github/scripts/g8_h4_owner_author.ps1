param(
    [Parameter(Mandatory = $true)]
    [string]$SourceSha
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Get-Location).Path
$OutputRoot = Join-Path $RepoRoot "artifacts/g8-h4-retained"
$PriorRoot = Join-Path $RepoRoot "artifacts/g8-h4-prior-attempts"
$AttemptPath = Join-Path $OutputRoot "attempt-complexity.json"
$LegacyComplexityPath = Join-Path $OutputRoot "complexity.json"
$CumulativePath = Join-Path $OutputRoot "complexity.json"
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$ProviderCommandStarted = $false
$PythonExe = $null
$PythonPrefix = @()

New-Item -ItemType Directory -Force $OutputRoot | Out-Null
New-Item -ItemType Directory -Force $PriorRoot | Out-Null

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Path -Encoding utf8
}

function Get-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return @($py.Source, "-3.12")
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return @($python.Source)
        }
    }

    if ($env:RUNNER_TOOL_CACHE) {
        $cached = Get-ChildItem -LiteralPath $env:RUNNER_TOOL_CACHE -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '[\\/]Python[\\/]3\.12\.' }
        foreach ($candidate in $cached) {
            & $candidate.FullName -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
            if ($LASTEXITCODE -eq 0) {
                return @($candidate.FullName)
            }
        }
    }

    throw "Python 3.12 is required on the trusted owner runner."
}

function Invoke-PythonChecked {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $script:PythonExe @script:PythonPrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE: $($Arguments -join ' ')"
    }
}

function Ensure-FailureEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][bool]$ProviderMayHaveRun
    )

    $failurePath = Join-Path $script:OutputRoot "failure.json"
    if (-not (Test-Path -LiteralPath $failurePath)) {
        Write-JsonFile -Path $failurePath -Value ([ordered]@{
            phase = "G8"
            child = "G8-H4"
            status = "failed-in-owner-executor"
            source_sha = $script:SourceSha.ToLowerInvariant()
            failure_type = "OwnerExecutorFailure"
            message = $Message
            contract_first = $true
            minimal_fix_required_before_new_schema = $true
            new_schema_or_contract_added = $false
            new_raster_authority_added = $false
        })
    }

    $summaryPath = Join-Path $script:OutputRoot "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath)) {
        Write-JsonFile -Path $summaryPath -Value ([ordered]@{
            phase = "G8"
            child = "G8-H4"
            source_issue = 119
            source_sha = $script:SourceSha.ToLowerInvariant()
            status = "failed"
            owner_verdict = "pending"
            failure_evidence = "failure.json"
            new_schema_or_contract_added = $false
            new_raster_authority_added = $false
            animation_advanced = $false
            trace2d_integration_advanced = $false
        })
    }

    if (-not (Test-Path -LiteralPath $script:AttemptPath)) {
        $elapsedNs = [int64]($script:Stopwatch.ElapsedTicks * (1000000000.0 / [System.Diagnostics.Stopwatch]::Frequency))
        $knownZero = -not $ProviderMayHaveRun
        Write-JsonFile -Path $script:AttemptPath -Value ([ordered]@{
            measurement_scope = "single-retained-authoring-attempt"
            raw_usage_authoritative = $true
            price_conversion_authoritative = $false
            provider_calls = $(if ($knownZero) { 0 } else { $null })
            input_tokens = $(if ($knownZero) { 0 } else { $null })
            output_tokens = $(if ($knownZero) { 0 } else { $null })
            iterations = $(if ($knownZero) { 0 } else { $null })
            revisions = $(if ($knownZero) { 0 } else { $null })
            operation_calls = $(if ($knownZero) { 0 } else { $null })
            pixel_edits = $(if ($knownZero) { 0 } else { $null })
            changed_pixels = $(if ($knownZero) { 0 } else { $null })
            repair_vs_regeneration = [ordered]@{
                repair_provider_calls = $(if ($knownZero) { 0 } else { $null })
                regeneration_provider_calls = $(if ($knownZero) { 0 } else { $null })
                canvas_restarts = $(if ($knownZero) { 0 } else { $null })
            }
            wall_time_ns = $elapsedNs
            cache_or_profile_reuse = [ordered]@{
                humanoid_profile_reused = $(if ($knownZero) { $true } else { $null })
                pose_profile_reused = $(if ($knownZero) { $true } else { $null })
                profile_research_provider_calls = $(if ($knownZero) { 0 } else { $null })
            }
            evidence_completeness = $(if ($knownZero) { "exact-zero-provider-pre-authoring-failure" } else { "incomplete-failure-after-provider-command-started" })
        })
    }
}

function Collect-PriorAttempts {
    if (-not $env:GH_TOKEN) { throw "GH_TOKEN is required to collect prior retained H4 attempts." }
    if (-not $env:REPOSITORY) { throw "REPOSITORY is required to collect prior retained H4 attempts." }
    if (-not $env:GITHUB_RUN_ID) { throw "GITHUB_RUN_ID is required to collect prior retained H4 attempts." }

    $env:G8_H4_PRIOR_ROOT = $script:PriorRoot
    $collector = @'
import io
import json
import os
from pathlib import Path
import urllib.request
import zipfile

repo = os.environ["REPOSITORY"]
token = os.environ["GH_TOKEN"]
current_run_id = int(os.environ["GITHUB_RUN_ID"])
root = Path(os.environ["G8_H4_PRIOR_ROOT"])
root.mkdir(parents=True, exist_ok=True)
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "TracePixel-G8-H4-scripted-owner-authoring",
}

def get_json(url: str):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

runs = get_json(
    f"https://api.github.com/repos/{repo}/actions/workflows/owner-g8-h4-pr-executor.yml/runs?status=completed&per_page=100"
).get("workflow_runs", [])

for run in runs:
    run_id = int(run.get("id", 0))
    if run_id <= 0 or run_id >= current_run_id:
        continue
    artifacts = get_json(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    ).get("artifacts", [])
    retained = next(
        (
            artifact
            for artifact in artifacts
            if not artifact.get("expired", False)
            and artifact.get("name") == f"g8-h4-retained-authoring-{run_id}"
        ),
        None,
    )
    if retained is None:
        continue
    request = urllib.request.Request(retained["archive_download_url"], headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        archive_bytes = response.read()
    target = root / str(run_id)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        for name in ("attempt-complexity.json", "complexity.json", "summary.json", "failure.json"):
            if name in names:
                (target / name).write_bytes(archive.read(name))
'@

    & $script:PythonExe @script:PythonPrefix -c $collector
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to collect prior retained G8-H4 attempt evidence."
    }
}

function Verify-Candidate {
    $summaryPath = Join-Path $script:OutputRoot "summary.json"
    if (-not (Test-Path -LiteralPath $summaryPath)) { throw "summary.json is missing." }
    if (-not (Test-Path -LiteralPath $script:CumulativePath)) { throw "cumulative complexity.json is missing." }

    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    $complexity = Get-Content -LiteralPath $script:CumulativePath -Raw | ConvertFrom-Json

    if ($summary.status -ne "succeeded") { throw "Retained authoring did not succeed: $($summary.failure_reasons -join ', ')" }
    if ($summary.owner_verdict -ne "pending") { throw "H4 must not self-approve H5." }
    if ($summary.new_schema_or_contract_added) { throw "H4 added an unauthorized schema/contract." }
    if ($summary.new_raster_authority_added) { throw "H4 added unauthorized raster authority." }
    if ($summary.animation_advanced) { throw "H4 must not advance G9 animation." }
    if ($summary.trace2d_integration_advanced) { throw "H4 must not advance Trace2D integration." }

    if ($complexity.measurement_scope -ne "all-retained-g8-h4-attempts-through-owner-acceptable-candidate") {
        throw "H4 complexity scope is not cumulative through the current owner candidate."
    }
    if ($complexity.owner_acceptance_state -ne "pending") { throw "H4 must not freeze owner acceptance." }
    if ($complexity.authority.authoritative_evidence -ne "raw-usage-metrics") { throw "Raw usage metrics must remain authoritative." }
    if ($complexity.authority.price_fields_used_for_comparison) { throw "Price conversion must not be authoritative comparison evidence." }

    foreach ($field in @(
        "provider_calls", "input_tokens", "output_tokens", "iterations", "revisions",
        "operation_calls", "pixel_edits", "changed_pixels", "repair_provider_calls",
        "regeneration_provider_calls", "canvas_restarts", "profile_research_provider_calls", "wall_time_ns"
    )) {
        if (-not $complexity.usage_completeness.$field) {
            throw "Cumulative raw metric '$field' is incomplete."
        }
    }

    if ($complexity.provider_calls -lt 1) { throw "No real provider call was retained." }
    if ($null -eq $complexity.input_tokens -or $null -eq $complexity.output_tokens) { throw "Exact cumulative token totals are required." }
    if ($complexity.repair_vs_regeneration.regeneration_provider_calls -ne 0) { throw "H4 may repair the same canvas but may not regenerate it." }
    if (-not $complexity.cache_or_profile_reuse.humanoid_profile_reused_for_all_provider_attempts) { throw "Not all provider attempts reused the retained humanoid profile." }
    if (-not $complexity.cache_or_profile_reuse.pose_profile_reused_for_all_provider_attempts) { throw "Not all provider attempts reused the retained pose." }
    if ($complexity.cache_or_profile_reuse.profile_research_provider_calls -ne 0) { throw "H4 unexpectedly spent provider calls on profile research." }

    foreach ($field in @(
        "provider_calls", "input_tokens", "output_tokens", "iterations", "revisions",
        "operation_calls", "pixel_edits", "changed_pixels", "wall_time_ns"
    )) {
        if ($null -eq $complexity.p10_c4_comparison.metrics.$field.percent_change) {
            throw "P10-C4 percentage change is missing for non-zero baseline metric '$field'."
        }
    }

    foreach ($relativePath in @(
        "final.png",
        "preview-8x.png",
        "stage-index.json",
        "review-package/index.html",
        "review-package/index.ko.html",
        "review-package/H5_REVIEW.md"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $script:OutputRoot $relativePath))) {
            throw "Required retained review evidence is missing: $relativePath"
        }
    }
}

try {
    $pythonCommand = Get-PythonCommand
    $PythonExe = $pythonCommand[0]
    if ($pythonCommand.Count -gt 1) {
        $PythonPrefix = @($pythonCommand[1..($pythonCommand.Count - 1)])
    }

    & $PythonExe @PythonPrefix -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "TracePixel editable install failed." }

    codex --version
    if ($LASTEXITCODE -ne 0) { throw "Codex CLI is unavailable on the trusted owner runner." }
    $loginStatus = codex login status 2>&1 | Out-String
    Write-Host $loginStatus
    if ($loginStatus -notmatch "Logged in using ChatGPT") {
        throw "G8-H4 requires Codex CLI authenticated through the existing ChatGPT plan boundary."
    }
    if ($loginStatus -match "Logged in using an API key") {
        throw "API-key billed Codex execution is not authorized for G8-H4."
    }

    $ProviderCommandStarted = $true
    & $PythonExe @PythonPrefix -m evidence.g8_h4.retained_authoring --output $OutputRoot --source-sha $SourceSha
    $authoringExit = $LASTEXITCODE

    if ((Test-Path -LiteralPath $LegacyComplexityPath) -and -not (Test-Path -LiteralPath $AttemptPath)) {
        Copy-Item -LiteralPath $LegacyComplexityPath -Destination $AttemptPath
    }
    if (-not (Test-Path -LiteralPath $AttemptPath)) {
        Ensure-FailureEvidence -Message "Retained authoring exited without exact attempt complexity (exit $authoringExit)." -ProviderMayHaveRun $true
    }

    Collect-PriorAttempts

    & $PythonExe @PythonPrefix -m evidence.g8_h4.cumulative_complexity `
        --current $OutputRoot `
        --prior-root $PriorRoot `
        --current-run-id $env:GITHUB_RUN_ID `
        --output $CumulativePath
    if ($LASTEXITCODE -ne 0) { throw "Failed to aggregate cumulative G8-H4 complexity evidence." }

    $reviewGuide = Join-Path $OutputRoot "review-package/H5_REVIEW.md"
    if (Test-Path -LiteralPath $reviewGuide) {
        Add-Content -LiteralPath $reviewGuide -Encoding utf8 -Value @"

## Cumulative complexity authority

The sibling `complexity.json` is cumulative through this candidate. Raw provider/token/edit/repair/reuse/wall-time metrics are authoritative; price conversion is derived and non-authoritative. If the owner accepts this image, H5 must freeze this exact cumulative record.
"@
    }

    if ($authoringExit -ne 0) {
        throw "G8-H4 retained authoring exited with code $authoringExit; retained failure evidence was preserved."
    }

    Verify-Candidate
    Write-Host "G8-H4 retained static humanoid candidate and cumulative raw evidence verified."
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-Error $message
    Ensure-FailureEvidence -Message $message -ProviderMayHaveRun $ProviderCommandStarted
    exit 1
}
