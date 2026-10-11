# Admin reports links & Reports tab

**Date:** 2026-10-11  
**Status:** Approved for planning  
**Scope:** Admin console analytics — link to public reports; new Reports tab with dense table

## Goal

Operators can open any fact-check report from the admin console without leaving the console (new browser tab), and can browse all reports in the selected date range in a dedicated tab.

## Decisions

| Decision | Choice |
|----------|--------|
| Reports tab content | Dense table: verdict, URL, summary, date, open link |
| Link target | `/report?id={id}` in a new tab (`target="_blank"`, `rel="noopener noreferrer"`) |
| Data source | Extend existing `/api/admin/analytics` (no new list endpoint) |
| Date range | Existing 7d / 30d top-bar control applies to the Reports tab |

## Architecture

### Backend

`aggregate_analytics` already receives `reports_in_range` but only returns `recent_reports` (first 10). Add `reports_in_range` to the analytics JSON response so the client can render the full table.

Each list item already includes: `id`, `verdict`, `url`, `context_summary`, `created_at` (from `reports_store._item_from_stored`).

No new API routes. Limit remains the existing `list_reports_since(..., limit=500)` used by the admin analytics route.

### Frontend (`AdminDashboard.tsx`)

1. Extend `Tab` / `NAV` with `reports` (label **Reports**, short hint e.g. “Fact-check history”).
2. Extend `Analytics` type with `reports_in_range` (same item shape as `recent_reports`, plus `created_at`).
3. **Overview → Recent reports:** each row links to `/report?id={id}` in a new tab (title or dedicated Open control).
4. **Reports tab:** one `admin-panel` with a dense table over `analytics.reports_in_range` for the selected range:
   - Verdict (existing pill styling)
   - URL (fallback to id)
   - Summary (`context_summary`)
   - Date (`created_at`, via existing `formatWhen`)
   - Open (new-tab link)
5. Empty state when the list is empty. Reuse existing admin CSS patterns; add minimal table styles in `globals.css` only if needed.

## Out of scope

- Pagination / search / filter beyond the existing range toggle
- In-admin report preview / embedding
- Separate `/api/admin/reports` endpoint
- Changing public report page behavior

## Success criteria

- Overview recent reports open the correct public report in a new tab.
- Reports nav tab lists all in-range reports in a dense table with the same open behavior.
- Changing 7d/30d refreshes the Reports table via existing analytics fetch.
- No new backend route; analytics response includes `reports_in_range`.
