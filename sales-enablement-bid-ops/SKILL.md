---
name: sales-enablement-bid-ops
description: End-to-end bid management automation for TokenShift. Use when a prospect expresses interest in any TokenShift service (DIAGNOSE, BUILD, TRANSITION, ASSURE). Handles the full bid lifecycle from intelligence collection, through strategy/pricing iteration, to branded proposal generation. Produces inter-agent messages, bid strategy documents, internal validation decks (English), and client-facing proposals (French) using the TokenShift PPTX template.
---

# Bid Management Operations

## Purpose
Automate the complete bid lifecycle from opportunity capture to proposal delivery, protecting both win rate and margin.

## Use When
- A prospect or client expresses interest in a TokenShift service
- Preparing a proposal, pitch, or bid response
- Running pricing/margin scenarios for a specific deal
- Generating internal bid validation materials

## Three-Phase Workflow

### Phase 1: Bid Collection
1. **Client research**: Use web-research skill or Task agent to gather client profile (revenue, employees, sector, challenges, AI initiatives, org structure)
2. **Internal intelligence**: Read existing documents from agent workspaces:
   - `product/03_Proposed_Changes/` - Product catalog, pricing, features
   - `sales/03_Proposed_Changes/` - Sales assumptions, funnel metrics
   - `chief_delivery/03_Proposed_Changes/` - Delivery model, costs, capacity
   - `cfo/03_Proposed_Changes/` - P&L model, business case
3. **Inter-agent messages**: Send requests to stakeholder inboxes per [references/inter-agent-messages.md](references/inter-agent-messages.md)
4. **Qualification**: Score the opportunity on 6 criteria (strategic fit, win probability, profitability, delivery feasibility, upsell potential, risk manageability) - each 1-5

### Phase 2: Strategy
1. **Solution design**: Map client needs to product (DIAGNOSE/BUILD/TRANSITION/ASSURE), define scope and workstreams
2. **Pricing**: Apply pricing rules from [references/pricing-rules.md](references/pricing-rules.md)
3. **P&L calculation**: Revenue, COGS breakdown (internal labor, partners, tools, QA buffer), gross margin
4. **Win strategy**: Competitive positioning, key messages, differentiation
5. **Risk assessment**: Identify risks (P/I scoring), mitigations
6. **Go/No-Go**: Average qualification score >= 3.5 = GO

### Phase 3: Proposal Writing

#### Language Rules
- **External client-facing proposals**: French by default (TokenShift operates in France). English only if explicitly requested.
- **Internal validation decks**: English by default (internal team lingua franca).

#### Template Rules
- **Always** use the TokenShift PPTX template: `08_Brand_Templates/01_Brand_Guidelines/TokenShift-Brand/tokenshift-template-v2.pptx`
- **Never** generate from scratch with pptxgenjs — the template contains the correct logo, branded layouts, and color scheme.
- Use the PPTX skill editing workflow: unpack → add_slide.py → XML text replacement → clean.py → pack.py

#### Deliverables
1. **Bid strategy doc**: Markdown document consolidating all intelligence
2. **Internal validation deck** (10 slides, English): see [references/internal-deck-structure.md](references/internal-deck-structure.md)
3. **External proposal** (14 slides, French): see [references/external-deck-structure.md](references/external-deck-structure.md)
4. **Generation**: Adapt `scripts/build_from_template.py` for each bid
5. **QA**: Run `markitdown` to verify content, check for remaining placeholder text

## Template Slide Layouts (9 available)
| # | Layout | Best For |
|---|--------|----------|
| 1 | Title | Opening slide (dark navy bg, logo, tagline) |
| 2 | Agenda | Executive summary, table of contents (4 numbered sections) |
| 3 | Section Divider | Context, transition between sections (dark bg, large text) |
| 4 | Content | Bullet points + visual placeholder (white bg, 4 bullets) |
| 5 | Two-Column | Comparisons, before/after, 2x4 items (white bg) |
| 6 | Metrics | Key numbers dashboard (4 metric cards with labels) |
| 7 | 4-Phase | Process flows, timelines (4 phases with descriptions) |
| 8 | Chart | *Avoid* — embedded Excel, hard to modify programmatically |
| 9 | Thank You | Closing slide, CTA (dark bg, tagline, contact info, logo) |

## Technical Notes for Deck Generation
- `add_slide.py` creates slide files and rels entries but does NOT auto-insert into `<p:sldIdLst>` — must insert manually with unique IDs.
- Text replacement: replace directly in `<a:t>` tags in slide XML. Multi-line labels (e.g., "Phases of\ntransformation") are split across `<a:p>` elements — replace each `<a:t>` value separately.
- After structural changes (add/remove slides), update `<p:sldIdLst>` order in `presentation.xml`.
- Run `clean.py` to remove orphaned slides/media before packing.

## Output Files
All outputs go to `90_Agent_Workspaces/sales_enablement/03_Proposed_Changes/`:
- `{Client}-Bid-Strategy-{date}.md`
- `{Client}-Internal-Bid-Validation-{date}.pptx` (10 slides, English)
- `{Client}-Proposal-{date}.pptx` (14 slides, French)

## Inter-Agent Communication
Send to these inboxes at `90_Agent_Workspaces/{agent}/01_Inbox/`:
| Agent | Purpose |
|-------|---------|
| `sales` | Pricing validation, win strategy |
| `marketer` | Brand assets, messaging guidance |
| `product` | Product scope confirmation |
| `chief_delivery` | Delivery capacity, milestones, deliverable templates |
| `partner` | Partner involvement assessment |
| `cfo` | Deal P&L validation |

## TokenShift Brand
- **Palette**: Navy `#0F1B2D`, Cyan `#00B4D8`, Slate `#475569`, White `#FFFFFF`
- **Typography**: Inter / Helvetica Neue (embedded in template)
- **Logo**: Linked Rings mark (embedded in template — never embed manually)
- **Tagline**: "From code to culture."

## DIAGNOSE Product Quick Reference
| Attribute | Value |
|-----------|-------|
| Duration | 4-6 weeks |
| Price range | EUR 75,000 - 150,000 |
| Pioneer price | -20% (first 5 clients) |
| COGS | 37.5% |
| Gross margin | 62.5% |
| Delivery | TokenShift direct (own consultants) |
| Team | Sr Consultant + AI Engineer + CEO oversight |
| Deliverables | 6 (Roadmap, Scorecard, Use Cases+ROI, EU AI Act Report, Workforce Impact, Board Brief) |
