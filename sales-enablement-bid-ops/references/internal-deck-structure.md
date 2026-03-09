# Internal Bid Validation Deck Structure (10 slides)

Uses TokenShift PPTX template. All text in **English** (internal lingua franca).

## Slide Mapping (Template → Content)

| Slide | Template Layout | Content |
|-------|----------------|---------|
| 1 | Title (slide 1) | "{Product} - {Client}" + "Internal Bid Validation \| BID-{YYYY}-{NNN}" + date + CONFIDENTIAL - INTERNAL |
| 2 | Metrics (slide 6) | Opportunity Summary: 4 key numbers (Investment, Duration, Gross Margin, Go/No-Go Score) |
| 3 | Section Divider (slide 3) | Client Context: key stats (revenue, employees, challenges, AI projects, deadlines) |
| 4 | 4-Phase (slide 7) | Proposed Solution: 4 workstreams mapped to client needs |
| 5 | Two-Column (slide 5) | Win Strategy: Our Advantages vs. Competition Weaknesses |
| 6 | 4-Phase dup (slide 7) | Delivery Plan: weekly timeline + team composition + onsite visits |
| 7 | Metrics dup (slide 6) | Deal Economics: Revenue, COGS, Gross Profit, LTV |
| 8 | Content (slide 4) | Competitive Landscape: threat analysis by competitor category |
| 9 | Content dup (slide 4) | Risk Assessment: identified risks (level + mitigation) |
| 10 | Thank You (slide 9) | RECOMMENDATION: GO/NO-GO + score + next steps with dates |

## Slides Not Used
- Slide 2 (Agenda) — not needed for internal validation
- Slide 8 (Chart) — embedded Excel, avoid programmatic editing

## Build Method
Use PPTX skill editing workflow: unpack → add_slide.py (duplicate slide4, slide6, slide7) → XML text replacement → set_slide_order → clean.py → pack.py.
The Metrics layout labels span multiple `<a:p>` elements — replace each `<a:t>` value separately.
