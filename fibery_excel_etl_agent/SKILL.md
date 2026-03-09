---
name: fibery_excel_etl_agent
description: Build and operate a Python ETL that migrates a complex Excel business workbook into Fibery using /api/commands, configure Fibery dashboards (board/timeline/list), generate an interactive HTML KPI dashboard, deploy it on Vercel, and embed it inside Fibery — with robust handling of Fibery API edge cases.
---

# Fibery Excel ETL Agent

Use this skill when you need to ingest Excel business data into Fibery and ship a usable UI (not raw giant tables).

## Role

You are an expert Python Data Engineer and Fibery API specialist.
You implement:

1. ETL ingestion from Excel to Fibery entities
2. Relationship-safe upsert order
3. User-friendly Fibery views (Board, Timeline/Calendar, List/Table)
4. Hardening against Fibery API/view quirks observed in production

## Required Fibery API Model

Never hallucinate standard REST CRUD endpoints.

- Data mutations go through one endpoint:
  - `POST https://{workspace}.fibery.io/api/commands`
- Headers:
  - `Authorization: Token {FIBERY_API_KEY}`
  - `Content-Type: application/json`
- Payload:
  - Array of commands (or `fibery.command/batch` for batching)

Creation example:

```json
[
  {
    "command": "fibery.entity/create",
    "args": {
      "type": "Business OS/Client",
      "entity": {
        "Business OS/Name": "Nom du Client"
      }
    }
  }
]
```

Relation example:

```json
"Business OS/Client": { "fibery/id": "uuid-of-client" }
```

## Views API Rules (Critical)

Fibery views use:

- `POST https://{workspace}.fibery.io/api/views/json-rpc`

Observed constraints and fixes:

1. Use field IDs in expressions, not field names.
2. Some tenants reject list grouping expressions and can crash with:
   - `not supported: { expression: [ 'Project Tracking/Periode' ] }`
   - For list views, prefer sort by `Periode` and keep `groupBy: null`.
3. `fibery/type` can be readonly on `update-views`.
   - If type migration or meta corruption is suspected: delete view + recreate.
4. Timeline can appear empty with milestone-only rendering.
   - Set `endExpression = startExpression` for one-day items.

## ETL Execution Order

Respect dependencies:

1. Clients
2. Sous-traitants
3. Contacts
4. Missions
5. Production Mensuelle (unpivot from Pipe/Reel months)
6. Interventions
7. Factures

Keep ID indexes in memory for relation linking.

## Excel Parsing Rules

- Use `pandas` + `openpyxl`.
- Handle NaN, blank placeholders, and mixed date formats.
- For month columns, unpivot/melt to rows (`Production Mensuelle`).
- Distinguish statuses:
  - Pipe -> `Prevu`
  - Reel -> `Realise`
- In Pipe/Reel, keep only pointage rows (ratio/coefficient present, typically `Unnamed: 5` > 0).
  This removes duplicated CA sections that otherwise inflate `Jours pointes`.
- Prevent false month headers from accounting metadata rows (e.g. `5eme exercice comptable`).
  Only treat a column as month if the first non-empty header-like value is month-like.

Date parsing rule:

- If date string is ISO-like (`YYYY-MM-DD`), parse with `dayfirst=False`.
- Otherwise parse with `dayfirst=True`.

This avoids period drift (e.g., everything collapsing to January).

## Invoice Ingestion Rules (Critical)

Do not build invoice identity from title alone.

1. Clean invoice number:
   - Reject placeholders (`0`, `nan`, null-like values)
   - Reject decimal monetary artifacts (`12.37`, `5133.3333`)
   - Reject date-like values accidentally mapped as numbers
   - Normalize `552.0 -> 552`
2. Source extraction primarily from `suivi`/`factures` tabs.
3. Upsert key should prefer invoice number field when available.
4. Human-readable title pattern:
   - `Facture {numero} | {mission_or_client}`

## Batching, Retry, and Stability

- Max 100 commands per batch request.
- Implement exponential backoff on:
  - HTTP 429
  - transient 5xx / network errors
- Print progress logs by stage.

## Expected UI Outputs

Build these user-oriented views:

1. `Dashboard - Pipe & Forecast 2026`
   - Type: `board`
   - Group by: `Statut`
2. `Dashboard - Planning Sous-traitants`
   - Type: `timeline` (or fallback `calendar`)
   - Group by: `Sous-traitant`
   - Start date: `Date intervention`
