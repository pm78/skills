# Prospecting Intelligence Playbooks

Detailed execution guides for each phase of the prospecting pipeline.

## Playbook 1: ICP Extraction from Market Study

### When to use
The user has completed a market study (via strategy-intelligence-suite or manual research) and wants to derive a prospecting-ready ICP.

### Inputs required
- Completed market study output (any combination of the 12 strategy modules)
- OR: manual description of target market, product, and customer

### Steps

1. **Parse persona output** (Module 3):
   - Extract top-priority persona demographics: job title, company size, industry
   - Map pain points to your product's value propositions
   - Note buying behavior and trigger events

2. **Parse TAM/SAM** (Module 1):
   - Extract SAM geography and segment boundaries
   - Use SOM as the realistic target account volume

3. **Parse competitive landscape** (Module 2):
   - Extract competitor customer segments (these are your displacement targets)
   - Identify whitespace segments (these are your greenfield targets)

4. **Structure as ICP JSON** (see SKILL.md schema)

5. **Validate with user**: Present ICP for confirmation before sourcing

### Output
Structured ICP JSON ready for account scoring.

---

## Playbook 2: Account Sourcing via LinkedIn

### When to use
ICP is defined and user wants to find matching companies.

### Steps

1. **Build search queries** from ICP:
   - Industry keywords + geography + role keywords
   - Competitor product names (to find displacement targets)
   - Domain-specific job titles (to find companies investing in the space)

2. **Execute LinkedIn job searches**:
   ```
   mcp__linkedin-scraper__search_jobs(search_term="<query>")
   ```
   - Parse company names and URLs from job results
   - Deduplicate by company

3. **Scrape company profiles**:
   ```
   mcp__linkedin-scraper__get_company_profile(linkedin_url="<url>")
   ```
   - Extract: industry, employee count, description, headquarters

4. **Score each account** against ICP criteria (see scoring matrix in SKILL.md)

5. **Tier and rank** the account list

### Output
Scored and tiered target account list.

---

## Playbook 3: Contact Mapping via LinkedIn

### When to use
Target accounts are identified and scored; user wants to find decision-makers.

### Steps

1. **For each Tier 1 account**, scrape with employees:
   ```
   mcp__linkedin-scraper__get_company_profile(linkedin_url="<url>", get_employees=true)
   ```

2. **Filter employees** by title keywords from ICP decision_makers roles

3. **Assign buying committee roles**:
   - Match title to economic_buyer, champion, influencer, or end_user
   - Prioritize: VP/Director level for champion, C-level for economic buyer

4. **Score contact relevance** (0-100):
   - Title match to ICP role: 40%
   - Seniority level: 30%
   - Department relevance: 30%

5. **Flag primary contact** per account (highest relevance score)

### Output
Contact list with buying committee mapping per account.

### GDPR Notes
- Only collect name, title, LinkedIn URL (publicly available professional data)
- Do NOT scrape personal email, phone, or non-professional social media
- Document the source and date of collection for each contact

---

## Playbook 4: Company Enrichment via Web Research

### When to use
Tier 1 accounts need deeper context for personalized outreach.

### Steps

1. **Recent news search**:
   ```
   WebSearch: "<company name>" news 2026
   ```
   - Look for: funding rounds, product launches, leadership changes, partnerships

2. **Job posting analysis**:
   ```
   WebSearch: "<company name>" careers OR jobs site:linkedin.com
   ```
   - Hiring in your domain = active investment = buying signal
   - Hiring for competitor's product = displacement opportunity

3. **Technology signals**:
   - Parse job descriptions for tech stack mentions
   - Check company website for technology partner logos

4. **Financial signals**:
   ```
   WebSearch: "<company name>" funding OR acquisition OR IPO 2025 2026
   ```

5. **Compile enrichment per account** as additional metadata

### Output
Enriched account profiles with buying signals and personalization hooks.

---

## Playbook 5: Outreach Angle Generation

### When to use
Accounts are scored, contacts mapped, and enrichment done. User wants outreach content.

### Steps

1. **For each account tier, select angle strategy**:
   - **Tier 1**: Hyper-personalized (company-specific pain + your specific solution)
   - **Tier 2**: Segment-personalized (industry pain + your category solution)
   - **Tier 3**: Generic value-led (broad pain + thought leadership)

2. **Build the hook** from:
   - Market trend (from Module 4 industry trends)
   - Company-specific news (from enrichment)
   - Competitive gap (from Module 2)

3. **Build the value proposition** from:
   - Product capabilities mapped to ICP pain points
   - Pricing advantage (from Module 6)
   - Differentiation (from Module 5 SWOT strengths)

4. **Build the proof point** from:
   - Case studies or track record
   - Industry statistics from market study
   - Named competitor displacement examples

5. **Draft message sequences** using templates in `references/outreach-templates.md`

### Output
Per-account outreach angles and message sequences.

---

## Playbook 6: GDPR Compliance Documentation

### When to use
Always, when the compliance zone is EU/GDPR.

### Steps

1. **Draft Legitimate Interest Assessment (LIA)**:
   - Purpose: B2B sales prospecting for [product] to [ICP]
   - Necessity: No less intrusive way to reach B2B decision-makers
   - Balancing: Professional data only, easy opt-out, limited retention

2. **Create processing record entry**:
   - Data categories: name, job title, company, LinkedIn URL
   - Legal basis: Art. 6(1)(f) GDPR - legitimate interest
   - Retention: 90 days for non-responders, active pipeline until relationship ends
   - Source: LinkedIn (publicly available professional profiles)

3. **Embed compliance elements in outreach**:
   - Sender identity and company name
   - Purpose statement (brief)
   - Opt-out instruction in every message
   - Link to privacy policy if available

4. **Generate compliance checklist** (see SKILL.md)

### Output
GDPR compliance documentation and checklist.

---

## Playbook 7: Pipeline Export & Handoff

### When to use
All phases complete; user wants deliverables.

### Steps

1. **Compile all data into JSON workbook schema** (see `assets/prospecting-workbook.json`)

2. **Render XLSX**:
   ```bash
   python3 skills/public/prospecting-intelligence/scripts/render_xlsx.py \
     skills/public/prospecting-intelligence/assets/prospecting-workbook.json \
     --out prospecting-pipeline.xlsx
   ```

3. **Optional: Render PPTX summary** using strategy-intelligence-suite renderer

4. **Provide next-steps briefing**:
   - Recommended cadence and timing
   - Follow-up triggers and escalation criteria
   - CRM import instructions (if applicable)
   - Campaign measurement KPIs

### Output
XLSX workbook + optional PPTX + next-steps brief.
