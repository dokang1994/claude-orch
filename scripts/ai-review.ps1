param(
    [ValidateSet("working", "staged", "branch")]
    [string] $Mode = "working",
    [string] $Base = "",
    [string] $DiffFile = "",
    [string] $Output = "",
    [ValidateSet("auto", "openai", "codex")]
    [string] $Provider = "auto",
    [switch] $AllowEmpty
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ArgsList = @("scripts/ai_review.py", "--mode", $Mode, "--provider", $Provider)

if ($Base) {
    $ArgsList += @("--base", $Base)
}
if ($DiffFile) {
    $ArgsList += @("--diff-file", $DiffFile)
}
if ($Output) {
    $ArgsList += @("--output", $Output)
}
if ($AllowEmpty) {
    $ArgsList += @("--allow-empty")
}

Push-Location $RepoRoot
try {
    python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
