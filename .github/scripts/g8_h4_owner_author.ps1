param(
    [Parameter(Mandatory = $true)]
    [string]$SourceSha
)

$ErrorActionPreference = "Stop"
$pythonExe = $null
$pythonPrefix = @()

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & $py.Source -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = $py.Source
        $pythonPrefix = @("-3.12")
    }
}

if (-not $pythonExe) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = $python.Source
        }
    }
}

if (-not $pythonExe -and $env:RUNNER_TOOL_CACHE) {
    $cached = Get-ChildItem -LiteralPath $env:RUNNER_TOOL_CACHE -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '[\\/]Python[\\/]3\.12\.' }
    foreach ($candidate in $cached) {
        & $candidate.FullName -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = $candidate.FullName
            break
        }
    }
}

if (-not $pythonExe) {
    throw "Python 3.12 is required on the trusted owner runner."
}

& $pythonExe @pythonPrefix -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    throw "TracePixel editable install failed."
}

& $pythonExe @pythonPrefix .github/scripts/g8_h4_owner_author.py --source-sha $SourceSha
exit $LASTEXITCODE
