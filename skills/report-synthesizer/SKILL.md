---
name: report-synthesizer
description: Synthesize a research brief plus web research results into a structured, citation-backed report and a PPTX-ready slide specification (pptx-generator JSON). Use when you need to turn research artifacts (sources + 1‑page brief) into a longer report and a study/briefing deck plan.
---

# Report Synthesizer

## Goal

Produce two artifacts from existing research inputs:

1) `report.md`: a structured report (3–10 pages in spirit) with explicit `[n]` citations  
2) `deck.json`: a `pptx-generator` config that turns the report into a study deck (sections, diagrams, charts, generated images)

## Inputs to ask for (if missing)

- Topic + audience + purpose (training, exec briefing, workshop, etc.)
- Time horizon + geography
- Target deck size (slides) + depth (intro vs deep dive)
- Confidentiality label (for footer)
- Source inputs (files or pasted):
  - Web research output (`web_search_raw.json` / `web_search_raw.md` / curated `sources.md`)
  - Research brief (`research_brief.md`) from `research-brief`
  - Internal notes / constraints (must-include sections, banned claims, etc.)

If the user has no sources and you cannot access the web, ask them to provide links or paste excerpts first.

## Workflow

1) Normalize sources into a numbered list `[1]..[N]` and keep numbering stable across outputs.
2) Extract 5–10 defensible claims with evidence and explicitly label uncertainty.
3) Write `report.md` using `assets/report_template.md`.
4) Convert the report into a slide plan:
   - Cover slide
   - Sections (3–6): overview + 1–3 concept slides + 1 diagram/chart/infographic slide
   - Key takeaways
   - Further reading (citations)
5) Emit `deck.json` using `assets/deck_config_template.json` as the base:
   - Prefer PPT-native infographics (`workflow`, `kpi-cards`) when users may want to edit.
   - Use `image_gen` when you want a rendered illustration/placeholder (infographic/sketch/photo-style).
   - Keep slide text short; push detail into the report.
6) Hand off to `pptx-generator`:
   - `python3 .../pptx-generator/scripts/generate_pptx.py --config deck.json --output dist/<slug>.pptx --theme template --qa`

## Output contract (for composition)

- Always produce both `report.md` and `deck.json`.
- Every non-trivial factual slide includes at least one citation in the slide text like `...[3]`.
- Use the same citation numbers in the report and the deck (do not renumber between artifacts).

## Assets

- `assets/report_template.md`: report template to fill
- `assets/deck_config_template.json`: minimal PPTX config skeleton for `pptx-generator`
