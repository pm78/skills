---
name: skills-github-push
description: Sync (clone/copy/commit/push) your managed skills from the canonical ~/.agents roots to a GitHub repo (e.g. pm78/skills). Use when asked to back up, version-control, or publish the local skill library to GitHub.
---

# Skills GitHub Push

## Workflow

1. Confirm the target repo (default: `pm78/skills`).
2. Ensure `git` can push to the repo (SSH keys or a credential helper). In sandboxed runs, use escalated commands for network access.
3. Run the sync script:

```bash
python3 scripts/push_skills.py --repo pm78/skills --skills-dir ~/.agents/skills --role-skills-dir ~/.agents/role_skills
```

## Options

- `--layout auto|root|skills`: Put skills at repo root, under `skills/`, or auto-detect.
- `--only <skill>`: Sync only a specific skill (repeatable).
- `--exclude <skill>`: Skip a specific skill (repeatable).
- `--include-system`: Also sync skills under `.system/*`.
- `--skills-dir <path>`: Override local skills directory.
- `--role-skills-dir <path>`: Also include role skills from a separate root.
- `--dry-run`: Clone/copy/stage only (no commit/push).
- `--author-name/--author-email`: Set commit author identity for the temp clone.

## Notes

- The script clones the repo into a temporary directory, copies skill folders, commits, and pushes.
- By default it prefers the canonical `~/.agents/skills` root and can also include `~/.agents/role_skills`.
- Existing folders in the repo that match synced skill paths will be replaced in that temp clone before committing.
- Local-only symlink aliases and cache artifacts are stripped so the GitHub repo receives portable skill folders rather than broken absolute symlinks.
- Pass an explicit SSH repo URL such as `git@github.com:pm78/skills.git` if you want headless pushes and GitHub SSH keys are configured; otherwise the default HTTPS form can rely on the local credential helper.
