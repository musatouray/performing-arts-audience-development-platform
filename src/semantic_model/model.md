# Semantic models — build spec

Four models, one per business domain. All are **Direct Lake on OneLake** over `wh_gold`.
They're built in the **DEV BI workspace** (web modeling or Power BI Desktop), then Git-synced and promoted by deployment pipeline.

| Model | Workspace | Audience | Endorsement |
|---|---|---|---|
| `sm_audience_development` | `hh-audience-*` | Ticketing, marketing, development analysts; leadership | **Certified** (after review) |
| `sm_education_impact` | `hh-education-*` | Education & Community staff, grants team | **Certified** |
| `sm_finance` | `hh-finance-*` | Finance office (CFO), auditors | **Certified** |
| `sm_operations` | `hh-operations-*` | Hall Operations, Event Services, Rentals | **Certified** |

## Why Direct Lake on OneLake (ADR-004)

* There's no import refresh copy of the data. Gold changes show up in reports as soon as `usp_load_gold` commits, with no scheduled refresh to babysit.
* It **doesn't fall back to DirectQuery**, unlike Direct Lake on the SQL endpoint, so performance stays predictable.
* Security is enforced **in the model** (RLS/OLS). Warehouse T-SQL RLS/DDM does **not** apply on this path (see `60_security.sql`).
* **Author access:** BI developers read `wh_gold` through an **item share** (Read, ReadData, ReadAll), not a Data Platform workspace role. See `scripts/09_verify_item_shares.py`.
* **Connection:** use a **fixed identity** (a shareable cloud connection owned by the platform team) so report viewers don't need OneLake read access to Gold. The model's RLS roles then decide what each viewer sees.
* **Fallback:** if a future requirement needs SQL views, switch that model to Direct Lake on SQL or Import. It's a per-model decision, not a platform one.

## sm_audience_development

### Tables (from `wh_gold`)

| Model table | Source | Notes |
|---|---|---|
| `dim_date` | `dim.date` | **Mark as date table** (`date`). Sort `month_name` by `fiscal_month_num`. Hide keys. |
| `dim_patron` | `dim.patron` | Hide `patron_key`, `scd_hash`, `valid_from`, `valid_to`. **OLS: hide `email`, `phone`, `address_line1` from the Audience role.** |
| `dim_performance` | `dim.performance` | Already carries venue + season (denormalised). Hierarchy: Season › Series › Performance. |
| `dim_channel` | `dim.channel` | |
| `dim_campaign` | `dim.campaign` | |
| `dim_fund` | `dim.fund` | |
| `fact_ticket_sales` | `fact.ticket_sales` | Hide all keys. |
| `fact_gifts` | `fact.gifts` | Hide all keys. |
| `fact_subscriptions` | `fact.subscriptions` | |
| `dim_email_campaign` | `dim.email_campaign` | Marketing. Campaign type, series promoted, audience segment. |
| `fact_email_results` | `fact.email_campaign_results` | One row per campaign, latest numbers. |
| `fact_email_click` | `fact.email_click` | One row per click, linked to the patron (no email address in Gold). |
| `fact_ad_spend` | `fact.ad_spend_daily` | One row per day per ad campaign. |
| `sec_user_venue` | `sec.user_venue` | **Hidden.** Used only by dynamic RLS. |
| `source_freshness` | `rpt.source_freshness` | Snapshot written by each Gold load. Data Trust measures as in [`finance_measures.dax`](finance_measures.dax). |
| `_Measures` | (calculated, empty) | Holds all measures from `measures.dax`, in display folders. |

`dim.venue` isn't imported. Venue attributes already live on `dim_performance`, and a second path to venue would make the filters ambiguous.

### Relationships (all many-to-one, single direction, fact → dim)

