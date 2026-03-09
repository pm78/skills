#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


HOME = Path.home()
SYNC_SCRIPT = HOME / ".agents" / "bin" / "sync-skills-wsl-vps.py"
PUSH_SCRIPT = HOME / ".agents" / "skills" / "skills-github-push" / "scripts" / "push_skills.py"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run WSL<->VPS skills sync, then optionally publish managed skills to GitHub."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview sync/publish actions without committing changes.")
    parser.add_argument("--sync-only", action="store_true", help="Only run the WSL<->VPS sync.")
    parser.add_argument("--publish", action="store_true", help="Publish to GitHub after a successful sync.")
    parser.add_argument("--publish-only", action="store_true", help="Skip VPS sync and only publish to GitHub.")
    parser.add_argument("--prefer-wsl", action="store_true", help="Resolve equal-mtime sync conflicts in favor of WSL.")
    parser.add_argument("--prefer-vps", action="store_true", help="Resolve equal-mtime sync conflicts in favor of VPS.")
    parser.add_argument(
        "--repo",
        default="pm78/skills",
        help="GitHub repo target. Default: pm78/skills",
    )
    parser.add_argument("--layout", choices=["auto", "root", "skills"], default="auto")
    parser.add_argument("--include-system", action="store_true", help="Also publish .system skills to GitHub.")
    parser.add_argument("--author-name", default=None)
    parser.add_argument("--author-email", default=None)
    parser.add_argument("--message", default=None, help="Override the Git commit message.")
    args = parser.parse_args()

    if args.prefer_wsl and args.prefer_vps:
        parser.error("Use at most one of --prefer-wsl or --prefer-vps.")
    if args.sync_only and args.publish_only:
        parser.error("Use either --sync-only or --publish-only, not both.")
    if not args.sync_only and not args.publish_only and not args.publish:
        args.publish = True
    return args


def main() -> int:
    args = parse_args()

    if not args.publish_only:
        sync_cmd = [sys.executable, str(SYNC_SCRIPT)]
        if args.dry_run:
            sync_cmd.append("--dry-run")
        if args.prefer_wsl:
            sync_cmd.append("--prefer-wsl")
        if args.prefer_vps:
            sync_cmd.append("--prefer-vps")
        run(sync_cmd)

    if args.sync_only:
        return 0

    if args.publish or args.publish_only:
        push_cmd = [
            sys.executable,
            str(PUSH_SCRIPT),
            "--repo",
            args.repo,
            "--layout",
            args.layout,
            "--skills-dir",
            str(HOME / ".agents" / "skills"),
            "--role-skills-dir",
            str(HOME / ".agents" / "role_skills"),
        ]
        if args.include_system:
            push_cmd.append("--include-system")
        if args.author_name:
            push_cmd.extend(["--author-name", args.author_name])
        if args.author_email:
            push_cmd.extend(["--author-email", args.author_email])
        if args.message:
            push_cmd.extend(["--message", args.message])
        if args.dry_run:
            push_cmd.append("--dry-run")
        run(push_cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
