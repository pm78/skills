---
name: openclaw-skill-installer
description: Fetch a skill folder from OpenClaw (`~/.openclaw/skills`), ClawHub, or GitHub and install it for Codex skill discovery in `.agents/skills`, `~/.agents/skills`, and optional Codex-home layouts. Use when the user asks to import, bridge, sync, or install skills from OpenClaw/ClawHub/GitHub into Codex.
---

# OpenClaw Skill Installer

## Overview

Import one skill folder that contains `SKILL.md` and install it into Codex skill paths.

Use the bundled script:

- `scripts/import_openclaw_skill.sh`

## Required input

Collect these values before running:

- Source type:
  - local skill directory (`--from-dir`)
  - OpenClaw installed skill name (`--from-openclaw`)
  - ClawHub slug (`--from-clawhub`)
  - GitHub repository URL (`--from-github`)
- Install mode: `copy` or `symlink`
- Destination scope: `user`, `project`, or `both`

Optional:

- GitHub subpath when repo contains multiple skills (`--github-skill-path`)
- Project root for project installs (`--project-root`)
- Target layout (`agents`, `codex-home`, or `both`)

## Workflow

1. Resolve the source skill folder and verify `SKILL.md` exists.
2. Determine the skill name from frontmatter (`name:`) or folder name.
3. Install to Codex-discoverable paths.
4. Verify install by checking `<destination>/<skill-name>/SKILL.md`.

## Command patterns

Run from this skill directory.

```bash
bash scripts/import_openclaw_skill.sh --from-openclaw my-skill --scope user --mode copy
```

```bash
bash scripts/import_openclaw_skill.sh --from-clawhub my-skill-slug --scope user --mode symlink
```

```bash
bash scripts/import_openclaw_skill.sh \
  --from-github https://github.com/acme/skill-repo.git \
  --github-skill-path skills/my-skill \
  --scope both \
  --mode copy
```

```bash
bash scripts/import_openclaw_skill.sh --from-dir ~/.openclaw/skills/my-skill --scope project --project-root /path/to/project
```

Dry-run before writing:

```bash
bash scripts/import_openclaw_skill.sh --from-openclaw my-skill --dry-run
```

## Destination rules

- `--target-layout agents` writes to:
  - user: `~/.agents/skills`
  - project: `<project-root>/.agents/skills`
- `--target-layout codex-home` writes to:
  - user: `${CODEX_HOME:-~/.codex}/skills`
  - project: `<project-root>/.codex/skills`
- `--target-layout both` writes to both layout families.

## Validation checklist

- Source folder contains `SKILL.md`.
- Installed folder exists in each destination.
- Installed `SKILL.md` is readable.

## Troubleshooting

- If ClawHub install fails, ensure `clawhub` CLI is installed and authenticated.
- If GitHub repo has multiple skills and auto-detect fails, pass `--github-skill-path`.
- If target folder already exists, choose another name with `--skill-name` or remove the existing folder first.