| From (many) | To (one) | Active | Why |
|---|---|---|---|
| `fact_ticket_sales[performance_date_key]` | `dim_date[date_key]` | ✅ | Default: "which season/show" |
| `fact_ticket_sales[order_date_key]` | `dim_date[date_key]` | ❌ | Used via `USERELATIONSHIP` for sales pacing |
| `fact_ticket_sales[patron_key]` | `dim_patron[patron_key]` | ✅ | |
| `fact_ticket_sales[performance_key]` | `dim_performance[performance_key]` | ✅ | |
| `fact_ticket_sales[channel_key]` | `dim_channel[channel_key]` | ✅ | |
| `fact_gifts[gift_date_key]` | `dim_date[date_key]` | ✅ | |
| `fact_gifts[patron_key]` | `dim_patron[patron_key]` | ✅ | |
| `fact_gifts[campaign_key]` | `dim_campaign[campaign_key]` | ✅ | |
| `fact_gifts[fund_key]` | `dim_fund[fund_key]` | ✅ | |
| `fact_subscriptions[purchase_date_key]` | `dim_date[date_key]` | ✅ | |
| `fact_subscriptions[patron_key]` | `dim_patron[patron_key]` | ✅ | |
| `fact_email_results[email_campaign_key]` | `dim_email_campaign[email_campaign_key]` | ✅ | |
| `fact_email_results[send_date_key]` | `dim_date[date_key]` | ✅ | |
| `fact_email_click[email_campaign_key]` | `dim_email_campaign[email_campaign_key]` | ✅ | |
| `fact_email_click[patron_key]` | `dim_patron[patron_key]` | ✅ | Who clicked |
| `fact_email_click[click_date_key]` | `dim_date[date_key]` | ✅ | |
| `fact_ad_spend[ad_date_key]` | `dim_date[date_key]` | ✅ | Series is a column, not a relationship: measures use `TREATAS` to `dim_performance[series]` |

There are no bi-directional relationships. Cross-fact questions ("buyers who also give") are answered in DAX with `SUMMARIZE` / `INTERSECT` on `patron_id`, not by opening up filter directions.

### Measures

See [`measures.dax`](measures.dax). There's also one **calculation group**, "Time Intelligence" (Current, FYTD, PY, PY FYTD, YoY, YoY %), which uses a fiscal year ending 30 June.

### Security

See [`rls_roles.md`](rls_roles.md).

## sm_education_impact

* **Tables:** `dim_date`, `dim_program`, `dim_school`, `fact_education_sessions`.
* **Measures:**
  * `Sessions = COUNTROWS(fact_education_sessions)`
  * `Participant Touchpoints = SUM(fact_education_sessions[participants])`
  * `Schools Served = CALCULATE(DISTINCTCOUNT(dim_school[school_id]), dim_school[school_key] > 0)`
  * `Title I Share % = DIVIDE(CALCULATE([Participant Touchpoints], dim_school[is_title_i] = TRUE()), [Participant Touchpoints])`
  * `Teaching Artist Hours = SUM(fact_education_sessions[teaching_artist_hours])`
* **Privacy by design:** there's no patron or student table in this model. Education staff can't reach donor data, because the separate model is the boundary.

## Report pages

### Audience & Development app

1. **Executive Overview.** KPI cards (Net Ticket Revenue, Sell-Through %, Gift Revenue, Donor Retention %, Subscriber Renewal %) with FYTD vs PY from the calc group, plus a revenue trend by fiscal month.
2. **Season & Performance.** A matrix of Season › Series › Performance with sell-through conditional formatting, a scatter of sell-through vs average ticket price, and a sales-pacing line (`Tickets Sold by Order Date`, by days before show).
3. **Patrons.** New vs returning buyers, region map (`dim_patron[region]`), channel mix, and Buyer-to-Donor Conversion %.
4. **Fundraising.** Campaign progress vs goal, the donor pyramid (gift bands), a LYBUNT list (table: patron, last-year amount), and a retention trend.
5. **Data Trust.** Source freshness (`source_freshness`: last load, data through, Fresh/Stale), plus DQ pass rate and quarantined rows (from `rpt.vw_dq_latest` / `vw_pipeline_health` via a paginated report).

## sm_finance

The Finance spoke (`hh-finance-*`, ADR-009), for the CFO's office. Direct Lake on OneLake over `wh_gold`.

### Tables (from `wh_gold`)

| Model table | Source | Notes |
|---|---|---|
| `dim_date` | `dim.date` | Mark as date table. Sort `month_name` by `fiscal_month_num`. |
| `dim_account` | `fin.dim_account` | Hierarchy: Type › Group › Account. Sort by `account_code`. |
| `dim_department` | `fin.dim_department` | |
| `dim_fund` | `dim.fund` | The same fund dimension as the audience model; `mip_fund_code` is the ledger's code. |
| `fact_gl_entry` | `fin.fact_gl_entry` | One row per journal line. Hide keys. |
| `recon_revenue_to_gl` | `fin.recon_revenue_to_gl` | Monthly reconciliation, with finance's notes. |
| `source_freshness` | `rpt.source_freshness` | Snapshot written by each Gold load; feeds the Data Trust page. |
| `_Measures` | (empty) | [`finance_measures.dax`](finance_measures.dax) |

