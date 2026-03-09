---
name: skills-sync-publish
description: Synchronize the canonical WSL skills/env with myvps, then optionally publish the resulting managed skill library to the GitHub repo pm78/skills. Use when asked to sync skills between WSL and VPS, back them up to GitHub, or run both steps safely with dry-run and conflict controls.
---

# Skills Sync Publish

Use this skill for the managed skills workflow centered on:

- shared skills in `~/.agents/skills`
- role skills in `~/.agents/role_skills`
- shared env in `~/.agents/skills/.env`
- VPS target via SSH alias `myvps`
- GitHub repo `pm78/skills`

## Workflow

1. Start with a dry-run unless the user explicitly wants the real sync immediately.
2. Run the WSL<->VPS sync first.
3. If requested, publish the managed skill library to GitHub after a successful sync.
4. Do not print `.env` values.

## Commands

Dry-run sync only:

```bash
python3 ~/.agents/skills/skills-sync-publish/scripts/sync_and_publish.py --dry-run --sync-only
```

Real sync only:

```bash
python3 ~/.agents/skills/skills-sync-publish/scripts/sync_and_publish.py --sync-only
```

Dry-run sync plus GitHub publish preview:

```bash
python3 ~/.agents/skills/skills-sync-publish/scripts/sync_and_publish.py --dry-run --publish
```

Real sync plus GitHub push to the default repo:

```bash
python3 ~/.agents/skills/skills-sync-publish/scripts/sync_and_publish.py --publish
```

## Options

- `--prefer-wsl` or `--prefer-vps`: resolve equal-mtime conflicts for the WSL<->VPS sync.
- `--publish`: after sync, publish skills to GitHub.
- `--publish-only`: skip WSL<->VPS sync and only publish to GitHub.
- `--repo <owner/repo|url>`: override the GitHub repo. Default: `pm78/skills`.
- `--author-name` and `--author-email`: set git commit identity for the push helper.
- `--message`: override the Git commit message.

## Notes

- The GitHub publish step uses the existing `skills-github-push` script, but points it at the canonical `.agents` roots rather than the exported Codex/Claude directories.
- The default GitHub target uses the HTTPS repo form because it already works in this environment. If you want fully headless pushes without credential-helper prompts, pass an explicit SSH remote such as `git@github.com:pm78/skills.git` after configuring GitHub SSH keys.
- The GitHub publish step strips local-only symlink artifacts so the repo does not receive broken absolute symlinks.
