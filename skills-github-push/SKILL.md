---
name: skills-github-push
description: Sync (clone/copy/commit/push) your installed Codex skills from $CODEX_HOME/skills to a GitHub repo (e.g. pm78/skills). Use when asked to back up, version-control, or publish all installed skills to GitHub, or to keep a skills repository in sync with local installs.
---

# Skills GitHub Push

## Workflow

1. Confirm the target repo (default: `pm78/skills`).
2. Ensure `git` can push to the repo (SSH keys or a credential helper). In sandboxed runs, use escalated commands for network access.
3. Run the sync script:

```bash
python3 scripts/push_skills.py --repo pm78/skills
```

## Options

- `--layout auto|root|skills`: Put skills at repo root, under `skills/`, or auto-detect.
- `--only <skill>`: Sync only a specific skill (repeatable).
- `--exclude <skill>`: Skip a specific skill (repeatable).
- `--include-system`: Also sync skills under `.system/*`.
- `--skills-dir <path>`: Override local skills directory.
- `--dry-run`: Clone/copy/stage only (no commit/push).
- `--author-name/--author-email`: Set commit author identity for the temp clone.

## Notes

- The script clones the repo into a temporary directory, copies skill folders, commits, and pushes.
- Existing folders in the repo that match synced skill paths will be replaced in that temp clone before committing.
