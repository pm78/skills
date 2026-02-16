---
name: hubspot-prospection
description: >
  Run prospecting campaigns via HubSpot CRM. Use when the user wants to import
  prospect lists (CSV/Excel), enrich contacts in HubSpot, enroll them in email
  sequences, track engagement, or manage deals. Covers the full prospection
  lifecycle: import → enrich → sequence → follow-up.
---

# HubSpot Prospection

## Overview

Execute end-to-end prospecting campaigns through HubSpot CRM. This skill handles four phases: importing prospects from files, enriching them with company associations and properties, enrolling them in automated email sequences, and tracking engagement to create deals.

**MCP dependency:** `@shinzolabs/hubspot-mcp` (full CRUD on HubSpot objects)
**Scripts:** Python scripts for Sequences API v4 (not exposed by any MCP)

## Prerequisites

Before starting, ensure:
1. HubSpot MCP is configured — see `references/setup.md`
2. Python packages installed: `pip install requests openpyxl`
3. User has provided or set `HUBSPOT_ACCESS_TOKEN`

If the MCP is not configured, guide the user through `references/setup.md` first.

## Required Inputs

Collect before starting:
- **Prospect file**: Path to CSV/Excel file with contact data
- **HubSpot token**: Private app access token (or env variable)
- **Campaign goal**: What the user wants (sequence enrollment, just import, full pipeline)
- **Sender email**: For sequence enrollment — must be connected in HubSpot

---

## Phase 1 — Import Contacts

**Goal:** Load prospects from a file into HubSpot as contacts.

### Step 1: Read and Analyze the File

1. Read the user's file (CSV, TSV, or Excel) using the xlsx skill or direct reading
2. Display first 3-5 rows to the user
3. Count total rows and identify available columns

### Step 2: Map Columns to HubSpot Properties

1. Check available HubSpot properties: use `hubspot_list_properties` with `objectType: "contacts"`
2. Map file columns to HubSpot properties using auto-mapping (see `references/batch-import-guide.md`)
3. Present the mapping to the user for confirmation
4. Handle custom properties: if a column doesn't map to a standard property, ask whether to create a custom property or skip

### Step 3: Validate and Deduplicate

1. Run the import script in dry-run mode first:
```bash
python scripts/import_contacts.py --token $TOKEN --file prospects.csv --dry-run
```
2. Report validation results to the user (valid/invalid/duplicate counts)
3. Fix any mapping issues before proceeding

### Step 4: Execute Import

1. Run the import (recommended: start with 5-10 contacts as a test):
```bash
python scripts/import_contacts.py --token $TOKEN --file prospects.csv \
    --lifecycle-stage lead --skip-duplicates
```
2. Report results (created/failed/skipped)
3. If test batch succeeds, import remaining contacts

### Alternative: MCP Batch Create

For smaller lists (< 50 contacts), use MCP directly:
- `hubspot_batch_create_contacts` with up to 100 contacts per call
- Construct the payload from the file data

---

## Phase 2 — Enrichment

**Goal:** Associate contacts with companies, fill missing properties, add context notes.

### Step 1: Find or Create Companies

For each unique company in the imported contacts:

1. Search HubSpot for existing company: `hubspot_search_companies` with filter on `name` or `domain`
2. If found: note the company ID
3. If not found: create it with `hubspot_create_company`:
   - Properties: `name`, `domain`, `industry`, `city`, `country`
   - Derive domain from contact email (e.g., `john@acme.com` → `acme.com`)

### Step 2: Create Associations

Link each contact to their company:
- `hubspot_create_association` with `fromObjectType: "contacts"`, `toObjectType: "companies"`, `associationType: "contact_to_company"`

### Step 3: Enrich Contact Properties

Update contacts with additional data:
- `hubspot_update_contact` to set/update: `lifecyclestage`, `hs_lead_status`, `jobtitle`, custom properties
- If the user has LinkedIn data, store in `linkedin_url` property (must be custom-created)

### Step 4: Add Context Notes

For contacts with specific context (e.g., reason for outreach, event met at):
- `hubspot_create_note` with association to the contact
- Example: "Met at SaaS Connect 2024. Interested in payment integration."

---

## Phase 3 — Email Sequences

**Goal:** Enroll contacts in automated email sequences for outreach.

> **Important:** The Sequences API is NOT available via MCP. Use the Python script.

### Step 1: List Available Sequences

```bash
python scripts/enroll_sequence.py --token $TOKEN --list-sequences
```
Present the list to the user and help them choose the right sequence.

### Step 2: Prepare Contact List

