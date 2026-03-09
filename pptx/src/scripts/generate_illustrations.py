#!/usr/bin/env python3
"""Generate slide illustration assets via the imagegen skill.

The script reads a JSON spec, invokes imagegen's CLI per slide, and writes
an illustration map that can be consumed by pptxgenjs or template workflows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_IMAGEGEN_SCRIPT = Path("/home/pascal/.agent/skills/imagegen/scripts/image_gen.py")
DEFAULT_ENV_FILE = Path("/home/pascal/.agent/skills/.env")

IMAGEGEN_OPTIONS = [
    "model",
    "size",
    "quality",
    "background",
    "output_format",
    "output_compression",
    "moderation",
    "use_case",
    "scene",
    "subject",
    "style",
    "composition",
    "lighting",
    "palette",
    "materials",
    "text",
    "constraints",
    "negative",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate PPTX illustration assets with imagegen."
    )
    parser.add_argument("--spec", required=True, help="Path to JSON spec file.")
    parser.add_argument(
        "--deck",
        default="deck",
        help="Deck slug used under --out-dir (overridden by spec.deck if set).",
    )
    parser.add_argument(
        "--out-dir",
        default="output/imagegen",
        help="Base output directory for generated assets.",
    )
    parser.add_argument(
        "--python",
        dest="python_exe",
        default=sys.executable,
        help="Python executable used to run imagegen.",
    )
    parser.add_argument(
        "--imagegen-script",
        default=str(DEFAULT_IMAGEGEN_SCRIPT),
        help="Path to imagegen/scripts/image_gen.py",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Optional .env file used if OPENAI_API_KEY is not already set.",
    )
    parser.add_argument(
        "--map-out",
        help="Output path for generated illustration map JSON. "
        "Defaults to <out-dir>/<deck>/illustration-map.json",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing remaining slides when one generation fails.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without calling the Image API.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Spec file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Spec file is not valid JSON: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise SystemExit("Spec root must be a JSON object.")
    return data


def _normalize_env_value(value: str) -> str:
    cleaned = value.strip().strip('"').strip("'")
    return cleaned.replace("\r", "")


def _read_openai_api_key(env_file: Path) -> str | None:
    if not env_file.exists():
        return None

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "OPENAI_API_KEY":
            normalized = _normalize_env_value(value)
            return normalized or None
    return None


def _pick(entry: dict[str, Any], defaults: dict[str, Any], key: str) -> Any:
    if key in entry:
        return entry[key]
    return defaults.get(key)


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "asset"


def _image_ext(entry: dict[str, Any], defaults: dict[str, Any]) -> str:
    output_format = str(_pick(entry, defaults, "output_format") or "png").lower()
    if output_format in {"jpg", "jpeg"}:
        return ".jpg"
    if output_format == "webp":
        return ".webp"
    return ".png"


def _asset_filename(
    entry: dict[str, Any], defaults: dict[str, Any], index: int, slide_label: str
) -> str:
    ext = _image_ext(entry, defaults)
    explicit = entry.get("filename")
    if explicit:
        filename = str(explicit).strip()
        if Path(filename).suffix:
            return filename
        return f"{filename}{ext}"

    asset_name = entry.get("asset_name")
    if asset_name:
        return f"{_slugify(str(asset_name))}{ext}"

    return f"slide-{slide_label}-{index:02d}{ext}"


def _build_generate_cmd(
    python_exe: str,
    imagegen_script: Path,
    prompt: str,
    out_file: Path,
    entry: dict[str, Any],
    defaults: dict[str, Any],
) -> list[str]:
    cmd = [
        python_exe,
        str(imagegen_script),
        "generate",
        "--prompt",
        prompt,
        "--out",
        str(out_file),
    ]

    for option in IMAGEGEN_OPTIONS:
        value = _pick(entry, defaults, option)
        if value is None or value == "":
            continue
        cmd.extend([f"--{option.replace('_', '-')}", str(value)])

    augment = _pick(entry, defaults, "augment")
    if augment is True:
        cmd.append("--augment")
    elif augment is False:
        cmd.append("--no-augment")

    return cmd


def _validate_slides(spec: dict[str, Any]) -> list[dict[str, Any]]:
    slides = spec.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SystemExit("Spec must include a non-empty 'slides' list.")

    for idx, entry in enumerate(slides, start=1):
        if not isinstance(entry, dict):
            raise SystemExit(f"slides[{idx}] must be an object.")
        prompt = entry.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"slides[{idx}] must include a non-empty 'prompt'.")
    return slides


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec).expanduser()
    spec = _read_json(spec_path)
    slides = _validate_slides(spec)

    defaults = spec.get("defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise SystemExit("'defaults' must be an object when provided.")

    deck = str(spec.get("deck") or args.deck).strip() or "deck"
    output_dir = Path(args.out_dir).expanduser() / deck
    output_dir.mkdir(parents=True, exist_ok=True)

    imagegen_script = Path(args.imagegen_script).expanduser()
    if not imagegen_script.exists():
        raise SystemExit(f"imagegen script not found: {imagegen_script}")

    env = dict(os.environ)
    if not env.get("OPENAI_API_KEY"):
        key = _read_openai_api_key(Path(args.env_file).expanduser())
        if key:
            env["OPENAI_API_KEY"] = key

    if not args.dry_run and not env.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is missing. Set it in the environment or provide --env-file."
        )

    generated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for index, entry in enumerate(slides, start=1):
        prompt = str(entry["prompt"]).strip()
        slide_value = entry.get("slide", index)
        slide_label = _slugify(str(slide_value))
        filename = _asset_filename(entry, defaults, index=index, slide_label=slide_label)
        out_file = output_dir / filename

        cmd = _build_generate_cmd(
            python_exe=args.python_exe,
            imagegen_script=imagegen_script,
            prompt=prompt,
            out_file=out_file,
            entry=entry,
            defaults=defaults,
        )

        print(f"[{index}/{len(slides)}] slide={slide_value} -> {out_file}")
        if args.dry_run:
            print("  DRY RUN:", " ".join(cmd))
            generated.append(
                {
                    "slide": slide_value,
                    "path": str(out_file),
                    "prompt": prompt,
                    "placement": entry.get("placement"),
                    "status": "dry-run",
                }
            )
            continue

        run = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if run.returncode == 0:
            generated.append(
                {
                    "slide": slide_value,
                    "path": str(out_file),
                    "prompt": prompt,
                    "placement": entry.get("placement"),
                    "status": "generated",
                }
            )
            print("  OK")
            continue

        error_text = (run.stderr or run.stdout or "").strip()
        failed_entry = {
            "slide": slide_value,
            "path": str(out_file),
            "prompt": prompt,
            "error": error_text,
        }
        failed.append(failed_entry)
        print("  FAILED")
        if error_text:
            print(" ", error_text.splitlines()[-1])
        if not args.continue_on_error:
            break

    map_out = Path(args.map_out).expanduser() if args.map_out else output_dir / "illustration-map.json"
    map_out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "deck": deck,
        "output_dir": str(output_dir),
        "generated": generated,
        "failed": failed,
    }
    map_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote map: {map_out}")

    if failed:
        print(f"Completed with failures: {len(failed)} failed, {len(generated)} generated.")
        return 1

    if args.dry_run:
        print(f"Completed dry run: {len(generated)} jobs planned.")
        return 0

    print(f"Completed: {len(generated)} generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