3. `Dashboard - Plan de Charge & CA Mensuel`
   - Type: `list`/`table` for input fields (`Jours pointes`)
   - No list grouping expression if tenant rejects it
4. `Dashboard - CA Mensuel (Formules)`
   - Separate view for computed CA metrics

## Business OS Web App (HTML + CRUD)

The app is branded "Air Consulting Services — Business OS" with the Air Consulting Services logo
(loaded from `logo.png`, base64-encoded at runtime via `_load_logo_b64()`).

It is a self-contained HTML single-page application with 7 tabs:

1. **Dashboard** — 7 KPI cards, pipeline breakdown, invoice breakdown, monthly CA chart, actions summary
   (server-rendered on initial page load, with hover drill-down popovers)
2. **Opportunites** — Pipeline missions CRUD table (statuses: Prospect, Qualification, Proposition,
   Negociation) with inline editing, status dropdowns, checkboxes, computed CA column
3. **Missions** — Signed/active missions CRUD table (statuses: Gagne, En cours, Livre)
4. **Clients** — Client CRUD table enriched with contact data (contact_name, contact_email,
   contact_phone queried from the Contact entity linked to Client)
5. **Sous-traitants** — Subcontractor CRUD table (Name, Email, Specialite, CJM)
6. **Factures** — Invoice CRUD table with status workflow, overdue highlighting, relance checkbox
7. **Actions** — Computed action list (proposals to send, invoices overdue, missions sans TJM) with
   quick-action buttons that toggle booleans via API

### Architecture

- `generate_dashboard.py` queries Fibery API, computes KPIs, generates the full HTML app shell
  (Dashboard tab pre-rendered, other tabs lazy-loaded via JSON API)
- `fibery_client.py` shared FiberyClient, schema helpers, and utility functions
- `crud_handlers.py` CRUD data fetching (`fetch_tab_data`), mutation handling (`handle_action`),
  and action detection (`compute_actions`). Mission entities include a `_section` field
  (`"signed"` or `"pipeline"`) for tab splitting. Client entities are enriched with contact data
  from the Contact entity via a separate query joined by client reference.
- `api/index.py` Vercel serverless handler with authentication and six routes:
  - `GET /login` → login page (styled, password form)
  - `POST /login` → authenticate, set session cookie (24h), redirect
  - `GET /logout` → clear session, redirect to login
  - `GET /` → HTML app shell (requires auth)
  - `GET /api/data?tab=<name>` → JSON data for CRUD tabs (requires auth)
  - `POST /api/action` → CRUD mutations proxied to Fibery API (requires auth)
- `logo.png` — Air Consulting Services logo (200x105 PNG, resized from original)

### CRUD Interaction Patterns

- **Inline edit**: Double-click cell → input → Enter saves, Escape cancels → optimistic DOM update
- **Checkbox**: Immediate toggle → async POST → revert on error
- **Status dropdown**: Color-coded select → change fires async POST → update chip color
- **Create new**: Button → slide-over form → Submit → optimistic prepend → POST
- **Row click**: Name column links to Fibery entity (`/{Space}/{Type}/{public-id}`)

### CLI Modes

- `python generate_dashboard.py --no-open` — generate static HTML file
- `python generate_dashboard.py --serve` — live HTTP server refreshing on each request
- `dashboard_live.bat` — recommended Windows launcher (WSL → static HTML → Windows open)

### Fibery URL Patterns (Critical)

**NEVER** use `/fibery/space/` prefix — it renders a blank workspace settings page.

Correct patterns:
- **Database list view**: `https://{workspace}.fibery.io/{Space}/{Type}`
- **Single entity**: `https://{workspace}.fibery.io/{Space}/{Type}/{public-id}`

Rules:
- Spaces in Space name and Type name become underscores: `Project Tracking` → `Project_Tracking`.
- `{public-id}` is the integer from `fibery/public-id` field, **not** `fibery/id` (UUID).
- Always include `fibery/public-id` in API queries to build deep links.

Examples:
```
https://tokenshift.fibery.io/Project_Tracking/Mission         ← opens Mission list
https://tokenshift.fibery.io/Project_Tracking/Mission/713     ← opens Mission #713
https://tokenshift.fibery.io/Project_Tracking/Facture/214     ← opens Facture #214
```

### KPI Computation Rules (Critical)

