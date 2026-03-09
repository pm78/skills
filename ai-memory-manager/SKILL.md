---
name: ai-memory-manager
description: "Manage two-level long-term memory for role-oriented agents: company memory in ~/.ai-memory/company_knowledge.md and role memory in ~/.ai-memory/roles/ROLE_memory.md using AGENT_ROLE. Use before complex decisions, when context is uncertain, and whenever durable high-signal facts should be persisted."
---

# AI Memory Manager

You have access to two memory layers:

1. Company Memory: `~/.ai-memory/company_knowledge.md`
- Company-wide source of truth.
- Read for global context, standards, and cross-functional policies.
- Write only when the fact impacts multiple roles or company policy.

2. Role Memory: `~/.ai-memory/roles/${AGENT_ROLE}_memory.md`
- Role-specific durable memory.
- Primary write target for role-level execution context.

## Role Resolution

- Resolve role from `AGENT_ROLE`.
- If `AGENT_ROLE` is missing, default to `developer`.
- Role memory path rule: `~/.ai-memory/roles/ROLE_memory.md`.

## Updated Workflow

1. Before starting a substantial task, read both files:
- `~/.ai-memory/company_knowledge.md`
- `~/.ai-memory/roles/${AGENT_ROLE}_memory.md`

2. Decide write destination:
- Write to role memory for role-specific facts.
- Write to company memory for cross-role facts and global policy.

3. Keep writes durable and high-signal:
- Preferences
- Constraints
- Stable environment facts
- Long-running operating rules

4. Avoid low-signal data:
- Temporary logs
- One-off debug output
- Speculation
- Sensitive data unless explicitly requested

## Trigger Handling

Treat these as direct memory update triggers:
- "Remember that..."
- "Retiens que..."
- "Do not forget..."
- "Update memory..."
- "Correct memory..."

When triggered, classify company-vs-role destination and update immediately.

## Command Patterns

- Read company memory:
  - `cat ~/.ai-memory/company_knowledge.md`

- Read role memory:
  - `cat ~/.ai-memory/roles/${AGENT_ROLE}_memory.md`

- Search both layers:
  - `rg -n "<keyword>" ~/.ai-memory/company_knowledge.md ~/.ai-memory/roles/${AGENT_ROLE}_memory.md`

- Append role fact:
  - `printf '\n- <fact>\n' >> ~/.ai-memory/roles/${AGENT_ROLE}_memory.md`

- Append company fact:
  - `printf '\n- <fact>\n' >> ~/.ai-memory/company_knowledge.md`
