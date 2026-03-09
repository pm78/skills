---
name: git-worktree-manager
description: Create and manage git worktrees for parallel feature development, including choosing a branch/slug, setting a base worktree directory, adding new or existing worktrees, opening them in an editor, and suggesting a parallel Codex session. Use when asked to spin up a parallel workspace, open a worktree in an editor, or handle worktree cleanup.
---

# Git Worktree Manager

## Overview

Use this workflow to create and open git worktrees safely and consistently.

## Workflow

1. Confirm the repo root. Use the current working directory unless the user specifies another repo. Validate with `git rev-parse --show-toplevel` if needed.
2. Determine the feature slug and branch name. Default branch pattern: `feat/<slug>`. If the user provides a branch name, use it as-is.
3. Choose the base directory for linked worktrees. Default: `../<project_name>-wt` (project name from repo root). Create it if missing.
4. Create the worktree.
   - New branch: `git worktree add -b feat/<slug> <base>/<slug>`
   - Existing branch: `git worktree add <base>/<slug> <branch>`
5. Open the worktree in the editor.
   - Prefer `code -n <path>`.
   - If `code` is unavailable, ask for the preferred editor command (e.g., `cursor -n`, `code`, `idea`).
6. Suggest a parallel Codex session in the new worktree: `cd <path> && codex`.
7. Confirm with `git worktree list` if the user asks for verification.

## Safety

- Do not use `--force` unless explicitly requested.
- Do not remove existing worktrees or branches unless the user asks for cleanup.

## Optional Cleanup (only if requested)

- Remove a worktree: `git worktree remove <path>`
- Delete a branch: `git branch -d <branch>`