### Relationships (many-to-one, single direction)

| From (many) | To (one) | Active |
|---|---|---|
| `fact_gl_entry[effective_date_key]` | `dim_date[date_key]` | ✅ |
| `fact_gl_entry[posted_date_key]` | `dim_date[date_key]` | ❌ (posting lag analysis via `USERELATIONSHIP`) |
| `fact_gl_entry[account_key]` | `dim_account[account_key]` | ✅ |
| `fact_gl_entry[fund_key]` | `dim_fund[fund_key]` | ✅ |
| `fact_gl_entry[department_key]` | `dim_department[department_key]` | ✅ |
| `recon_revenue_to_gl[month_start]` | `dim_date[date]` | ✅ |
| `recon_revenue_to_gl[fund_code]` | `dim_fund[mip_fund_code]` | ✅ |
| `recon_revenue_to_gl[gl_account_code]` | `dim_account[account_code]` | ✅ |

The same "Time Intelligence" calculation group as the audience model (fiscal year ending 30 June): one column, `Calculation`, with Current, FYTD, PY, PY FYTD, YoY and YoY %. Its items clear `dim_date` filters themselves (`REMOVEFILTERS`), so they work whether or not the date table is marked. Implicit measures are off, as calculation groups require.
Role: **Finance** (`sg-hh-analysts-finance`), no row filter. The model itself is the boundary: only finance gets it.

### Report pages

1. **Income Statement.** Revenue, Expenses, Net Surplus by account group and month, FYTD vs PY (calc group), earned vs contributed mix.
2. **Revenue Reconciliation.** Month × revenue stream (× fund) with Source, Ledger, Variance and status colour, and the lines to investigate with cause and resolution. This page replaces the month-end spreadsheet.
3. **Data Trust.** Source freshness, Out of Balance (always 0), open reconciliation items.

## sm_operations

The Operations spoke (`hh-operations-*`, ADR-009), for Hall Operations, Event Services and Rentals. Direct Lake on OneLake over `wh_gold`. No ledger tables: rental revenue here is what Diese records; finance reconciles it to the ledger in `sm_finance`.

### Tables (from `wh_gold`)

| Model table | Source | Notes |
|---|---|---|
| `dim_date` | `dim.date` | Mark as date table. |
| `dim_room` | `dim.room` | Hierarchy: Room type › Room. |
| `dim_event` | `dim.event` | `client_name` can name a private client; the model is limited to the operations team, who deal with those clients. |
| `dim_performance` | `dim.performance` | For concert events: which show, series and season. |
| `fact_venue_booking` | `fact.venue_booking` | Hide keys. |
| `source_freshness` | `rpt.source_freshness` | Data Trust page. |
| `_Measures` | (empty) | [`operations_measures.dax`](operations_measures.dax) |

### Relationships (many-to-one, single direction)

| From (many) | To (one) | Active |
|---|---|---|
| `fact_venue_booking[booking_date_key]` | `dim_date[date_key]` | ✅ |
| `fact_venue_booking[event_key]` | `dim_event[event_key]` | ✅ |
| `fact_venue_booking[room_key]` | `dim_room[room_key]` | ✅ |
| `dim_event[performance_key]` | `dim_performance[performance_key]` | ✅ (snowflake: event → performance; one direction only) |

Role: **Operations** (`sg-hh-analysts-operations`), no row filter.

### Report pages

1. **Halls & Rentals.** Utilisation % by room and month, concert vs rental vs rehearsal hours, rental revenue and average fee, top rental clients.
2. **Calendar.** Upcoming confirmed and tentative bookings by room, so holds are visible before they lapse.
3. **Data Trust.** Source freshness, unlinked concerts (Diese events with no Tessitura performance).

### Excel: the cube replacement

Finance keeps working in Excel, against the certified model instead of a cube:
Excel › Data › Get Data › From Power Platform › **From Power BI semantic model** › `sm_finance` (or any certified model) › PivotTable. Then PivotTable Analyze › OLAP Tools › **Convert to Formulas** turns it into `CUBEVALUE` cells that survive any layout, for example:

```
=CUBEVALUE("<connection>", "[Measures].[Revenue]", "[dim_date].[fiscal_year_label].&[FY2026]")
=CUBEVALUE("<connection>", "[Measures].[Variance]", "[recon_revenue_to_gl].[revenue_stream].&[Contributions]", "[dim_date].[fiscal_year_label].&[FY2026]")
```

Same definitions as the reports, same security, refreshed by the same daily load. No cube processing to schedule.
