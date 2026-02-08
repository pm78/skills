---
name: pptx-generator
description: Generate PowerPoint (.pptx) decks from a JSON slide specification using python-pptx, including Worldline corporate templates, charts, images (including generated images), infographics/workflows (editable shapes), automatic agenda + footer, and exporting slide snapshots (PNG/JPG) for visual QA. Use when you need to create a branded PPTX programmatically, add charts/images from structured data, generate workflow diagrams/KPI cards, generate image assets (infographics/sketches/placeholders), or iterate on slide readability and design.
---

# PPTX Generator

Generate `.pptx` files programmatically from a JSON slide specification.

## Quick start

1. Install dependencies:

   `python3 -m pip install -r scripts/requirements.txt`

2. Generate a deck:

   `python3 scripts/generate_pptx.py --config assets/sample_config.json --output output.pptx --theme dark`

## Corporate template (Worldline)

- The bundled Worldline template lives at `assets/worldline-template.pptx`.
- Use it by running with template styling:

  `python3 scripts/generate_pptx.py --config assets/sample_config.json --output worldline.pptx --theme template`

- Or point to any other `.pptx` template:

  `python3 scripts/generate_pptx.py --config assets/sample_config.json --output deck.pptx --template /path/to/template.pptx --theme template`

WSL tip: convert a Windows path to a WSL path with `wslpath -u "C:\\path\\to\\file.pptx"`.

By default, any sample slides inside the template are removed so the output contains only your generated slides. Use `--keep-template-slides` to keep them.

To replace the corporate template, overwrite `assets/worldline-template.pptx` with the updated `.pptx`.

## Images

- Use the `image` layout with `image_path`.
- `image_path` may be absolute, relative (relative to the JSON config file), or a Windows path like `C:\\Users\\...\\image.png` (auto-converted on WSL when possible).

### Generated images (infographics / sketches / placeholders)

The generator can also create image assets on the fly (using Pillow) and embed them into slides.

- In an `image` slide, add `image_gen` to generate the image.
- Images are written to `--assets-dir` (default: `<output-stem>-assets` next to the PPTX).

Example (see `assets/images_agenda_footer_palette_demo.json`):

- `image_gen.kind`: `infographic` (default), `workflow`, `sketch`, `photo`
- `image_gen.prompt`: headline text to render on the image
- `image_gen.aspect_ratio`: e.g. `16:9`, `8:9`, `1:1`
- `image_gen.long_side_px` (or `width_px` + `height_px`): output resolution
- Optional: `image_gen.steps` for `workflow` images

## Charts

- Use the `chart` layout to create a native PowerPoint chart (editable in PPT).
- Example config: `assets/charts_images_demo.json` (includes both a chart slide and an image slide using `assets/sample-image.png`).

## Infographics & workflows

- Use `workflow` to generate a process/workflow diagram (rounded steps + arrows).
- Use `kpi-cards` (alias: `infographic`) to generate a grid of KPI/metric cards (rounded rectangles).
- Example config: `assets/infographics_workflows_demo.json`.

## Agenda + footer (automatic)

By default, the generator:
- Inserts an `Agenda` slide after the first `title` slide (or at the beginning if there’s no title slide)
- Adds a footer on each non-title slide: document title, confidentiality, and page number

Configure in `presentation`:
- `title` (used for footer title)
- `confidentiality` (used for footer confidentiality level)
- `agenda`: set `enabled: false` to disable, or override `title`
- `footer`: set `enabled: false` to disable; options: `include_on_title`, `show_total`, `show_page_number`

## Visual QA loop (snapshots)

python-pptx can’t render slides, so use snapshots to visually inspect readability (overflow, tiny fonts, bad spacing).

Generate + export snapshots in one command:

`python3 scripts/generate_pptx.py --config assets/sample_config.json --output deck.pptx --theme template --snapshots-dir dist/deck-slides --snapshots-format png --snapshots-gallery`

Or export snapshots from an existing deck:

`python3 scripts/export_slides.py --pptx deck.pptx --outdir dist/deck-slides --format png --gallery --method auto`

Export methods:
- `--method powerpoint`: Use Windows PowerPoint via WSL interop (best fidelity when available).
- `--method libreoffice`: Use `soffice` if installed in WSL/Linux.

Iteration guideline:
- Export snapshots → inspect slide by slide → shorten text / split dense slides / adjust layout overrides → regenerate → re-export.

## Automatic QA (generate → snapshot → auto-fix → regenerate)

