# Batch Import Guide

Guide for importing prospect lists (CSV/Excel) into HubSpot CRM.

## Column Mapping

### Auto-Mapped Columns

The import script automatically maps common column names (EN/FR) to HubSpot properties:

| Source Column | HubSpot Property | Notes |
|--------------|-----------------|-------|
| Email, E-mail | `email` | Primary dedup key |
| First Name, Prénom | `firstname` | |
| Last Name, Nom | `lastname` | |
| Company, Société, Entreprise | `company` | |
| Phone, Téléphone | `phone` | |
| Mobile, Portable | `mobilephone` | |
| Job Title, Poste, Fonction | `jobtitle` | |
| Website, Site web | `website` | |
| City, Ville | `city` | |
| Country, Pays | `country` | |
| LinkedIn, LinkedIn URL | `linkedin_url` | Custom property — must exist |
| Zip, Code postal | `zip` | |
| Address, Adresse | `address` | |

### Custom Mapping

For non-standard columns, use explicit mapping:

```bash
python import_contacts.py --token TOKEN --file data.csv \
    --mapping "Société=company,Téléphone fixe=phone,Segment=hs_lead_status"
```

### Custom Properties

If your file contains data for HubSpot custom properties:
1. First create the property in HubSpot (Settings > Properties)
2. Use the property's internal name (not label) in mapping
3. Internal names are lowercase with underscores (e.g., `custom_segment`)

## Validation Rules

The import script validates each row before sending to HubSpot:

1. **Email format**: Must contain `@` if present
2. **Minimum data**: Each contact needs either `email` OR (`firstname` AND `lastname`)
3. **Empty rows**: Rows with no mapped values are skipped
4. **None values**: String "None" or "none" values are treated as empty

## Deduplication

### Within-File Dedup
- Automatic: first occurrence wins when emails match
- Case-insensitive email comparison

### Against HubSpot (--skip-duplicates)
- Searches HubSpot for each email before creating
- Slower but prevents duplicates
- Recommended for re-imports or incremental loads

### HubSpot's Built-in Dedup
- HubSpot deduplicates on email by default
- If a contact with the same email exists, the API returns a `409 Conflict`
- The batch endpoint may partially succeed (some created, some rejected)

## Lifecycle Stages

Set with `--lifecycle-stage`:

| Stage | Internal Value | When to Use |
|-------|---------------|-------------|
| Subscriber | `subscriber` | Newsletter signups |
| Lead | `lead` | Downloaded content, showed interest |
| MQL | `marketingqualifiedlead` | Matches ICP, engaged |
| SQL | `salesqualifiedlead` | Sales-ready, qualified |
| Opportunity | `opportunity` | Active deal in pipeline |
| Customer | `customer` | Closed-won |

Default: HubSpot assigns `subscriber` if not specified.

## Error Handling

### Common Batch Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `409 Conflict` | Email already exists | Use `--skip-duplicates` |
| `400 Invalid input` | Bad property value | Check enum values, date formats |
| `429 Too Many Requests` | Rate limited | Script auto-retries with backoff |
| `403 Forbidden` | Missing scope | Add `crm.objects.contacts.write` |
| Property not found | Custom property doesn't exist | Create in HubSpot first |

### Date Format
HubSpot expects dates as midnight UTC timestamps: `2024-01-15T00:00:00.000Z` or Unix ms.

### Phone Format
Include country code: `+33612345678`. HubSpot stores as-is.

## Recommended Workflow

1. **Dry run first**: `--dry-run` to validate mapping and data quality
2. **Small batch test**: Import 5-10 contacts to verify in HubSpot UI
3. **Full import**: Run without `--dry-run`
4. **Verify**: Check contact count and properties in HubSpot
5. **Enrich**: Use Phase 2 (Enrichment) to associate with companies
