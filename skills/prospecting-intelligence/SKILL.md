---
name: prospecting-intelligence
description: >
  Turn market study outputs into actionable prospecting pipelines.
  Use when the user wants to identify target accounts, find decision-maker contacts,
  build scored prospect lists, draft outreach strategies, or create GDPR-compliant
  prospecting campaigns. Leverages strategy-intelligence-suite outputs and LinkedIn
  MCP tools for live company and contact enrichment.
---

# Prospecting Intelligence

## Overview

Bridge the gap between strategic market analysis and revenue-generating outreach.
This skill takes the output of a market study (from `strategy-intelligence-suite` or
equivalent research) and converts it into a prioritized, enrichable prospect pipeline
with contact mapping, outreach angles, and compliance guardrails.

## Dependencies

- **strategy-intelligence-suite** skill (for market study inputs)
- **linkedin-search** skill / LinkedIn MCP tools (for live company and contact data)
- **xlsx** skill (for workbook generation)
- **pptx** skill (optional, for summary deck)

## Required Inputs

Collect this context before starting. If missing, ask focused follow-up questions.

- **Market study context**: Industry, geography, product/service being sold
- **ICP seed**: Ideal customer profile hints (company size, sector, pain points) or
  a completed strategy-intelligence-suite output to extract them from
- **Engagement goal**: What the user wants (meeting, demo, partnership, RFP response)
- **Compliance zone**: EU/GDPR, US/CAN-SPAM, or other (defaults to GDPR if not specified)
- **Budget tier**: free-only, low-cost ($50-100/mo tools), or full-stack

## Workflow

### Phase 1 -- ICP Definition & Target Account List

#### Step 1: Extract or Build ICP

If the user has a completed market study, extract ICP from:
- Customer Persona & Segmentation output (Module 3 of strategy-intelligence-suite)
- TAM/SAM/SOM analysis (Module 1) for segment sizing
- Competitive landscape (Module 2) for positioning gaps to exploit

Structure the ICP as:

```json
{
  "icp": {
    "firmographics": {
      "industries": ["<NAICS or free-text>"],
      "company_size_employees": {"min": 50, "max": 5000},
      "company_size_revenue": {"min": "$5M", "max": "$500M"},
      "geographies": ["<country or region>"],
      "company_types": ["enterprise", "mid-market", "SMB"]
    },
    "technographics": {
      "tech_stack_signals": ["<tools they likely use>"],
      "digital_maturity": "high|medium|low"
    },
    "pain_points": ["<top 3 pains your product solves>"],
    "buying_signals": [
      "Recently raised funding",
      "Hiring for <role>",
      "Published RFP in <domain>",
      "Expanding to <geography>"
    ],
    "decision_makers": {
      "economic_buyer": ["CEO", "CFO", "VP Finance"],
      "champion": ["Head of <domain>", "Director of <domain>"],
      "influencer": ["<functional role>"],
      "end_user": ["<operational role>"]
    },
    "disqualifiers": [
      "Company already uses <competitor>",
      "Company size below <threshold>",
      "Geography outside scope"
    ]
  }
}
```

#### Step 2: Source Target Accounts

Use the following data sources in priority order:

| Priority | Source | Tool/Method | Data Retrieved |
|----------|--------|-------------|----------------|
| 1 | LinkedIn Company Search | `mcp__linkedin-scraper__search_jobs` + `mcp__linkedin-scraper__get_company_profile` | Company profiles, size, industry |
| 2 | Web Search | `WebSearch` | Company lists, industry directories, news |
| 3 | Public Tender Portals | `WebSearch` / `WebFetch` | Active buyers with budgets |
| 4 | Industry Reports | From strategy-intelligence-suite output | Named companies in competitive analysis |
| 5 | Event/Conference Lists | `WebSearch` / `WebFetch` | Attendees, sponsors, speakers |

For each target account, collect:

```json
{
  "account": {
    "company_name": "",
    "linkedin_url": "",
    "website": "",
    "industry": "",
    "employee_count": "",
    "revenue_estimate": "",
    "headquarters": "",
    "description": "",
    "icp_fit_score": 0,
    "scoring_rationale": "",
    "buying_signals_detected": [],
    "source": ""
  }
}
```

#### Step 3: Score & Rank Accounts

Score each account 0-100 using:

| Criterion | Weight | Scoring |
|-----------|--------|---------|
| Industry match | 25% | Exact match = 100, adjacent = 50, unrelated = 0 |
| Size fit | 20% | Within ICP range = 100, +/- 50% = 50, outside = 0 |
| Geography match | 15% | Target geo = 100, adjacent = 50, outside = 0 |
| Buying signals | 20% | Each signal detected = +25 (cap 100) |
| Pain point alignment | 20% | Strong evidence = 100, inferred = 50, none = 0 |

Classify: **Tier 1** (75-100), **Tier 2** (50-74), **Tier 3** (25-49), **Disqualified** (<25)

### Phase 2 -- Contact Mapping & Enrichment

#### Step 4: Map the Buying Committee

For each Tier 1 and Tier 2 account, use LinkedIn to identify contacts:

```
mcp__linkedin-scraper__get_company_profile(linkedin_url, get_employees=true)
```

Map contacts to buying committee roles defined in the ICP:

