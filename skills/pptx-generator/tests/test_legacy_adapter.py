from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pptxgen import adapt_legacy_pptx_spec  # noqa: E402


def test_adapt_legacy_spec_maps_title_and_body() -> None:
    payload = {
        "slides": [
            {"layout": "title_and_body", "title": "Executive Summary", "bullets": ["A", "B"]},
        ]
    }

    out = adapt_legacy_pptx_spec(payload, document_title="Proposal")
    slides = out["presentation"]["slides"]

    assert slides[0]["layout"] == "title"
    assert slides[1]["layout"] == "bullets"
    assert slides[1]["title"] == "Executive Summary"
    assert slides[1]["bullets"] == ["A", "B"]
