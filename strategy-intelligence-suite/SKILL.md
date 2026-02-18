---
name: strategy-intelligence-suite
description: Use this skill whenever a user asks for investor-ready strategy work across market sizing, competitive landscape, customer segmentation, industry trend analysis, SWOT/Porter, pricing, go-to-market, customer journey, unit economics, risk, market entry, and executive synthesis.
---

# Strategy Intelligence Suite

## Use
1. Confirm required business context before drafting outputs.
2. Fill all placeholders (for example `[YOUR PRODUCT]`, `[YOUR INDUSTRY]`, `[BUDGET]`) from user input.
3. If inputs are missing, ask only what blocks the requested section.
4. Generate requested modules only; for a full request, run all 12 modules in sequence.

## Required Context
- Company and product/service name
- Industry, geography, and segment focus
- Target customer definition
- Stage, revenue, cost structure, and goals
- Budget and timeline when relevant

## Standard Output Rules
- Use structured markdown tables for rankings, assumptions, and scenario outputs.
- Use USD for all dollar figures unless requested otherwise.
- State assumptions for every quantitative estimate.
- Flag non-validated market data as assumption-based.
- Include a short verdict for each module: key takeaway, key risk, immediate action.
- Always deliver strategy reports as a slide-ready investor deck unless the user explicitly asks for another format.
- Use the installed `pptx` skill to produce the final PPTX artifact.
- Build a slide plan first, then generate a PPTX with:
  - Clear section header slide per requested module
  - Consistent title style and one data-backed takeaway per slide
  - Appendix slide for assumptions, sources, and caveats
  - One short summary slide linking all modules into a single strategic recommendation.

## Module 1: Market Sizing & TAM Analysis
- Top-down: global → regional → segment.
- Bottom-up: unit economics × potential customer pool.
- Deliver TAM/SAM/SOM with assumptions and formulas.
- Include 5-year CAGR and growth assumptions.
- Compare to 3 research firms or analyst reports.
- Output as an investor slide structure.

## Module 2: Competitive Landscape Deep Dive
- Direct competitors: top 10 by market share, revenue, funding.
- Indirect competitors: 5 adjacent potential entrants.
- For each competitor include pricing, features, audience, strengths, weaknesses, recent moves.
- Add positioning map (`price` × `value`) and threat rating.
- Include competitive moats and white-space opportunities.

## Module 3: Customer Persona & Segmentation
- Create 4 detailed personas.
- Include demographics, psychographics, pain points, goals, buying behavior, media habits, objections, trigger events, willingness-to-pay.
- Add segment size (%) and prioritization matrix (`segment attractiveness` vs `fit` vs `commercial urgency`).

## Module 4: Industry Trend Analysis
- Provide 5 macro trends and 7 micro trends from last 12 months.
- Include regulatory shifts and technology disruptions with timing.
- Include investment signals (funding, M&A, IPO activity).
- Map each trend to 0-1yr, 1-3yr, 3-5yr with impact ratings 1-10 and `so what` for this company.

## Module 5: SWOT + Porter’s Five Forces
- 7 strengths, 7 weaknesses, 7 opportunities, 7 threats.
- Include SO and WT cross-analysis.
- Rate each Porter force 1-10 and provide industry attractiveness score.

## Module 6: Pricing Strategy Analysis
- Competitor pricing audit with tiers, packaging, and price points.
- Value-based price estimate and cost-plus floor.
- Price elasticity approach and sensitivity logic.
- Psychological pricing recommendations (anchoring, charm, decoy).
- Design 3-tier price plan and discount policy.
- Projection of aggressive/moderate/conservative revenue cases.

## Module 7: Go-To-Market Strategy
- Pre-launch (60 days), launch week, post-launch (90 days).
- Rank top 7 channels by expected ROI.
- Channel mix for stated marketing budget.
- Messaging framework, funnel content plan, and partnership list.
- KPI framework (10 metrics), launch risks, and 14-day quick wins with owners.

## Module 8: Customer Journey Mapping
- Map awareness, consideration, decision, onboarding, engagement, loyalty, churn.
- For each stage include actions/thoughts/emotions, touchpoints, friction, delight opportunities, metric, and optimization tactics/tools.
- Add textual emotional curve and early churn signals.

## Module 9: Financial Modeling & Unit Economics
- CAC by channel, LTV model, LTV:CAC, payback, gross contribution, unit contribution margin.
- 3-year projection: month-by-month year 1 and quarterly year 2/3 with fixed vs variable split.
- Break-even, burn, cash flow, assumptions, sensitivity, benchmarks, and red flags.

## Module 10: Risk Assessment & Scenario Planning
- List 15 risks across market, operational, financial, regulatory, reputational.
- For each include probability (1-5), impact (1-5), risk score, indicators, mitigations, and contingency.
- Build best/base/worst/black-swan scenarios with timeline and impact.

## Module 11: Market Entry & Expansion Strategy
- Score market attractiveness with weighted criteria.
- Compare entry modes: direct, JV, acquisition, licensing/franchise, digital-first.
- Build localization and legal/compliance checklist.
- Provide 12-month month-by-month roadmap.
- Include budget allocation, resource plan, KPIs for 6 and 12 months.

## Module 12: Executive Strategy Synthesis
- Executive summary (3 paragraphs, CEO-ready).
- Current-state assessment and strategic options: conservative, balanced, aggressive.
- Recommend top strategy with rationale, timeline, investment, and risk profile.
- Top 5 priority actions for next 90 days.
- Decision framework and the single most important 1-hour insight/action.

## Completion
- If only one module is requested, respond with that module only.
- If a full suite is requested, include a concise executive bridge section connecting the outputs.
- If the request is explicitly a deck request, call out generated PPTX filename and include a one-minute executive readout.
