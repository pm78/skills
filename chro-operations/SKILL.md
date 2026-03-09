---
name: chro-operations
description: HR transformation operations for restructuring, change management, training, and outplacement delivery.
---

# chro-operations

## Purpose
- Execute role-specific operations for the CHRO agent.

## Context Inputs
- Company memory file: ~/.ai-memory/company_knowledge.md
- Role memory file: ~/.ai-memory/roles/chro_memory.md
- Optional skills roots from environment: SKILLS_PATH

## Workflow
1. Read company memory and role memory before material people-impact decisions.
2. Break delivery into parallel streams: workforce assessment, legal/compliance alignment, partner shortlisting, and execution planning.
3. Produce actionable artifacts: decision memo, transition plan, training roadmap, outplacement plan, and risk register.
4. Persist durable outcomes to role memory; escalate cross-functional policy facts to company memory only when broadly relevant.

## Safety
- Flag legal and jurisdiction-sensitive points for dedicated legal review before final layoff execution.
- Do not store secrets or personal data in memory files unless explicitly requested.
