# Semantic models — build spec

Two models, one per business domain. Both are **Direct Lake on OneLake** over `wh_gold`.
They're built in the **DEV BI workspace** (web modeling or Power BI Desktop), then Git-synced and promoted by deployment pipeline.

| Model | Workspace | Audience | Endorsement |
|---|---|---|---|
| `sm_audience_development` | `hh-audience-*` | Ticketing, marketing, development analysts; leadership | **Certified** (after review) |
| `sm_education_impact` | `hh-education-*` | Education & Community staff, grants team | **Certified** |

## Why Direct Lake on OneLake (ADR-003)

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
| `sec_user_venue` | `sec.user_venue` | **Hidden.** Used only by dynamic RLS. |
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
5. **Data Trust.** Last load time, DQ pass rate by entity, quarantined rows (from `rpt.vw_dq_latest` / `vw_pipeline_health` via a small Import model or a paginated report).
