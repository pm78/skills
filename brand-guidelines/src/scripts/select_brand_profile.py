#!/usr/bin/env python3
"""Select a brand profile by brand id or name from preset and custom profile files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    if "brand_id" not in data and "brand_name" not in data:
        raise ValueError(f"Missing brand_id/brand_name in {path}")
    return data


def collect_profiles(preset_dir: Path, extra_files: list[Path]) -> list[tuple[Path, dict]]:
    profiles: list[tuple[Path, dict]] = []

    if preset_dir.exists():
        for candidate in sorted(preset_dir.glob("*.json")):
            profiles.append((candidate, load_json(candidate)))

    for file_path in extra_files:
        profiles.append((file_path, load_json(file_path)))

    return profiles


def profile_aliases(profile: dict) -> set[str]:
    aliases = set()

    brand_id = profile.get("brand_id")
    brand_name = profile.get("brand_name")

    if brand_id:
        aliases.add(brand_id.lower())
        aliases.add(slugify(brand_id))

    if brand_name:
        aliases.add(brand_name.lower())
        aliases.add(slugify(brand_name))

    return {a for a in aliases if a}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset-dir",
        default=str(Path(__file__).resolve().parent.parent / "assets" / "profiles"),
        help="Directory with preset profile JSON files",
    )
    parser.add_argument("--profile", action="append", default=[], help="Additional profile JSON file")
    parser.add_argument("--brand", help="Brand selector (id or name)")
    parser.add_argument("--list", action="store_true", help="List available brands")
    parser.add_argument("--allow-partial", action="store_true", help="Allow partial name match")
    parser.add_argument("--out", help="Write selected profile JSON to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preset_dir = Path(args.preset_dir)
    extra_files = [Path(p) for p in args.profile]

    profiles = collect_profiles(preset_dir, extra_files)
    if not profiles:
        print("No profiles found", file=sys.stderr)
        return 1

    if args.list:
        for source, profile in profiles:
            brand_id = profile.get("brand_id", "")
            brand_name = profile.get("brand_name", "")
            print(f"{brand_id}\t{brand_name}\t{source}")
        return 0

    if not args.brand:
        print("Pass --brand (or use --list)", file=sys.stderr)
        return 2

    needle = args.brand.strip().lower()
    needle_slug = slugify(needle)

    exact_matches: list[tuple[Path, dict]] = []
    partial_matches: list[tuple[Path, dict]] = []

    for source, profile in profiles:
        aliases = profile_aliases(profile)
        if needle in aliases or needle_slug in aliases:
            exact_matches.append((source, profile))
            continue

        if args.allow_partial:
            hay = " ".join(aliases)
            if needle in hay or needle_slug in hay:
                partial_matches.append((source, profile))

    candidates = exact_matches or partial_matches

    if len(candidates) == 0:
        print(f"No profile matched '{args.brand}'. Run with --list to inspect options.", file=sys.stderr)
        return 1

    if len(candidates) > 1:
        print(f"Ambiguous brand selector '{args.brand}'. Matches:", file=sys.stderr)
        for source, profile in candidates:
            print(f"- {profile.get('brand_id')} ({profile.get('brand_name')}): {source}", file=sys.stderr)
        return 1

    selected_source, selected_profile = candidates[0]
    selected_profile = dict(selected_profile)
    selected_profile["selected_from"] = str(selected_source)

    output = json.dumps(selected_profile, indent=2, ensure_ascii=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"Selected profile written to {out_path}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