1. **CA Produit YTD** = sum of `jours_pointes * TJM` for ALL production rows tagged `Realise`
   where period <= current month.
   - The `Realise` tag on Production Mensuelle is the authority — do NOT filter by mission pipeline status.
   - Missions marked "Prospect" can have "Realise" production when work has started but contract status
     wasn't updated.

2. **CA Facture** = sum of all invoice `Montant HT`. Note: invoice statuses may be blank in data —
   treat blank status as "Non defini", not as paid.

3. **CA Prevu Annuel** = `TJM * Jours totaux vendus` from missions with won/active status
   (En cours, Gagne, Livre). This is the full-year contractual value.

4. **Pipeline Non Pondere** = `TJM * Jours totaux vendus` from prospect/pipe missions.

5. **Pipeline Pondere** = Pipeline * probabilite.
   - Probability is stored as percentage (0-100), not decimal.
   - Apply: `prob / 100.0 if prob > 1 else prob`.

6. **Marge Brute YTD** = CA Produit YTD - total sous-traitance costs.

### Bar Chart Deduplication (Critical)

For the monthly CA chart, a mission can have BOTH a `Prevu` and a `Realise` row for the same month.
When both exist, **realise supersedes prevu** — do NOT stack them.

Implementation: two-pass approach:
1. First pass: collect all `(mission_id, month)` combinations that have `Realise` rows.
2. Second pass: process `Prevu` rows, skip any `(mission_id, month)` already in the realise set.

### Data Quality Pitfalls

- TJM values from Fibery API may come as strings → always use `safe_float()`.
- Status fields contain accented characters (e.g., "Réalisé") → use `strip_accents()` before normalize.
- The REEL Excel sheet = full-year budget, not just past actuals. After ETL, "Realise" production
  exists for future months. The YTD filter (period <= current month) handles this.

### Interactive Dashboard Architecture

Two interaction modes on every element (KPI card, bar chart column, pipeline/facture row):

1. **Hover** (`onmouseenter`) → floating popover shows entity-level detail table (missions, invoices,
   production rows). Each row name is a clickable link to the entity in Fibery.
   - Popover stays visible when mouse enters it (for scrolling): use `clearTimeout` on mouseenter.
   - Entity links inside popover use `event.stopPropagation()` to avoid triggering parent click.
   - Hide with ~250ms delay (`schedHide()`) so user can move cursor into the popover.
2. **Click** (`onclick`) → opens the relevant Fibery database list view in a new tab:
   - Mission-related KPIs and pipeline rows → `…/{Space}/Mission`
   - Facture-related KPIs and status rows → `…/{Space}/Facture`
   - Production-related KPIs and monthly bars → `…/{Space}/Production_Mensuelle`

Implementation:
- `_build_drill_data(data)` builds a JSON dict keyed by drill target (e.g., `kpi_produit`, `m_2026-01`,
  `st_prospect`, `fs_non defini`). Each value: `{"t": type, "h": [headers], "r": [{n, v, d, u}]}`.
- Fibery database URLs are built as a separate dict mapping each drill key to the correct database URL.
- Both dicts are embedded as `var D=…;` and `var U=…;` in the HTML `<script>` tag.
- The popover is a fixed-position `div` anchored near the hovered element, repositioned to stay within
  the viewport.

## Troubleshooting Playbook

If Fibery URLs land on a blank settings page:

1. Remove `/fibery/space/` from the URL path. Correct: `/{Space}/{Type}/{id}`.
2. Remove `/database/` segment. The database list view uses the same `/{Space}/{Type}` pattern.
3. Ensure spaces are replaced by underscores in both Space and Type names.

If a view crashes with unsupported expression:

1. Query view metadata via `query-views`
2. Remove invalid grouping/meta expressions
3. Delete + recreate affected views
4. Re-open with hard refresh in browser

If timeline seems empty:

1. Query interventions count with date + sous-traitant
2. Confirm `startExpression` and `yExpression` IDs
3. Set `endExpression = startExpression`
4. Validate visible time window (e.g., Feb-Jun 2026)

If days look like revenue amounts (e.g., 17,830 instead of 1.5/3/7):

1. Check Pipe/Reel has duplicated sections (days + CA)
2. Enforce ratio-based row filtering (`ratio`/`coef` > 0) before melt aggregation
3. Rebuild Production rows (delete + reimport) because upsert alone does not remove bad legacy rows
4. Re-check:
   - `max(Project Tracking/Jours pointes)` should be realistic (typically < 30)
   - no `2025-01` period leakage when importing `2026 Pipe/REEL`

