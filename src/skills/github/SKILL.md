---
name: github
summary: 通过 gh CLI 操作 GitHub（issues/PR/runs/api）
user-invocable: false
priority: low
category: dev
triggers:
  keywords:
    - GitHub
    - gh
    - PR
    - issue
    - workflow
    - CI
  intents:
    - 查/建/改 GitHub issue 或 PR
    - 查 CI 状态、workflow 日志
examples:
  - 看下 owner/repo 最新 PR 的 CI 状态
---

# GitHub Skill

Use the `gh` CLI to interact with GitHub. Always specify `--repo owner/repo` when not in a git directory, or use URLs directly.

## Pull Requests

Check CI status on a PR:
```bash
gh pr checks 55 --repo owner/repo
```

List recent workflow runs:
```bash
gh run list --repo owner/repo --limit 10
```

View a run and see which steps failed:
```bash
gh run view <run-id> --repo owner/repo
```

View logs for failed steps only:
```bash
gh run view <run-id> --repo owner/repo --log-failed
```

## API for Advanced Queries

The `gh api` command is useful for accessing data not available through other subcommands.

Get PR with specific fields:
```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'
```

## JSON Output

Most commands support `--json` for structured output.  You can use `--jq` to filter:

```bash
gh issue list --repo owner/repo --json number,title --jq '.[] | "\(.number): \(.title)"'
```
