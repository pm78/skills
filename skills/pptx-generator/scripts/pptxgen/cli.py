"""CLI orchestration for PPTX generator."""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from pptx import Presentation

from .errors import ConfigValidationError
from .qa_pipeline import export_snapshots, run_qa_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate PPTX presentations from JSON specifications")
    parser.add_argument("--config", required=True, help="Path to JSON configuration file")
    parser.add_argument("--output", required=True, help="Output PPTX file path")
    parser.add_argument("--template", default=None, help="Optional path to a .pptx template file")
    parser.add_argument(
        "--assets-dir",
        default=None,
        help="Directory to write generated image assets (default: <output-stem>-assets next to the PPTX)",
    )
    parser.add_argument(
        "--keep-template-slides",
        action="store_true",
        help="Keep any existing slides found in the template (default: remove them)",
    )
    parser.add_argument(
        "--theme",
        default=None,
        choices=["dark", "light", "template"],
        help='Color theme (default: "dark", or "template" when using --template)',
    )
    parser.add_argument(
        "--list-layouts",
        action="store_true",
        help="Print slide layout indices/names for the chosen template and exit",
    )
    parser.add_argument("--snapshots-dir", default=None, help="Optional output directory for slide PNG/JPG snapshots")
    parser.add_argument(
        "--snapshots-format",
        default="png",
        choices=["png", "jpg", "jpeg"],
        help="Snapshot image format (default: png)",
    )
    parser.add_argument(
        "--snapshots-method",
        default="auto",
        choices=["auto", "powerpoint", "libreoffice"],
        help="Snapshot export method (default: auto)",
    )
    parser.add_argument("--snapshots-gallery", action="store_true", help="Also write an index.html gallery")
    parser.add_argument("--qa", action="store_true", help="Run automatic readability/layout QA loop after generation")
    parser.add_argument("--qa-passes", type=int, default=2, help="Max QA passes (default: 2)")
    parser.add_argument("--qa-max-bullets", type=int, default=5, help="Max bullets per slide before splitting")
    parser.add_argument("--qa-max-column-lines", type=int, default=8, help="Max lines per column before splitting")
    parser.add_argument(
        "--qa-config-out",
        default=None,
        help="Optional path to write the QA-adjusted config JSON (default: next to output PPTX when --qa)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full traceback for unexpected errors",
    )
    return parser


def run_cli(generator_cls) -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        default_template = Path(__file__).resolve().parents[2] / "assets" / "worldline-template.pptx"
        template_path = args.template
        theme = args.theme or ("template" if template_path else "dark")

        if theme == "template" and not template_path and default_template.exists():
            template_path = str(default_template)

        if args.list_layouts:
            if not template_path:
                raise SystemExit("No template selected. Pass --template or ensure assets/worldline-template.pptx exists.")
            prs = Presentation(str(template_path))
            for i, layout in enumerate(prs.slide_layouts):
                print(f"{i}\t{getattr(layout, 'name', '')}")
            return

        output_path = Path(args.output).resolve()
        config_path = Path(args.config).resolve()
        assets_dir = Path(args.assets_dir).resolve() if args.assets_dir else output_path.parent / f"{output_path.stem}-assets"

        if args.qa:
            snapshots_dir = (
                Path(args.snapshots_dir).resolve()
                if args.snapshots_dir
                else output_path.parent / f"{output_path.stem}-slides"
            )
            qa_config_out = (
                Path(args.qa_config_out).resolve()
                if args.qa_config_out
                else output_path.parent / f"{output_path.stem}.qa.json"
            )
            run_qa_pipeline(
                generator_cls=generator_cls,
                config_path=config_path,
                output_path=output_path,
                theme=theme,
                template_path=template_path,
                keep_template_slides=args.keep_template_slides,
                assets_dir=assets_dir,
                snapshots_dir=snapshots_dir,
                snapshots_format=args.snapshots_format,
                snapshots_method=args.snapshots_method,
                snapshots_gallery=args.snapshots_gallery,
                qa_passes=args.qa_passes,
                qa_max_bullets=args.qa_max_bullets,
                qa_max_column_lines=args.qa_max_column_lines,
                qa_config_out=qa_config_out,
            )
            return

        generator = generator_cls(
            str(config_path),
            theme=theme,
            template_path=template_path,
            assets_dir=str(assets_dir),
            keep_template_slides=args.keep_template_slides,
        )
        generator.generate()
        saved = generator.save(str(output_path))

        if args.snapshots_dir:
            export_snapshots(
                pptx_path=saved,
                outdir=Path(args.snapshots_dir).resolve(),
                fmt=args.snapshots_format,
                method=args.snapshots_method,
                gallery=args.snapshots_gallery,
            )
    except ConfigValidationError as e:
        raise SystemExit(str(e)) from e
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        raise SystemExit(f"PPTX generation failed: {e}") from e
