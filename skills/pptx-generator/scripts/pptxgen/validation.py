"""Config validation for the PPTX generator JSON input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from .errors import ConfigValidationError

_ALLOWED_LAYOUTS = {
    "title",
    "bullets",
    "two-column",
    "chart",
    "image",
    "architecture",
    "workflow",
    "kpi-cards",
    "infographic",
    "blank",
}


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _ensure_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_slide(slide: Dict[str, Any], idx: int, issues: list[str]) -> None:
    prefix = f"slides[{idx}]"
    layout = slide.get("layout", "blank")

    if not isinstance(layout, str) or not layout.strip():
        issues.append(f"{prefix}.layout must be a non-empty string")
        return

    if layout not in _ALLOWED_LAYOUTS:
        allowed = ", ".join(sorted(_ALLOWED_LAYOUTS))
        issues.append(f"{prefix}.layout '{layout}' is unsupported (supported: {allowed})")
        return

    if "template_layout" in slide and not isinstance(slide.get("template_layout"), str):
        issues.append(f"{prefix}.template_layout must be a string when provided")

    if "template_layout_index" in slide and not isinstance(slide.get("template_layout_index"), int):
        issues.append(f"{prefix}.template_layout_index must be an integer when provided")

    if layout == "title":
        if not _is_non_empty_str(slide.get("title")):
            issues.append(f"{prefix}.title is required for layout='title' and must be a non-empty string")
        if "subtitle" in slide and not isinstance(slide.get("subtitle"), str):
            issues.append(f"{prefix}.subtitle must be a string when provided")
        return

    if layout == "bullets":
        if not _is_non_empty_str(slide.get("title")):
            issues.append(f"{prefix}.title is required for layout='bullets' and must be a non-empty string")
        bullets = slide.get("bullets")
        if not isinstance(bullets, list):
            issues.append(f"{prefix}.bullets must be a list of strings")
        elif not bullets:
            issues.append(f"{prefix}.bullets must contain at least one bullet")
        elif not _ensure_list_of_str(bullets):
            issues.append(f"{prefix}.bullets must contain only strings")
        return

    if layout == "two-column":
        for field in ("left", "right"):
            if not isinstance(slide.get(field), str):
                issues.append(f"{prefix}.{field} is required for layout='two-column' and must be a string")
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        return

    if layout == "chart":
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        if "categories" in slide and not _ensure_list_of_str(slide.get("categories")):
            issues.append(f"{prefix}.categories must be a list of strings when provided")
        series = slide.get("series")
        if series is not None:
            if not isinstance(series, list):
                issues.append(f"{prefix}.series must be a list when provided")
            else:
                for s_idx, series_item in enumerate(series):
                    sp = f"{prefix}.series[{s_idx}]"
                    if not isinstance(series_item, dict):
                        issues.append(f"{sp} must be an object with name + values")
                        continue
                    if "name" in series_item and not isinstance(series_item.get("name"), str):
                        issues.append(f"{sp}.name must be a string when provided")
                    values = series_item.get("values")
                    if values is None:
                        issues.append(f"{sp}.values is required")
                    elif not isinstance(values, list):
                        issues.append(f"{sp}.values must be a list of numbers")
        return

    if layout == "image":
        has_image_path = _is_non_empty_str(slide.get("image_path"))
        has_image_gen = isinstance(slide.get("image_gen"), dict)
        if not has_image_path and not has_image_gen:
            issues.append(f"{prefix} requires either image_path (string) or image_gen (object)")
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        if "caption" in slide and not isinstance(slide.get("caption"), str):
            issues.append(f"{prefix}.caption must be a string when provided")
        return

    if layout == "workflow":
        steps = slide.get("steps")
        if not isinstance(steps, list) or not steps:
            issues.append(f"{prefix}.steps is required for layout='workflow' and must be a non-empty list")
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        return

    if layout in {"kpi-cards", "infographic"}:
        cards = slide.get("cards") if isinstance(slide.get("cards"), list) else slide.get("items")
        if not isinstance(cards, list) or not cards:
            issues.append(f"{prefix} requires cards (or items) as a non-empty list")
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        return

    if layout == "architecture":
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")
        return

    if layout == "blank":
        if "title" in slide and not isinstance(slide.get("title"), str):
            issues.append(f"{prefix}.title must be a string when provided")


def _check_palette(palette: Any, issues: list[str], prefix: str) -> None:
    if palette is None:
        return
    if not isinstance(palette, dict):
        issues.append(f"{prefix}.palette must be an object when provided")
        return
    for section in ("diagram", "footer", "image"):
        section_val = palette.get(section)
        if section_val is not None and not isinstance(section_val, dict):
            issues.append(f"{prefix}.palette.{section} must be an object when provided")


def _check_presentation(presentation: Dict[str, Any], issues: list[str], prefix: str) -> None:
    for field in ("title", "author", "confidentiality"):
        value = presentation.get(field)
        if value is not None and not isinstance(value, str):
            issues.append(f"{prefix}.{field} must be a string when provided")

    agenda = presentation.get("agenda")
    if agenda is not None and not isinstance(agenda, (bool, dict)):
        issues.append(f"{prefix}.agenda must be a boolean or object when provided")

    footer = presentation.get("footer")
    if footer is not None and not isinstance(footer, (bool, dict)):
        issues.append(f"{prefix}.footer must be a boolean or object when provided")

    _check_palette(presentation.get("palette"), issues, prefix)

    slides = presentation.get("slides")
    if not isinstance(slides, list):
        issues.append(f"{prefix}.slides is required and must be a list")
        return
    if not slides:
        issues.append(f"{prefix}.slides must contain at least one slide")
        return

    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            issues.append(f"{prefix}.slides[{idx}] must be an object")
            continue
        _check_slide(slide, idx, issues)


def validate_config(config: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Validate a config dict and return (config, wrapped)."""
    if not isinstance(config, dict):
        raise ConfigValidationError(["Root JSON value must be an object"])

    wrapped = "presentation" in config
    presentation = config.get("presentation") if wrapped else config

    if not isinstance(presentation, dict):
        raise ConfigValidationError(["'presentation' must be an object"])

    issues: list[str] = []
    _check_presentation(presentation, issues, "presentation" if wrapped else "root")

    if issues:
        raise ConfigValidationError(issues)

    return config, wrapped


def validate_config_file(config_path: Path) -> tuple[Dict[str, Any], bool]:
    """Load and validate a JSON config file."""
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigValidationError([f"Config file not found: {config_path}"]) from exc

    try:
        data: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError([f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]) from exc

    return validate_config(data)
