param(
    [Parameter(Mandatory = $true)]
    [string] $Title,
    [Parameter(Mandatory = $true)]
    [string[]] $Changed,
    [Parameter(Mandatory = $true)]
    [string[]] $Files,
    [string[]] $Verified = @(),
    [string[]] $Risks = @(),
    [string[]] $Next = @(),
    [string] $DoneId = "",
    [string] $DoneTask = "",
    [string] $DoneVerification = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ArgsList = @("scripts/update_handoff.py", "--title", $Title)

foreach ($Item in $Changed) { $ArgsList += @("--changed", $Item) }
foreach ($Item in $Files) { $ArgsList += @("--files", $Item) }
foreach ($Item in $Verified) { $ArgsList += @("--verified", $Item) }
foreach ($Item in $Risks) { $ArgsList += @("--risks", $Item) }
foreach ($Item in $Next) { $ArgsList += @("--next", $Item) }

if ($DoneId) {
    $ArgsList += @("--done-id", $DoneId, "--done-task", $DoneTask, "--done-verification", $DoneVerification)
}

Push-Location $RepoRoot
try {
    python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
