---
name: ai-topic-deck-generator
description: Meta-skill that composes web-research + research-brief + report-synthesizer + pptx-generator to produce a cited study deck on any topic. Use when the user asks for an end-to-end “study deck”, “training deck”, “deep dive deck”, or “topic briefing” grounded in sources and delivered as a PowerPoint.
---

# AI Topic Deck Generator

## Goal

Generate a study deck end-to-end by composing other skills:

- `web-research`: gather and log sources (raw + curated)
- `research-brief`: create a 1-page cited brief
- `report-synthesizer`: expand into a report + PPTX-ready deck spec (`pptx-generator` JSON)
- `pptx-generator`: render the final branded PPTX (agenda + footer + QA loop)

## Inputs to ask for (if missing)

- Topic and the *type* of study deck (training / exec briefing / workshop)
- Audience + goal (what decision/learning outcome this supports)
- Time horizon + geography
- Target length (slides) + depth (intro vs deep dive)
- Preferred brand/template + confidentiality label (for footer)
- Must-include sources or internal notes (optional)

## Composition workflow (skill-by-skill)

### 0) Create an output folder (single source of truth)

Use a predictable structure so each stage feeds the next:

- `work/<slug>/01_web_search_raw.json`
- `work/<slug>/01_web_search_raw.md`
- `work/<slug>/02_sources_curated.md`
- `work/<slug>/03_research_brief.md`
- `work/<slug>/04_report.md`
- `work/<slug>/05_deck.json`
- `work/<slug>/dist/<slug>.pptx`
- `work/<slug>/dist/<slug>-assets/` (generated images)
- `work/<slug>/dist/<slug>-slides/` (optional snapshots)

### 1) Web research (log everything)

Use `web-research` to collect candidate sources and log the complete results:

- Prefer running `scripts/web_search.py` to capture a raw log:
  - `python3 <web-research>/scripts/web_search.py --query "<topic>" --mode ai --since-days 30 --format json > 01_web_search_raw.json`
  - Also write markdown output for readability: `--format markdown > 01_web_search_raw.md`
- Curate a short, high-quality source set into `02_sources_curated.md` (numbered `[1]..[N]`).

If live web access is unavailable, ask the user to provide links or paste excerpts and treat that as the source log.

### 2) Research brief (1 page)

Use `research-brief` to produce `03_research_brief.md` grounded in the curated sources, with explicit citations `[n]`.

### 3) Report + deck spec

Use `report-synthesizer` to:
- expand the brief into `04_report.md`
- produce a PPTX-ready `05_deck.json` for `pptx-generator`

Keep citation numbers stable across sources → brief → report → deck.

### 4) Render the PPTX (branded + QA)

Use `pptx-generator` to render the deck:

- Generate with the corporate template: `--theme template`
- Use the QA loop to avoid dense slides: `--qa`
- Export snapshots when possible for visual inspection

Example:

`python3 <pptx-generator>/scripts/generate_pptx.py --config 05_deck.json --output dist/<slug>.pptx --theme template --qa --snapshots-dir dist/<slug>-slides --snapshots-gallery`

## Quality gates

Use `assets/study_deck_checklist.md` as the final checklist.
