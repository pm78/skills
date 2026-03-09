---
name: finance-operations
description: Finance operations for transaction parsing, accounting integration, and cashflow projection.
---

# finance-operations

## Purpose
- Execute role-specific operations for the cfo agent.

## Context Inputs
- Company memory file: ~/.ai-memory/company_knowledge.md
- Role memory file: ~/.ai-memory/roles/cfo_memory.md
- Optional skills roots from environment: SKILLS_PATH

## Workflow
1. Read company memory and role memory before making material decisions.
2. Use scripts from scripts/ for deterministic operations.
3. Persist durable outcomes back to role memory.
4. Escalate to company memory only if the fact is cross-functional.

## Safety
- Do not store secrets or credentials in memory files unless explicitly requested.
- Confirm destructive actions before executing them.
