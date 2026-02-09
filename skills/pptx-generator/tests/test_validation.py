from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_pptx as gp  # noqa: E402
from pptxgen import ConfigValidationError, validate_config  # noqa: E402


def test_validate_config_accepts_sample_config() -> None:
    sample_path = Path(__file__).resolve().parents[1] / "assets" / "sample_config.json"
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    validated, wrapped = validate_config(payload)
    assert wrapped is True
    assert isinstance(validated, dict)


def test_validate_config_rejects_non_list_slides() -> None:
    bad = {"presentation": {"slides": "not-a-list"}}
    with pytest.raises(ConfigValidationError) as exc:
        validate_config(bad)
    assert "slides is required and must be a list" in str(exc.value)


def test_validate_config_rejects_image_without_source() -> None:
    bad = {
        "presentation": {
            "slides": [
                {"layout": "title", "title": "Deck"},
                {"layout": "image", "title": "Visual"},
            ]
        }
    }
    with pytest.raises(ConfigValidationError) as exc:
        validate_config(bad)
    assert "requires either image_path" in str(exc.value)


def test_validate_config_accepts_professional_settings() -> None:
    cfg = {
        "presentation": {
            "professional": {
                "enabled": True,
                "date": {"value": "today", "format": "%B %d, %Y", "on_title": True, "in_footer": True},
                "agenda_links": True,
            },
            "slides": [{"layout": "title", "title": "Deck"}],
        }
    }
    validated, wrapped = validate_config(cfg)
    assert wrapped is True
    assert isinstance(validated, dict)


def test_validate_config_rejects_invalid_professional_type() -> None:
    bad = {"presentation": {"professional": 42, "slides": [{"layout": "title", "title": "Deck"}]}}
    with pytest.raises(ConfigValidationError) as exc:
        validate_config(bad)
    assert ".professional must be a boolean or object" in str(exc.value)


def test_professional_mode_adds_back_to_agenda_links() -> None:
    cfg = {
        "presentation": {
            "title": "Deck",
            "professional": {
                "enabled": True,
                "agenda_links": True,
                "agenda": True,
                "back_to_agenda": True,
                "date": {"value": "today"},
            },
            "footer": {"enabled": False},
            "slides": [
                {"layout": "title", "title": "Deck"},
                {"layout": "bullets", "title": "Section A", "bullets": ["Alpha"]},
                {"layout": "bullets", "title": "Section B", "bullets": ["Beta"]},
            ],
        }
    }

    generator = gp.PPTXGenerator.from_dict(cfg, theme="light")
    prs = generator.generate()

    # title + agenda + 2 sections
    assert len(prs.slides) == 4
    agenda_slide = prs.slides[1]

    for idx in (2, 3):
        slide = prs.slides[idx]
        link_shapes = [shape for shape in slide.shapes if hasattr(shape, "text") and "Back to Agenda" in shape.text]
        assert link_shapes, f"Missing back link on slide {idx + 1}"
        target = link_shapes[0].click_action.target_slide
        assert target is agenda_slide


def test_snapshot_cleanup_preserves_unrelated_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outdir = tmp_path / "snapshots"
    outdir.mkdir(parents=True, exist_ok=True)

    stale_slide = outdir / "Slide1.PNG"
    stale_slide.write_text("old", encoding="utf-8")
    keep_file = outdir / "keep.txt"
    keep_file.write_text("keep", encoding="utf-8")
    keep_png = outdir / "diagram.png"
    keep_png.write_text("external", encoding="utf-8")

    def fake_run(cmd, check):
        # Simulate export script output.
        (outdir / "Slide2.PNG").write_text("new", encoding="utf-8")
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(gp.subprocess, "run", fake_run)

    ok = gp._export_snapshots(
        pptx_path=tmp_path / "deck.pptx",
        outdir=outdir,
        fmt="png",
        method="auto",
        gallery=False,
    )

    assert ok is True
    assert not stale_slide.exists()
    assert (outdir / "Slide2.PNG").exists()
    assert keep_file.exists()
    assert keep_png.exists()
