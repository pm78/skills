#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SkillEntry:
    src_dir: Path
    rel_path: Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    printable = " ".join(cmd)
    prefix = f"[{cwd}] " if cwd else ""
    print(f"+ {prefix}{printable}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _capture(cmd: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result.stdout


def _normalize_repo(repo: str) -> str:
    repo = repo.strip().rstrip("/")
    if repo.startswith("git@"):
        return repo
    if repo.startswith("https://") or repo.startswith("http://"):
        return repo if repo.endswith(".git") else f"{repo}.git"
    # Treat as "owner/repo".
    return f"https://github.com/{repo}.git"


def _discover_skills_dir(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_dir():
            raise SystemExit(f"--skills-dir is not a directory: {path}")
        return path

    codex_home = os.environ.get("CODEX_HOME")
    candidates: list[Path] = []
    if codex_home:
        candidates.append(Path(codex_home).expanduser().resolve() / "skills")

    candidates.append(Path.home() / ".agent" / "skills")
    candidates.append(Path.home() / ".codex" / "skills")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    raise SystemExit(
        "Could not locate your Codex skills directory. "
        "Set CODEX_HOME or pass --skills-dir explicitly."
    )


def _list_skill_entries(
    *,
    skills_dir: Path,
    include_hidden: bool,
    include_system: bool,
    only: list[str] | None,
    exclude: list[str] | None,
) -> list[SkillEntry]:
    only_set = set(only or [])
    exclude_set = set(exclude or [])

    entries: list[SkillEntry] = []

    def maybe_add(src_dir: Path, rel_path: Path) -> None:
        if not src_dir.is_dir():
            return
        if not (src_dir / "SKILL.md").is_file():
            return
        if not include_hidden and rel_path.parts and rel_path.parts[0].startswith("."):
            return
        if only_set and rel_path.name not in only_set:
            return
        if rel_path.name in exclude_set:
            return
        entries.append(SkillEntry(src_dir=src_dir, rel_path=rel_path))

    for child in sorted(skills_dir.iterdir()):
        if child.name.startswith("."):
            continue
        maybe_add(child, Path(child.name))

    if include_system:
        system_root = skills_dir / ".system"
        if system_root.is_dir():
            for child in sorted(system_root.iterdir()):
                maybe_add(child, Path(".system") / child.name)

    return entries


def _git_config_get(repo_dir: Path, key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=str(repo_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync installed Codex skills to a GitHub repo (clone, copy, commit, push)."
    )
    parser.add_argument(
        "--repo",
        default="pm78/skills",
        help="Target GitHub repo (owner/repo, https URL, or git@ SSH URL). Default: pm78/skills",
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Override the local skills directory. Defaults to $CODEX_HOME/skills then ~/.agent/skills then ~/.codex/skills.",
    )
    parser.add_argument(
        "--layout",
        choices=["auto", "root", "skills"],
        default="auto",
        help="Where to place skills in the repo: root, skills/ subdir, or auto (use skills/ if it already exists).",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden skill directories (names starting with '.').",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Also include skills under .system/*.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="Only sync a specific skill name (repeatable). Matches by folder name.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Exclude a specific skill name (repeatable). Matches by folder name.",
    )
    parser.add_argument(
        "--author-name",
        default=None,
        help="Set git user.name for the commit (local to the temp clone).",
    )
    parser.add_argument(
        "--author-email",
        default=None,
        help="Set git user.email for the commit (local to the temp clone).",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Commit message. Default is an auto-generated sync message.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except git commit/push (still clones and copies).",
    )
    args = parser.parse_args()

    skills_dir = _discover_skills_dir(args.skills_dir)
    entries = _list_skill_entries(
        skills_dir=skills_dir,
        include_hidden=args.include_hidden,
        include_system=args.include_system,
        only=args.only,
        exclude=args.exclude,
    )

    if not entries:
        print(f"No skills found under: {skills_dir}", file=sys.stderr)
        return 1

    repo_url = _normalize_repo(args.repo)
    commit_message = args.message or (
        "Sync Codex skills "
        + datetime.now(timezone.utc).strftime("(%Y-%m-%dT%H:%M:%SZ)")
    )

    ignore = shutil.ignore_patterns(
        ".git",
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".DS_Store",
        "node_modules",
    )

    with tempfile.TemporaryDirectory(prefix="codex-skills-github-push-") as tmp:
        clone_dir = Path(tmp) / "repo"
        _run(["git", "clone", repo_url, str(clone_dir)])

        if args.layout == "root":
            target_base = clone_dir
        elif args.layout == "skills":
            target_base = clone_dir / "skills"
            target_base.mkdir(parents=True, exist_ok=True)
        else:
            target_base = (clone_dir / "skills") if (clone_dir / "skills").is_dir() else clone_dir

        print(f"Local skills dir: {skills_dir}")
        print(f"Repo: {repo_url}")
        print(f"Layout base: {target_base.relative_to(clone_dir)}")
        print("Skills to sync:")
        for entry in entries:
            print(f"- {entry.rel_path}")

        for entry in entries:
            dest_dir = target_base / entry.rel_path
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(entry.src_dir, dest_dir, symlinks=True, ignore=ignore)

        _run(["git", "add", "-A"], cwd=clone_dir)
        status = _capture(["git", "status", "--porcelain"], cwd=clone_dir)
        if not status.strip():
            print("No changes to commit.")
            return 0

        if args.dry_run:
            print("Dry run: changes staged but not committed/pushed.")
            return 0

        if args.author_name:
            _run(["git", "config", "user.name", args.author_name], cwd=clone_dir)
        if args.author_email:
            _run(["git", "config", "user.email", args.author_email], cwd=clone_dir)

        name = _git_config_get(clone_dir, "user.name")
        email = _git_config_get(clone_dir, "user.email")
        if not name or not email:
            print(
                "git author identity is not configured. "
                "Set git config user.name/user.email, or pass --author-name/--author-email.",
                file=sys.stderr,
            )
            return 2

        _run(["git", "commit", "-m", commit_message], cwd=clone_dir)
        _run(["git", "push", "origin", "HEAD"], cwd=clone_dir)

        print("Push complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
