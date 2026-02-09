"""Compatibility adapters for legacy PPTX specs."""

from __future__ import annotations

from typing import Any, Dict, List


def normalize_legacy_layout(layout: str) -> str:
    """Map legacy layout names to skill-supported layout names."""
    normalized = str(layout or "").strip().lower()
    if normalized in {"title_and_body", "title-and-body", "title-body", "content"}:
        return "bullets"
    if normalized in {"kpi_cards", "kpi"}:
        return "kpi-cards"
    if normalized in {"two_column", "two-columns", "two columns"}:
        return "two-column"
    return normalized or "blank"


def adapt_legacy_pptx_spec(
    pptx_spec: Dict[str, Any],
    *,
    document_title: str,
    confidentiality: str = "Confidential",
) -> Dict[str, Any]:
    """Convert an existing exports.pptx_spec payload to generator presentation schema."""
    slides_in = pptx_spec.get("slides")
    if not isinstance(slides_in, list):
        slides_in = []

    slides_out: List[Dict[str, Any]] = []
    for slide in slides_in:
        if not isinstance(slide, dict):
            continue

        layout = normalize_legacy_layout(str(slide.get("layout") or "blank"))
        title = str(slide.get("title") or "").strip()

        if layout == "title":
            slides_out.append(
                {
                    "layout": "title",
                    "title": title or document_title,
                    "subtitle": str(slide.get("subtitle") or "").strip(),
                }
            )
            continue

        if layout in {"bullets", "blank"}:
            bullets = slide.get("bullets")
            bullet_list = [str(item).strip() for item in bullets] if isinstance(bullets, list) else []
            bullet_list = [item for item in bullet_list if item]

            if layout == "blank":
                slides_out.append({"layout": "blank", "title": title})
            else:
                slides_out.append(
                    {
                        "layout": "bullets",
                        "title": title or "Slide",
                        "bullets": bullet_list or ["Key point"],
                    }
                )
            continue

        if layout == "two-column":
            slides_out.append(
                {
                    "layout": "two-column",
                    "title": title or "Comparison",
                    "left": str(slide.get("left") or ""),
                    "right": str(slide.get("right") or ""),
                }
            )
            continue

        # Unknown layouts are preserved as blank title placeholders.
        slides_out.append({"layout": "blank", "title": title or "Slide"})

    if not slides_out:
        slides_out = [{"layout": "title", "title": document_title, "subtitle": ""}]

    first_layout = str(slides_out[0].get("layout") or "")
    if first_layout != "title":
        slides_out.insert(0, {"layout": "title", "title": document_title, "subtitle": ""})

    return {
        "presentation": {
            "title": document_title,
            "confidentiality": confidentiality,
            "slides": slides_out,
        }
    }
