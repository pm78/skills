---
name: chief-delivery-operations
description: Delivery operations workflow for optimizing cost, lead time, and quality across TokenShift services.
---

# chief-delivery-operations

## Purpose
- Execute delivery operations with strict control of cost, lead time, and quality.
- Standardize execution across TokenShift packages: Diagnose, Build, Transition, Assure.

## Context Inputs
- Company memory file: `~/.ai-memory/company_knowledge.md`
- Role memory file: `~/.ai-memory/roles/chief_delivery_memory.md`
- Optional skills roots from environment: `SKILLS_PATH`

## Workflow
1. Read company memory and chief_delivery role memory before material decisions.
2. Confirm scope, outcomes, and acceptance criteria for the engagement.
3. Build a delivery plan with owners, estimates, milestones, and explicit risks.
4. Execute with daily blocker triage and weekly KPI tracking.
5. Run quality gates before client handover (first-pass validation, defect checks, packaging review).
6. Close with retrospective actions and persist durable lessons to role memory.
7. Escalate to company memory only when a rule or fact affects multiple roles.

## KPI Framework
- Cost KPIs: gross margin, cost variance, rework effort share.
- Lead-time KPIs: quote-to-kickoff time, kickoff-to-handover time, on-time milestone rate.
- Quality KPIs: first-pass acceptance, defect escape rate, delivery CSAT.
- Reliability KPIs: critical blocker resolution time, SLA/SOW attainment.

## Operating Cadence
- Daily: engagement standup for progress and blockers.
- Weekly: portfolio KPI and risk review.
- Bi-weekly: process improvement sprint for playbooks/templates.
- Monthly: executive delivery review with CAIO/Sales/Product.
- Quarterly: package-level recalibration of delivery targets and guardrails.

## TokenShift Folder Policy
- Canonical root: `/mnt/c/Users/pasca/TokenShift` (Windows: `C:\Users\pasca\TokenShift`).
- For TokenShift tasks, write and reference files only inside this root.
- Role workspace for drafts: `/mnt/c/Users/pasca/TokenShift/90_Agent_Workspaces/chief_delivery/03_Proposed_Changes`.
- Promote reviewed artifacts to canonical business folders after validation.
- Treat TokenShift artifacts outside this root as legacy and relocate when touched.

## Safety
- Do not store secrets or credentials in memory files unless explicitly requested.
- Confirm destructive actions before executing them.