```json
{
  "contact": {
    "name": "",
    "title": "",
    "linkedin_url": "",
    "buying_role": "economic_buyer|champion|influencer|end_user",
    "seniority": "C-level|VP|Director|Manager",
    "relevance_score": 0,
    "outreach_priority": "primary|secondary|monitor"
  }
}
```

#### Step 5: Enrich Company Context

For each Tier 1 account, gather additional intelligence:
- Recent news (WebSearch: `"<company name>" news 2026`)
- Job postings (signals growth areas and pain points)
- Technology stack signals (from job descriptions)
- Recent funding or M&A activity

### Phase 3 -- Outreach Strategy & Campaign Prep

#### Step 6: Build Outreach Angles

For each account tier, generate personalized outreach angles derived from the market study:

```json
{
  "outreach_angle": {
    "account_name": "",
    "hook": "<1-sentence pain-point hook tied to market trend>",
    "value_proposition": "<how your product solves their specific problem>",
    "proof_point": "<relevant case study, stat, or competitive gap>",
    "call_to_action": "<specific ask: meeting, demo, whitepaper>",
    "personalization_notes": "<company-specific details to reference>"
  }
}
```

#### Step 7: Draft Outreach Sequences

Generate templates for:

1. **LinkedIn Connection Request** (max 300 chars)
2. **LinkedIn Follow-up Message** (after connection accepted)
3. **Email Intro** (if email available)
4. **Email Follow-up 1** (value-add, no hard sell)
5. **Email Follow-up 2** (social proof + CTA)

Each template must include `{{personalization}}` placeholders mapped to account-level data.

#### Step 8: Compliance Checklist

Generate GDPR compliance documentation:

- [ ] Legal basis: Legitimate interest for B2B prospecting (Art. 6(1)(f))
- [ ] Legitimate Interest Assessment (LIA) drafted
- [ ] Data minimization: only professional data collected
- [ ] Transparency: outreach includes identity of sender and purpose
- [ ] Right to object: opt-out mechanism in every message
- [ ] Retention policy: contacts who don't respond deleted after 90 days
- [ ] Processing record: data sources and dates documented per contact
- [ ] No personal email addresses collected (business emails only)

## Output Deliverables

### Default Output: Prospecting Workbook (XLSX)

Use the **xlsx** skill to generate a workbook with these sheets:

| Sheet | Contents |
|-------|----------|
| `ICP` | Structured ICP definition with scoring criteria |
| `Target Accounts` | All accounts with scores, tiers, and metadata |
| `Contacts` | Buying committee contacts per account |
| `Outreach Angles` | Personalized hooks and value props per account |
| `Sequences` | Message templates with placeholders |
| `Compliance` | GDPR checklist and processing records |
| `Sources` | All data sources with access dates |

Color-code account rows by tier: green (Tier 1), yellow (Tier 2), red (Tier 3).

### Optional Output: PPTX Summary

If the user requests a presentation, use the **pptx** skill to generate slides covering:
- ICP definition and rationale
- Target account heat map (tier distribution)
- Top 10 accounts with outreach angles
- Campaign methodology and timeline
- Compliance framework

## LinkedIn Search Strategy

Since the LinkedIn MCP provides job search, use it strategically:

1. **Search for jobs your prospects post** -- companies hiring for roles related to your domain are actively investing (buying signal)
2. **Search for jobs at competitor companies** -- find companies using competitor solutions (displacement opportunity)
3. **Company profile scraping** -- get employee count, industry, description for scoring

Example searches:
- `"<your-domain> manager"` in `<target geography>` -- finds companies hiring in your space
- `"<competitor product> administrator"` -- finds companies using competitors
- `"digital transformation <industry>"` -- finds companies with relevant initiatives

## Integration with strategy-intelligence-suite

This skill consumes output from these strategy modules:

| Strategy Module | What it feeds into prospecting |
|----------------|-------------------------------|
| 1. TAM Analysis | Segment sizing for account volume targets |
| 2. Competitive Landscape | Named competitors and their customers as prospects |
| 3. Customer Personas | ICP definition and buying behavior |
| 4. Industry Trends | Buying signals and timing triggers |
| 5. SWOT/Porter's | Competitive weaknesses to exploit in outreach |
| 6. Pricing Strategy | Value proposition framing for outreach |
| 7. GTM Strategy | Channel prioritization and sequencing |
| 11. Market Entry | Geography-specific account sourcing |

## Account Sourcing Strategy by Budget Tier

**Free tier (LinkedIn MCP + WebSearch only):**
1. Extract company names from strategy-intelligence-suite competitive landscape output
2. Search LinkedIn for companies matching ICP firmographics
3. Web search for industry directories and "top companies in <industry> <geography>"
4. Scrape company profiles for employee data

**Low-cost tier (add Apollo.io or Hunter.io at ~$50-100/mo):**
- All free tier steps, plus email finding/verification and technographic enrichment

**Full-stack tier (add ZoomInfo, Clearbit, Bombora):**
- All previous tiers, plus verified phone numbers, real-time intent data, CRM integration

## Resources

- `references/playbooks.md`: detailed playbooks for each prospecting phase
- `references/gdpr-b2b-prospecting.md`: GDPR compliance guide for B2B outreach