Use `--qa` to run an automated readability pass after generation. The QA loop:
- Generates the deck
- Exports slide snapshots (if supported on your machine)
- Applies heuristic fixes (e.g., split overly dense `bullets`/`two-column` slides; split overfull `workflow`/`kpi-cards` slides)
- Regenerates the final PPTX (and re-exports snapshots)

Example:

`python3 scripts/generate_pptx.py --config assets/my_deck.json --output dist/my_deck.pptx --theme template --qa --snapshots-method auto --snapshots-format png --snapshots-gallery`

Notes:
- If snapshot export fails (no PowerPoint/LibreOffice available), QA still runs based on the JSON structure only.
- QA writes a QA-adjusted config to `<config>.qa.json` (override with `--qa-config-out`).

## Inspect slide layouts (template debugging)

Templates can name layouts differently. To list layout indices + names:

`python3 scripts/generate_pptx.py --config assets/sample_config.json --output /tmp/out.pptx --theme template --list-layouts`

## Input schema (JSON)

The generator accepts either of these JSON shapes:

- `{ "presentation": { ... } }` (preferred)
- `{ ... }` where the root object is the presentation

### Presentation fields

- `title` (string, optional)
- `author` (string, optional)
- `confidentiality` (string, optional): footer label (default: `Confidential`)
- `slides` (array, required)
- `agenda` (bool|object, optional): auto agenda (default enabled)
- `footer` (bool|object, optional): auto footer (default enabled)
- `palette` (object, optional): color overrides (see below)

### Slide layouts

Each slide is an object with `layout` plus layout-specific fields:

- Optional template overrides (for any slide):
  - `template_layout` (string): slide layout name (substring match) when using `--template`
  - `template_layout_index` (number): slide layout index when using `--template` (see `--list-layouts`)

- `title`: `title` (string), `subtitle` (string, optional)
- `bullets`: `title` (string), `bullets` (string[], recommended 3–6)
- `two-column`: `title` (string), `left` (string), `right` (string) — use `\n` for line breaks (literal `\\n` is also accepted)
- `chart`:
  - `title` (string, optional)
  - `chart_type` (string, e.g. `column`, `bar`, `line`, `pie`)
  - `categories` (string[])
  - `series` ({ name: string, values: number[] }[])
  - Optional: `legend` (bool), `legend_position` (`right`/`left`/`top`/`bottom`), `style` (int)
- `image`: `image_path` (string, required), `title` (string, optional), `caption` (string, optional)
  - Optional: `image_gen` (object) to generate the image asset:
    - `id` (string, optional): output file name base
    - `kind` (string): `infographic` | `workflow` | `sketch` | `photo`
    - `prompt` (string, optional): headline text to render
    - `aspect_ratio` (string, optional): e.g. `16:9`, `8:9`, `1:1`
    - `long_side_px` (int, optional) or `width_px` + `height_px`
    - Optional: `format` (`png`/`jpg`), `overwrite` (bool), `steps` (for `workflow`)
- `workflow`:
  - `title` (string, optional)
  - `orientation` (`horizontal`/`vertical`, default `horizontal`)
  - `steps` (string[] or { title: string, subtitle?: string }[])
  - Optional: `show_numbers` (bool, default true)
- `kpi-cards` (alias: `infographic`):
  - `title` (string, optional)
  - `cards` (or `items`) ({ label?: string, value?: string, note?: string, icon_path?: string }[])
  - Optional: `columns` (int, defaults to 2 or 3 based on card count)
- `blank`: `title` (string, optional)

## Notes on templates

- When `--theme template` is used, the generator tries to use the template’s layouts/placeholders for `title`, `bullets`, and `two-column`, and falls back to manual text boxes if placeholders aren’t found.
- When `--theme dark` or `--theme light` is used, the generator applies its own background/colors (even if a template is provided).

## Palette / theme colors (creative control)

Use `presentation.palette` to override colors while staying within the template palette.

Color values can be either:
- Theme tokens (recommended for templates): `ACCENT_1`, `ACCENT_2`, … `TEXT_1`, `TEXT_2`, `BACKGROUND_1`, `BACKGROUND_2`
- Hex colors: `#RRGGBB`

Sections:
- `palette.diagram`: affects `workflow` and `kpi-cards` shapes (`fill`, `line`, `text_primary`, `text_secondary`, `arrow`)
- `palette.footer`: affects footer (`text`, `line`)
- `palette.image`: affects generated images (`bg`, `accent`, `text`)

## References

- python-pptx quick reference: `references/PPTX_API_GUIDE.md`
