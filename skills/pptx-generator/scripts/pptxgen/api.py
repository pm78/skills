"""Public API helpers for programmatic PPTX generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def generate_pptx_from_config(
    *,
    generator_cls,
    config_path: Path,
    output_path: Path,
    theme: str = "template",
    template_path: Optional[str] = None,
    assets_dir: Optional[Path] = None,
    keep_template_slides: bool = False,
) -> Path:
    """Generate a PPTX from a validated config file via the provided generator class."""
    generator = generator_cls(
        str(config_path),
        theme=theme,
        template_path=template_path,
        assets_dir=str(assets_dir) if assets_dir else None,
        keep_template_slides=keep_template_slides,
    )
    generator.generate()
    return generator.save(str(output_path))


def write_config(config: Dict[str, Any], path: Path) -> Path:
    """Write a JSON config to disk and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
