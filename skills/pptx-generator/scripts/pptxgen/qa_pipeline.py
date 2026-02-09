"""QA and snapshot pipeline helpers for PPTX generation."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .validation import validate_config_file


def _load_config(config_path: Path) -> tuple[Dict[str, Any], bool]:
    return validate_config_file(config_path)


def _get_slides(config: Dict[str, Any]) -> list[Dict[str, Any]]:
    presentation = config.get("presentation", config)
    slides = presentation.get("slides", [])
    if not isinstance(slides, list):
        raise ValueError("Invalid config: presentation.slides must be a list")
    return slides


def _set_slides(config: Dict[str, Any], slides: list[Dict[str, Any]], *, wrapped: bool) -> None:
    if wrapped:
        config.setdefault("presentation", {})["slides"] = slides
    else:
        config["slides"] = slides


def _chunk(items: list[Any], size: int) -> list[list[Any]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _split_bullets_slide(slide: Dict[str, Any], *, max_bullets: int) -> tuple[list[Dict[str, Any]], list[str]]:
    bullets = [str(b).strip() for b in slide.get("bullets", []) if str(b).strip()]
    if len(bullets) <= max_bullets:
        return [slide], []

    parts = _chunk(bullets, max_bullets)
    total = len(parts)
    new_slides: list[Dict[str, Any]] = []
    changes: list[str] = [f"Split bullets slide '{slide.get('title','')}' into {total} slides"]

    for idx, part in enumerate(parts, start=1):
        new_slide = dict(slide)
        new_slide["bullets"] = part
        new_slide.pop("template_layout", None)
        new_slide.pop("template_layout_index", None)
        if idx > 1:
            new_slide.pop("id", None)
            if new_slide.get("title"):
                new_slide["title"] = f"{new_slide['title']} ({idx}/{total})"
        new_slides.append(new_slide)

    return new_slides, changes


def _split_two_column_slide(
    slide: Dict[str, Any], *, max_lines: int
) -> tuple[list[Dict[str, Any]], list[str]]:
    left = str(slide.get("left", "") or "")
    right = str(slide.get("right", "") or "")
    left = left.replace("\r\n", "\n").replace("\\n", "\n")
    right = right.replace("\r\n", "\n").replace("\\n", "\n")

    left_lines = [line for line in left.split("\n") if line != ""]
    right_lines = [line for line in right.split("\n") if line != ""]
    if max(len(left_lines), len(right_lines)) <= max_lines:
        return [slide], []

    max_lines = max(2, max_lines)
    body_chunk = max_lines - 1

    left_header = left_lines[0] if left_lines else ""
    right_header = right_lines[0] if right_lines else ""
    left_body = left_lines[1:] if len(left_lines) > 1 else []
    right_body = right_lines[1:] if len(right_lines) > 1 else []

    chunks = max(
        1,
        math.ceil(len(left_body) / body_chunk) if left_body else 1,
        math.ceil(len(right_body) / body_chunk) if right_body else 1,
    )

    changes = [f"Split two-column slide '{slide.get('title','')}' into {chunks} slides"]
    new_slides: list[Dict[str, Any]] = []

    for idx in range(chunks):
        lb = left_body[idx * body_chunk : (idx + 1) * body_chunk]
        rb = right_body[idx * body_chunk : (idx + 1) * body_chunk]

        new_slide = dict(slide)
        new_slide.pop("template_layout", None)
        new_slide.pop("template_layout_index", None)
        new_slide["left"] = "\n".join([left_header, *lb]).strip()
        new_slide["right"] = "\n".join([right_header, *rb]).strip()
        if idx > 0:
            new_slide.pop("id", None)
            if new_slide.get("title"):
                new_slide["title"] = f"{new_slide['title']} ({idx+1}/{chunks})"
        new_slides.append(new_slide)

    return new_slides, changes


def _split_workflow_slide(slide: Dict[str, Any], *, max_steps: int) -> tuple[list[Dict[str, Any]], list[str]]:
    steps = slide.get("steps") or []
    if not isinstance(steps, list):
        return [slide], []
    if len(steps) <= max_steps:
        return [slide], []

    parts = _chunk(steps, max_steps)
    total = len(parts)
    new_slides: list[Dict[str, Any]] = []
    changes: list[str] = [f"Split workflow slide '{slide.get('title','')}' into {total} slides"]

    for idx, part in enumerate(parts, start=1):
        new_slide = dict(slide)
        new_slide["steps"] = part
        new_slide.pop("template_layout", None)
        new_slide.pop("template_layout_index", None)
        if idx > 1:
            new_slide.pop("id", None)
            if new_slide.get("title"):
                new_slide["title"] = f"{new_slide['title']} ({idx}/{total})"
        new_slides.append(new_slide)

    return new_slides, changes


def _split_kpi_cards_slide(
    slide: Dict[str, Any], *, max_cards: int
) -> tuple[list[Dict[str, Any]], list[str]]:
    cards_key = "cards" if isinstance(slide.get("cards"), list) else ("items" if isinstance(slide.get("items"), list) else None)
    if not cards_key:
        return [slide], []

    cards = slide.get(cards_key) or []
    if not isinstance(cards, list):
        return [slide], []
    if len(cards) <= max_cards:
        return [slide], []

    parts = _chunk(cards, max_cards)
    total = len(parts)
    new_slides: list[Dict[str, Any]] = []
    changes: list[str] = [f"Split {slide.get('layout','kpi-cards')} slide '{slide.get('title','')}' into {total} slides"]

    for idx, part in enumerate(parts, start=1):
        new_slide = dict(slide)
        new_slide[cards_key] = part
        new_slide.pop("template_layout", None)
        new_slide.pop("template_layout_index", None)
        if idx > 1:
            new_slide.pop("id", None)
            if new_slide.get("title"):
                new_slide["title"] = f"{new_slide['title']} ({idx}/{total})"
        new_slides.append(new_slide)

    return new_slides, changes


def _parse_slide_number(path: Path) -> Optional[int]:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else None


def _analyze_slide_image(image_path: Path) -> Optional[Dict[str, float]]:
    try:
        from PIL import Image
    except Exception:
        return None

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    img = img.resize((max(240, img.width // 6), max(135, img.height // 6)))
    w, h = img.size
    px = img.load()

    patch = max(2, int(min(w, h) * 0.06))
    samples: list[Tuple[int, int, int]] = []
    for y in range(patch):
        for x in range(patch):
            samples.append(px[x, y])
            samples.append(px[w - 1 - x, y])
            samples.append(px[x, h - 1 - y])
            samples.append(px[w - 1 - x, h - 1 - y])
    if not samples:
        return None

    samples.sort(key=lambda c: (c[0], c[1], c[2]))
    bg = samples[len(samples) // 2]

    def is_content(rgb: Tuple[int, int, int]) -> bool:
        dr = rgb[0] - bg[0]
        dg = rgb[1] - bg[1]
        db = rgb[2] - bg[2]
        return (dr * dr + dg * dg + db * db) > 25 * 25

    margin_x = int(w * 0.08)
    margin_y = int(h * 0.08)
    x0, x1 = margin_x, w - margin_x
    y0, y1 = margin_y, h - margin_y
    if x1 <= x0 or y1 <= y0:
        return None

    inner_total = (x1 - x0) * (y1 - y0)
    inner_ink = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if is_content(px[x, y]):
                inner_ink += 1

    band_h = max(1, int(h * 0.06))
    bottom_total = (x1 - x0) * band_h
    bottom_ink = 0
    for y in range(h - band_h, h):
        for x in range(x0, x1):
            if is_content(px[x, y]):
                bottom_ink += 1

    return {
        "inner_coverage": inner_ink / inner_total,
        "bottom_coverage": bottom_ink / bottom_total,
    }


def export_snapshots(
    *,
    pptx_path: Path,
    outdir: Path,
    fmt: str,
    method: str,
    gallery: bool,
) -> bool:
    removable_patterns = (
        "Slide*.png",
        "Slide*.PNG",
        "Slide*.jpg",
        "Slide*.JPG",
        "Slide*.jpeg",
        "Slide*.JPEG",
    )
    outdir.mkdir(parents=True, exist_ok=True)
    for pattern in removable_patterns:
        for existing in outdir.glob(pattern):
            if existing.is_file():
                try:
                    existing.unlink()
                except Exception:
                    pass
    gallery_file = outdir / "index.html"
    if gallery_file.exists():
        try:
            gallery_file.unlink()
        except Exception:
            pass

    export_script = Path(__file__).resolve().parent.parent / "export_slides.py"
    cmd = [
        sys.executable,
        str(export_script),
        "--pptx",
        str(pptx_path),
        "--outdir",
        str(outdir),
        "--format",
        fmt,
        "--method",
        method,
    ]
    if gallery:
        cmd.append("--gallery")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        msg = stderr or str(e)
        print(f"⚠️  Snapshot export failed (continuing without images): {msg}", file=sys.stderr)
        return False


def _auto_fix_slides(
    slides: list[Dict[str, Any]],
    *,
    max_bullets: int,
    max_column_lines: int,
    image_metrics: Optional[Dict[int, Dict[str, float]]],
) -> tuple[list[Dict[str, Any]], list[str]]:
    new_slides: list[Dict[str, Any]] = []
    changes: list[str] = []

    for idx, slide in enumerate(slides, start=1):
        layout = slide.get("layout", "blank")

        metrics = (image_metrics or {}).get(idx)
        dense = bool(metrics and metrics.get("inner_coverage", 0.0) > 0.22)
        bottom_touch = bool(metrics and metrics.get("bottom_coverage", 0.0) > 0.10)

        if layout == "bullets":
            bullets = [str(b).strip() for b in (slide.get("bullets", []) or []) if str(b).strip()]
            total_chars = sum(len(b) for b in bullets)
            max_bullet_chars = max((len(b) for b in bullets), default=0)
            text_dense = total_chars > 650 or max_bullet_chars > 170

            effective_max = max_bullets
            if dense or bottom_touch or text_dense:
                effective_max = max(3, max_bullets - 1)
            if total_chars > 900 or max_bullet_chars > 220:
                effective_max = max(2, max_bullets - 2)

            split, split_changes = _split_bullets_slide(slide, max_bullets=effective_max)
            new_slides.extend(split)
            changes.extend(split_changes)
            continue

        if layout == "two-column":
            left = str(slide.get("left", "") or "")
            right = str(slide.get("right", "") or "")
            total_chars = len(left) + len(right)

            effective_lines = max_column_lines
            if dense or bottom_touch or total_chars > 900:
                effective_lines = max(4, max_column_lines - 1)
            if total_chars > 1200:
                effective_lines = max(4, max_column_lines - 2)

            split, split_changes = _split_two_column_slide(slide, max_lines=effective_lines)
            new_slides.extend(split)
            changes.extend(split_changes)
            continue

        if layout == "workflow":
            steps = slide.get("steps") or []
            step_text = ""
            if isinstance(steps, list):
                for s in steps:
                    if isinstance(s, str):
                        step_text += s
                    elif isinstance(s, dict):
                        step_text += str(s.get("title") or s.get("text") or "")
                        step_text += str(s.get("subtitle") or s.get("note") or "")

            effective_steps = 10
            if dense or bottom_touch or len(step_text) > 550:
                effective_steps = 8
            if len(step_text) > 800:
                effective_steps = 6

            split, split_changes = _split_workflow_slide(slide, max_steps=effective_steps)
            new_slides.extend(split)
            changes.extend(split_changes)
            continue

        if layout in {"kpi-cards", "infographic"}:
            cards = slide.get("cards") if isinstance(slide.get("cards"), list) else slide.get("items")
            cards_len = len(cards) if isinstance(cards, list) else 0
            effective_cards = 9
            if dense or bottom_touch or cards_len > 9:
                effective_cards = 6
            split, split_changes = _split_kpi_cards_slide(slide, max_cards=effective_cards)
            new_slides.extend(split)
            changes.extend(split_changes)
            continue

        new_slides.append(slide)

    return new_slides, changes


def run_qa_pipeline(
    *,
    generator_cls,
    config_path: Path,
    output_path: Path,
    theme: str,
    template_path: Optional[str],
    keep_template_slides: bool,
    assets_dir: Optional[Path],
    snapshots_dir: Path,
    snapshots_format: str,
    snapshots_method: str,
    snapshots_gallery: bool,
    qa_passes: int,
    qa_max_bullets: int,
    qa_max_column_lines: int,
    qa_config_out: Optional[Path],
) -> None:
    config, wrapped = _load_config(config_path)

    last_changes: list[str] = []
    changes_in_last_pass = False
    for pass_idx in range(1, max(1, qa_passes) + 1):
        changes_in_last_pass = False
        generator = generator_cls.from_dict(
            config,
            theme=theme,
            template_path=template_path,
            assets_dir=str(assets_dir) if assets_dir else None,
            keep_template_slides=keep_template_slides,
            config_dir=config_path.parent,
        )
        generator.generate()
        generator.save(str(output_path))

        snapshots_ok = export_snapshots(
            pptx_path=output_path,
            outdir=snapshots_dir,
            fmt=snapshots_format,
            method=snapshots_method,
            gallery=snapshots_gallery,
        )

        image_metrics: Optional[Dict[int, Dict[str, float]]] = None
        if snapshots_ok:
            image_metrics = {}
            fmt = "jpg" if snapshots_format.lower() == "jpeg" else snapshots_format.lower()
            for img in snapshots_dir.glob(f"*.{fmt}"):
                num = _parse_slide_number(img)
                if not num:
                    continue
                analysis = _analyze_slide_image(img)
                if analysis:
                    image_metrics[num] = analysis

        slides = _get_slides(config)
        fixed_slides, changes = _auto_fix_slides(
            slides,
            max_bullets=qa_max_bullets,
            max_column_lines=qa_max_column_lines,
            image_metrics=image_metrics,
        )

        if not changes:
            if pass_idx == 1:
                print("✅ QA: no layout fixes needed")
            else:
                print(f"✅ QA: stabilized after pass {pass_idx}")
            break

        last_changes = changes
        changes_in_last_pass = True
        _set_slides(config, fixed_slides, wrapped=wrapped)
        print(f"🛠️  QA pass {pass_idx}: applied {len(changes)} fix(es)")
        for change in changes[:12]:
            print(f"  - {change}")

    if changes_in_last_pass:
        generator = generator_cls.from_dict(
            config,
            theme=theme,
            template_path=template_path,
            assets_dir=str(assets_dir) if assets_dir else None,
            keep_template_slides=keep_template_slides,
            config_dir=config_path.parent,
        )
        generator.generate()
        generator.save(str(output_path))
        export_snapshots(
            pptx_path=output_path,
            outdir=snapshots_dir,
            fmt=snapshots_format,
            method=snapshots_method,
            gallery=snapshots_gallery,
        )

    if last_changes and qa_config_out:
        qa_config_out.parent.mkdir(parents=True, exist_ok=True)
        qa_config_out.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"📝 QA config written to {qa_config_out}")
