# AI review automation

This repository includes three ways to review Claude-generated changes before they are merged.

## 1. Manual local review

Set one provider:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode working
```

Useful modes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode staged
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode branch -Base origin/main
```

If `OPENAI_API_KEY` is not set, the script tries Codex CLI when `codex` is available on `PATH`.

## 2. Automatic pre-push review

Install the hook:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ai-review-hook.ps1
```

The hook reviews the branch diff before `git push`. By default, a failed or unavailable AI
review does not block the push. To make it blocking:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ai-review-hook.ps1 -Strict
```

## 3. GitHub PR review

The workflow at `.github/workflows/ai-review.yml` runs on pull requests and comments with
an AI review.

Configure this repository secret in GitHub:

```text
OPENAI_API_KEY
```

Optionally configure this repository variable:

```text
OPENAI_MODEL
```

The default model is `gpt-4.1`.