If KPI values look wrong:

1. Probe data first — run entity queries to see actual status distributions, TJM values,
   and production row counts before assuming code bugs.
2. Check mission status vs production tag alignment — most "Realise" production may be on
   "Prospect" missions (status not updated). Never filter CA Produit by mission status.
3. Check for prevu/realise double-counting in bar charts — same mission+month with both tags.
4. Verify `Probabilite` scale: 50 means 50%, not 0.50.

## Security

- Never hardcode real API tokens in committed files.
- Load secrets from `.env` (example file only with placeholders).
- The `--serve` mode binds to `0.0.0.0` for WSL compatibility but the token stays server-side,
  never exposed to the HTML.

## Vercel Deployment (Fibery Embed)

The dashboard can be deployed as a Vercel serverless function and embedded inside Fibery:

Structure:
```
api/index.py          # Vercel handler — routes GET /, GET /api/data, POST /api/action
fibery_client.py      # Shared FiberyClient, schema helpers, utilities
crud_handlers.py      # CRUD data fetching, mutations, action detection
generate_dashboard.py # Core dashboard + app shell HTML generation
vercel.json           # Routes all requests to api/index.py
requirements.txt      # Only requests + python-dotenv (no pandas)
requirements-etl.txt  # Full ETL deps (pandas, openpyxl) for local use
.vercelignore         # Excludes .env, ETL scripts, probe scripts
```

Environment variables (set in Vercel project settings, NOT in code):
- `FIBERY_BASE_URL` — e.g. `https://tokenshift.fibery.io`
- `FIBERY_API_TOKEN` — Fibery API token
- `APP_PASSWORD` — Shared password for login page (optional; if unset, auth is disabled)

Headers set by the function:
- `Content-Security-Policy: frame-ancestors 'self' https://*.fibery.io` — allows Fibery iframe embed
- `CDN-Cache-Control: s-maxage=300` — 5-minute CDN cache to avoid hammering Fibery API
- `Cache-Control: no-cache` — browser always requests fresh (served from CDN cache if < 5 min)

Fibery embed: in any Fibery Document, type `/embed` and paste the Vercel deployment URL.
Name the document "Cockpit Direction" or similar for easy sidebar access.

Deployment gotchas:
- `vercel.json`: `functions` and `builds` properties **cannot coexist**. Use `functions` + `rewrites`.
- Env var injection via CLI: `echo "value" | vercel env add NAME` can fail with `missing_value`.
  Use `vercel env add NAME production --value "the-value"` instead.
- Vercel Python handler class MUST be lowercase `handler` (not `Handler`).
- GitHub repo: `pm78/tokenshift-dashboard` (private).

### Fibery Document Content API

Fibery stores rich-text document bodies separately from the entity/view metadata:

- **Read**: `GET https://{workspace}.fibery.io/api/documents/{secret}` → returns `{"content": "..."}`
- **Write**: `PUT https://{workspace}.fibery.io/api/documents/{secret}` with body `{"content": "markdown string"}`
- The `{secret}` is the UUID from `fibery/document-secret` field on the entity or view.
- Content can be a markdown string or Prosemirror JSON string.

### Fibery Embed Automation Limitation (Critical)

The `/embed` command in Fibery documents is **client-side only** — it cannot be automated via API.

What was tried and failed:
1. Created a `document` view via `create-views` API — view created successfully.
2. Wrote Prosemirror JSON with an `embed` node (`type: "embed"`, `attrs: {src: url}`) via
   `PUT /api/documents/{secret}`.
3. Result: Fibery interpreted the embed src as a route, navigating to `/fibery/space/embed` → blank
   "You don't have access to space embed" page.
4. Even markdown content stored via the API renders, but embed blocks cannot be injected this way.

**Correct workflow**: Create the document view via API (or manually), then have the user manually
type `/embed` in the Fibery editor and paste the Vercel URL. This is a one-time setup.

## WSL2 / Windows Interop Notes

- WSL2 localhost forwarding to the Windows host is unreliable. A server running on `localhost:8050`
  inside WSL may show "Ce site est inaccessible" in Windows Chrome.
- Preferred approach: use a `.bat` launcher that calls `wsl python3 script.py --no-open` to generate
  a static HTML file, then opens it with `start ""` — no server dependency.
- API tokens are read from `.env` inside WSL. The generated HTML is a static file with no secrets.
