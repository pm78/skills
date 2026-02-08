# Study Deck Quality Checklist

## Sources & citations

- Every key claim has at least one citation: `...[n]`
- Sources are numbered once and reused consistently across brief → report → deck
- Uncited context is explicitly labeled as such

## Narrative

- Agenda reflects the actual sections
- Each section ends with a short “Key takeaways” slide
- Deck ends with “Further reading” + “Open questions”

## Slide readability

- Bullets: ≤ 6 per slide (split if dense)
- Minimum font size: ~16pt for body text
- Avoid walls of text: split into multiple slides
- Prefer diagrams/charts for structure and comparisons

## Brand / template

- Use template theme tokens for colors (ACCENT_1..6, TEXT_1/2, BACKGROUND_1/2)
- Footer shows title + confidentiality + page number (unless intentionally disabled)

## QA loop

- Run `pptx-generator --qa` and re-check snapshots if available
- Fix the JSON spec rather than hand-editing slides in PowerPoint (repeatable)

