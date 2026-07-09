param(
    [switch] $Strict
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $RepoRoot
try {
    git config core.hooksPath .githooks
    if ($Strict) {
        git config aiReview.strict true
    }
    else {
        git config --unset aiReview.strict 2>$null
    }

    Write-Host "Installed AI review pre-push hook."
    Write-Host "Set OPENAI_API_KEY for OpenAI API review, or install Codex CLI for local review."
    Write-Host "Run manually with: powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode working"
}
finally {
    Pop-Location
}