1. Identify which contacts to enroll (e.g., by lifecycle stage, company, or tag)
2. Use `hubspot_search_contacts` to get contact IDs matching criteria
3. Collect IDs into a comma-separated list or file

### Step 3: Dry Run Enrollment

```bash
python scripts/enroll_sequence.py --token $TOKEN \
    --sequence-id SEQ_ID \
    --sender-email sender@company.com \
    --contact-ids 101,102,103 \
    --dry-run
```
Confirm with the user before actual enrollment.

### Step 4: Execute Enrollment

```bash
python scripts/enroll_sequence.py --token $TOKEN \
    --sequence-id SEQ_ID \
    --sender-email sender@company.com \
    --contact-ids 101,102,103 \
    --output-json enrollment_results.json
```

Report results and handle failures (see `references/sequence-enrollment-guide.md`).

### Permission-aware fallback (when account has no Sequences rights)

If `scripts/enroll_sequence.py --list-sequences` returns a 403 with missing scopes (for example `automation.sequences.read`), do not block the campaign. Apply this fallback automatically:

1. Mark Phase 3 as **skipped (permission-limited)** with the exact missing scope(s)
2. Generate a manual outreach list (CSV/JSON) from selected contacts including: `contact_id`, `email`, `firstname`, `lastname`, `company`, `jobtitle`, `lifecyclestage`, `hs_lead_status`
3. Create follow-up actions for sales reps:
   - Preferred: create HubSpot tasks for each contact (call/email follow-up)
   - If task creation is unavailable, add a contact note with next action + due date
4. For priority contacts, create deals and associate contact/company/deal
5. Continue with Phase 4 tracking and pipeline reporting

This keeps import/enrichment operational even when Sequences permissions are not available.

### Rate Limits

- **1,000 enrollments per day** per portal
- For larger lists, plan multi-day enrollment batches
- The script enforces API rate limits automatically

---

## Phase 4 — Follow-Up & Deal Management

**Goal:** Track engagement, identify hot leads, create deals.

### Step 1: Monitor Engagement

After sequences have been running (wait at least 24-48h):

1. Search for email engagement: `hubspot_search_emails` to find opens, clicks, replies
2. Search for enrolled contacts: `hubspot_search_contacts` with filter `hs_sequences_is_enrolled`
3. Identify hot leads: contacts who opened multiple emails or clicked links

### Step 2: Create Deals for Hot Leads

For contacts showing interest:

1. List pipelines: `hubspot_list_pipelines` with `objectType: "deals"`
2. Create deal: `hubspot_create_deal` with properties:
   - `dealname`: "{Contact Name} - {Company} - Prospection"
   - `dealstage`: `appointmentscheduled` (or appropriate stage)
   - `pipeline`: default or user-specified
   - `amount`: estimated deal value if known
   - `hubspot_owner_id`: assigned sales rep
3. Associate deal with contact: `hubspot_create_association` (contact↔deal)
4. Associate deal with company: `hubspot_create_association` (company↔deal)

### Step 3: Generate Pipeline Report

Summarize the campaign results:
- Total contacts imported
- Contacts enrolled in sequences
- Email open/click rates (if available)
- Deals created
- Pipeline value

Present as a structured table or generate an Excel report using the xlsx skill.

---

## Operating Rules

1. **Always dry-run first** — never import or enroll without showing the user what will happen
2. **Confirm before bulk actions** — ask user approval before creating > 10 records
3. **Respect rate limits** — HubSpot enforces 10 API calls/second and 1,000 enrollments/day
4. **Preserve existing data** — use `--skip-duplicates` on import; search before creating companies
5. **Log everything** — use `--output-json` on scripts to save results for troubleshooting
6. **Incremental approach** — test with small batches (5-10 records) before scaling
7. **Token security** — never log or display the HubSpot token in output

## Troubleshooting

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| MCP tools not found | MCP not configured | Follow `references/setup.md` |
| 401 on API calls | Invalid/expired token | Regenerate token in HubSpot |
| 403 on sequences | Missing `automation` scope | Update private app scopes |
| Sequences skipped automatically | Missing Sequences permission in account | Continue with manual outreach fallback (tasks/notes + deals) |
| Import creates duplicates | Didn't use `--skip-duplicates` | Use flag; merge in HubSpot |
| Sequence emails not sending | Sender email not connected | Connect in HubSpot Settings |
| Batch create partially fails | Some emails already exist | Check 409 errors; use `--skip-duplicates` |
| Rate limit errors | Too many rapid calls | Scripts handle this; wait and retry |

For detailed troubleshooting, read:
- `references/setup.md` — MCP and token issues
- `references/batch-import-guide.md` — import errors
- `references/sequence-enrollment-guide.md` — enrollment errors
