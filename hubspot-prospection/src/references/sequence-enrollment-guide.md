# Sequence Enrollment Guide

Guide for enrolling contacts into HubSpot email sequences via the Sequences API v4.

## Why a Script?

The HubSpot Sequences API v4 (enrollment endpoints) is **not exposed by any MCP server** — neither the official `@hubspot/mcp` (read-only) nor `@shinzolabs/hubspot-mcp`. The `enroll_sequence.py` script fills this gap.

## API Overview

### Base URL
```
https://api.hubapi.com/automation/v4/sequences
```

### Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/automation/v4/sequences` | List all sequences |
| GET | `/automation/v4/sequences/{id}` | Get sequence details |
| POST | `/automation/v4/sequences/{id}/enrollments` | Enroll a contact |

### Enrollment Request Schema

```json
POST /automation/v4/sequences/{sequenceId}/enrollments
{
    "contactId": "123456",
    "senderEmail": "sales@company.com",
    "startingStepOrder": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contactId` | string | Yes | HubSpot contact ID |
| `senderEmail` | string | Yes | Must be a connected email in HubSpot |
| `startingStepOrder` | integer | No | Step to start at (0 = first step) |

### Success Response (201)
```json
{
    "id": "enrollment-id",
    "sequenceId": "seq-id",
    "contactId": "123456",
    "status": "EXECUTING",
    "startedAt": "2024-01-15T10:00:00Z"
}
```

## Prerequisites

### Connected Email
The `senderEmail` must be a connected inbox in HubSpot:
- Settings > General > Email > Connected Emails
- Supports Gmail, Outlook/Office 365, IMAP

### Contact Requirements
Contacts must:
- Have a valid email address
- Not already be enrolled in the same sequence
- Not have unsubscribed from emails
- Not be in a "do not contact" state

### Required Scope
The private app needs the `automation` scope.

## Rate Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Enrollments per day | 1,000 | Per portal, resets at midnight UTC |
| API requests per second | 10 | Across all API calls |
| Contacts per sequence | 1,000 (Starter), unlimited (Pro/Enterprise) | Per sequence at a time |

The script enforces a 120ms delay between requests (~8/s) to stay safely under the 10/s limit.

## Common Errors

| HTTP Status | Error | Cause | Fix |
|-------------|-------|-------|-----|
| 400 | `CONTACT_ALREADY_ENROLLED` | Contact is already in this sequence | Skip or unenroll first |
| 400 | `INVALID_SENDER_EMAIL` | Email not connected in HubSpot | Connect email in Settings |
| 400 | `CONTACT_UNSUBSCRIBED` | Contact opted out of emails | Respect opt-out, do not re-enroll |
| 403 | `FORBIDDEN` | Missing `automation` scope | Update private app scopes |
| 404 | `SEQUENCE_NOT_FOUND` | Wrong sequence ID | Use `--list-sequences` to verify |
| 429 | `RATE_LIMIT` | Too many requests | Script auto-retries with delay |

## Usage Examples

### List sequences to find the ID
```bash
python enroll_sequence.py --token $HUBSPOT_ACCESS_TOKEN --list-sequences
```

### Dry run enrollment
```bash
python enroll_sequence.py --token $HUBSPOT_ACCESS_TOKEN \
    --sequence-id 12345 \
    --sender-email sales@company.com \
    --contact-ids 101,102,103 \
    --dry-run
```

### Enroll from file
Create a file `contact_ids.txt` with one ID per line:
```
101
102
103
```
```bash
python enroll_sequence.py --token $HUBSPOT_ACCESS_TOKEN \
    --sequence-id 12345 \
    --sender-email sales@company.com \
    --contact-ids-file contact_ids.txt
```

### Save results as JSON
```bash
python enroll_sequence.py --token $HUBSPOT_ACCESS_TOKEN \
    --sequence-id 12345 \
    --sender-email sales@company.com \
    --contact-ids 101,102,103 \
    --output-json enrollment_results.json
```

## Monitoring After Enrollment

After enrolling contacts, monitor engagement via MCP tools:
1. `hubspot_search_emails` — check for email sends and opens
2. `hubspot_search_contacts` — filter by `hs_sequences_is_enrolled = true`
3. Check sequence dashboard in HubSpot UI for open/click/reply rates

## Best Practices

1. **Always dry-run first** to catch issues before enrolling
2. **Start small** — enroll 5-10 contacts, verify emails are sent correctly
3. **Check sender email** — must be connected and verified in HubSpot
4. **Respect daily limits** — 1,000/day, plan multi-day enrollments for larger lists
5. **Monitor bounce rates** — high bounces harm sender reputation
6. **Use A/B sequences** — test different messaging on small groups before scaling
