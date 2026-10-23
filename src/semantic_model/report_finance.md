# Report: rp_finance (Finance app)

Built on `sm_finance` in `hh-finance-dev`, published as the **Finance** app (audiences in `tenant.yaml › apps`).
Every page has the same header: a text card with **[Data Freshness Banner]**, then the page's slicers.
Theme: one accent colour for the ledger, one for the source systems, red only for "Investigate" and "Stale".

## Page 1: Overview

| Visual | Fields |
|---|---|
| Slicer (dropdown) | `dim_date[fiscal_year_label]` (default: current FY) |
| 4 cards | `[Revenue]`, `[Expenses]`, `[Net Surplus]`, `[Earned Revenue %]`, each with the `Time Intelligence[Calculation]` filter on **FYTD** |
| Clustered column + line | X: `dim_date[month_name]` (fiscal order); columns: `[Revenue]`, `[Expenses]`; line: `[Net Surplus]` |
| Matrix | Rows: `dim_account` › Account Hierarchy; columns: `Time Intelligence[Calculation]` filtered to FYTD, PY FYTD, YoY %; values: `[Revenue]` (switch to `[Expenses]` with a second matrix or a field parameter) |

## Page 2: Revenue reconciliation (the month-end page)

| Visual | Fields |
|---|---|
| Slicers | `dim_date[fiscal_year_label]`, `recon_revenue_to_gl[revenue_stream]`, `recon_revenue_to_gl[status]` |
| 4 cards | `[Reconciled %]`, `[Lines to Investigate]`, `[Open Items]`, `[Variance]` |
| Matrix | Rows: `recon_revenue_to_gl[month_start]`; columns: `recon_revenue_to_gl[revenue_stream]`; values: `[Variance]`, with background colour rules: red when `[Lines to Investigate]` > 0, green otherwise |
| Table "Lines to investigate" (visual filter `status` = Investigate) | `month_start`, `revenue_stream`, `fund_code`, `[Source Amount]`, `[Ledger Amount]`, `[Variance]`, `cause`, `resolution` |

Talking point: each line has a story (cut-off, unposted batch, reclass, rentals cancelled after invoicing, returns timing). Finance writes the cause in `fin.recon_note`; the next load shows it here.

## Page 3: Data trust

| Visual | Fields |
|---|---|
| Table | `source_freshness[source_name]`, `[Last Loaded (UTC)]`, `[Data Through]`, `source_freshness[expected_refresh]`, `[Freshness Status]` (red when Stale) |
| Cards | `[Out of Balance]` (always $0.00), `[Open Items]` |

## Publish

1. Save the report as **rp_finance** in `hh-finance-dev`, then Source control › Commit.
2. Workspace › **Create app** › name *Finance*. Add the three pages.
3. **Audience** tab: create the audiences from `tenant.yaml › apps`:
   * *Finance team*: `sg-hh-analysts-finance`, tick **Allow people to build content with the data** (Excel, their own reports).
   * *Leadership*: `sg-hh-executives`, Build unticked.
4. Publish. In the model's Security, the **Finance** role has both groups, so model security applies to everyone who isn't a workspace member.

In production the app is published from `hh-finance-prod`, after the deployment pipeline; a DEV app is only for the demo.
