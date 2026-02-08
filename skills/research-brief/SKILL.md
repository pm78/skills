---
name: research-brief
description: Turn a topic plus links/notes into a 1-page research brief with key claims, evidence, and explicit citations. Use when the user asks for a research brief, memo, or one-pager grounded in provided sources (URLs, PDFs, pasted notes), including uncertainty, “Next questions”, and “What would change my mind”.
---

# Research Brief

## Overview

Produce a compact 1-page brief that is decision-useful: a clear scope, a handful of defensible claims, and citations back to the user’s sources.

## Inputs to Ask For (if missing)

- Audience and goal (who will read this, what decision it supports)
- Must-include sources/notes (links, PDFs, pasted excerpts, internal notes)
- Time horizon (e.g., “next 6–12 months”)
- Geography/market (e.g., “US”, “EU”, “global”)

If sources are missing or inaccessible, ask the user to paste the relevant excerpts and/or provide alternative links.

## Workflow

### 1) Restate the question and scope

- Restate the topic as a concrete research question.
- Confirm time horizon and geography.
- Clarify what is in-scope vs out-of-scope (1–3 bullets).

### 2) Inventory the sources

- List each provided source once and assign it a citation number (`[1]`, `[2]`, …).
- Note source type and date when available (report, article, paper, blog, etc.).
- Prefer the most primary/authoritative sources when conflicts exist.

### 3) Extract key claims from the sources

- Identify 3–7 high-signal claims that are directly supported by the sources.
- For each claim:
  - Summarize the claim in one sentence.
  - Add a short evidence bullet (quote or paraphrase) with citations.
  - Explain why it matters for the audience/goal.

### 4) Flag uncertainty and missing data

- Call out disagreements across sources, weak evidence, outdated data, or unclear assumptions.
- Separate “supported claims” from “hypotheses” and label anything that is not well supported.

### 5) Produce the 1-page brief using the template

- Use `assets/brief.md` as the output template.
- Keep it “one page” in spirit: concise headings + bullets; avoid long paragraphs.
- Default target length: ~600–900 words (unless the user requests otherwise).

### 6) Add “Next questions” and “What would change my mind”

- Provide 3–7 next questions that would materially improve confidence or change a decision.
- Provide 3–7 falsifiers: what evidence would cause you to update/flip key conclusions.

## Citation Rules (keep consistent)

- Use inline bracket citations for claims and evidence: `... [2]` or `... [1][3]`.
- Every “Key Claim” must have at least one citation.
- If you include general background knowledge that is not in the provided sources, label it explicitly as “uncited context” and keep it out of the “Key Claims” section.

## Resource

- `assets/brief.md`: 1-page brief template to fill and return.
