---
name: web-research
description: Domain-aware web research and source selection. Use when you need to search the live web for up-to-date, reliable sources (news, health/medical studies, AI research + commentary, finance) and return a curated, cited source list with clear reliability tiers and recency.
---

# Web Research

Do domain-aware web research that routes queries to the right source types (news vs studies vs papers vs filings) and returns a concise, reliable source set with citations.

## Inputs to Ask For (if missing)

- Audience + goal (what decision or output this supports)
- Time horizon (e.g., last 7 days / last 12 months / “as of today”)
- Geography/market (global/US/EU/etc.)
- Output format (source list, evidence table, brief summary)

## Workflow Decision Tree (pick a research mode)

1) **News** (what happened recently?)
- Triggers: “latest”, “today”, “this week”, breaking developments, policy announcements.
- Primary sources: reputable outlets + official statements.

2) **Health / Medicine** (what does the evidence say?)
- Triggers: treatment efficacy, side effects, epidemiology, guidelines, clinical questions.
- Primary sources: PubMed-indexed studies, systematic reviews, major health authorities.

3) **AI** (what’s new in models + what are people saying?)
- Triggers: LLMs, model releases, benchmarks, AI policy, safety incidents.
- Primary sources: arXiv/OpenReview/venues + reputable reporting.
- Secondary (signal only): Reddit/Substack/X (use as leads, not proof).

4) **Finance / Markets** (what’s the latest for a company/market?)
- Triggers: earnings, filings, macro data releases, market-moving news.
- Primary sources: regulators (SEC/EDGAR), central banks, official datasets.
- Secondary: reputable financial press (note paywalls).

5) **General** (everything else)
- Use broad search + prioritize primary/official sources when available.

## Reliability Rules (always apply)

- **Prefer primary sources** (original data, filings, standards, peer-reviewed papers) over commentary.
- **Separate signal from evidence**: treat Reddit/Substack/X as “what people claim”, then validate via primary sources.
- **Cross-check** important factual claims with **2+ independent sources** when feasible.
- **Expose uncertainty**: note when evidence is early (preprints), conflicted, or paywalled.
- **No medical/financial advice**: summarize evidence, cite sources, and recommend professional guidance where appropriate.

## Recommended Output Template

1) **Source list** (numbered)
- `1. Title — Publisher/Author, date. URL`

2) **Evidence table** (optional)
- Claim → Evidence quote/paraphrase → Source `[n]`

3) **Notes**
- What’s missing / what to verify next

## Scripted Search (optional but faster)

Use `scripts/web_search.py` to collect candidate sources quickly, then curate.

Examples:

- News: `python3 scripts/web_search.py --query "topic" --mode news --since-days 7 --format markdown`
- Health: `python3 scripts/web_search.py --query "topic" --mode health --since-years 5 --format markdown`
- AI: `python3 scripts/web_search.py --query "topic" --mode ai --since-days 30 --include-community --format markdown`
- Finance: `python3 scripts/web_search.py --query "topic" --mode finance --since-days 14 --format markdown`

For a “citations-only” candidate set, add `--strict` to filter to Tier A/B/C sources.

## References

- Curated source lists + guidance: `references/sources.md`
