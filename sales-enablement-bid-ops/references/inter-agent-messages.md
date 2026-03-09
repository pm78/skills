# Inter-Agent Message Templates

All messages go to `90_Agent_Workspaces/{agent}/01_Inbox/` with filename format:
`MSG-{YYYYMMDD}-{HHMMSS}-from_sales_enablement-to_{agent}-{subject-slug}.md`

Mandatory headers: From, To, Date, Subject

## To Head of Sales
```
Subject: {Client} {Product} - Pricing & Win Strategy Input
Content:
- Client profile summary
- Proposed pricing (with justification)
- Win strategy questions (exec sponsor, competitive threats, bundling)
- Response deadline
```

## To Marketing Manager
```
Subject: {Client} Proposal - Brand Assets & Messaging Guidance
Content:
- Confirm brand assets for proposal
- Key messaging for client's sector
- Competitive differentiation messaging
- Approved boilerplate text
```

## To Product Manager
```
Subject: {Client} {Product} - Scope Confirmation
Content:
- Proposed scope/workstreams (tailored to client)
- Questions on scope boundaries
- Deliverable templates availability
- Quick-win add-ons
```

## To Chief Delivery
```
Subject: {Client} {Product} - Delivery Capacity & Milestones
Content:
- Engagement parameters (duration, team, effort)
- Milestone plan
- Capacity/staffing questions
- Quality gate requirements
```

## To Partner Manager
```
Subject: {Client} {Product} - Partner Involvement Assessment
Content:
- Engagement summary
- Specialist partner needs (legal, regulatory, sector)
- COGS impact of partner involvement
- Post-sale partner pre-identification
```

## To CFO
```
Subject: {Client} {Product} - Deal P&L Validation
Content:
- Revenue (price, billing terms, recognition)
- COGS breakdown table
- Gross profit and margin
- LTV estimate (upsell paths with probabilities)
- Pricing justification
```
