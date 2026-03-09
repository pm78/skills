# External Proposal Deck Structure (14 slides)

Uses TokenShift PPTX template. All text in **French** (client-facing, France market).

## Slide Mapping (Template → Content)

| Slide | Template Layout | Content |
|-------|----------------|---------|
| 1 | Title (slide 1) | "{Product}" + "Proposition pour {Client}" + date + CONFIDENTIEL |
| 2 | Agenda (slide 2) | Synthese Executive: 4 value pillars with one-line descriptions |
| 3 | Section Divider (slide 3) | Votre Contexte: key transformation stats in one line |
| 4 | Content (slide 4) | Le Defi: key challenge bullets + provocative question in visual placeholder |
| 5 | 4-Phase (slide 7) | Notre Approche: Framework name + 4 workstreams with descriptions |
| 6 | Two-Column (slide 5) | Detail Axes 1 & 2: workstream activities (4 items per column) |
| 7 | Two-Column dup (slide 5) | Detail Axes 3 & 4: workstream activities (4 items per column) |
| 8 | Content dup (slide 4) | Vos Livrables: numbered deliverables with descriptions |
| 9 | 4-Phase dup (slide 7) | Calendrier & Jalons: weekly milestones with client effort |
| 10 | Content dup (slide 4) | Votre Equipe: team members with roles, days, and scope |
| 11 | Two-Column dup (slide 5) | Pourquoi {Company}: differentiators split Methodologie / Philosophie |
| 12 | Metrics (slide 6) | Investissement: 4 key numbers (Price, Duration, Consulting Days, Payment) |
| 13 | 4-Phase dup (slide 7) | Et Apres: full service journey (DIAGNOSE→BUILD→TRANSITION→ASSURE) |
| 14 | Thank You (slide 9) | Passons a l'Action + CTA + contact details |

## Slides Not Used
- Slide 8 (Chart) — embedded Excel, avoid programmatic editing

## Build Method
Use PPTX skill editing workflow: unpack → add_slide.py (duplicate slide4 x2, slide5 x2, slide7 x2) → XML text replacement → set_slide_order → clean.py → pack.py.

## Tone Guidelines (French)
- Use "vous" (formal)
- Avoid jargon — explain concepts clearly
- Focus on client outcomes, not our process
- Lead with questions the CTO cares about
- Quantify everything possible
- Reference specific client context (their AI projects, challenges, numbers)
