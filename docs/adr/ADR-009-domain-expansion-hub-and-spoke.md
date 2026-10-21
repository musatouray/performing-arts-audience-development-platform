# ADR-009: Adding venue operations and finance: hub and spoke, not one platform per domain

**Status:** Accepted and built (dev): MIP and Diese ingestion, `fin.*`, `dim.event`, `dim.room`, `fact.venue_booking`, the reconciliation and the `hh-finance-{env}` family. See [`70_finance_and_venue_ops.sql`](../../src/warehouse/70_finance_and_venue_ops.sql).

## Context

Two more source systems are planned, alongside Tessitura (database and REST API), education and marketing:

- **Venue operations**: a booking system (Dièse-style) that schedules the halls and rooms: public performances, external rentals, rehearsals and education sessions.
- **Fund accounting**: the general ledger (MIP-style), where ticket and gift revenue is finally posted and audited.

That raises the question of whether each business domain (ticketing, finance, venue operations) should get its own data workspaces and pipelines, or whether the current structure should be extended.

## Options

| Option | For | Against |
|---|---|---|
| **A. A data platform per domain** (data mesh) | Each domain owns its data end to end | Venue, date, season and performance are needed by every domain, so each would rebuild them and they'd drift. Questions that cross domains, such as concerts vs rentals by hall or sales vs ledger, become cross-workspace joins. Needs an engineering team per domain. |
| **B. Hub and spoke** (current structure, extended) | One governed copy of the shared dimensions; cross-source questions are a single join; a small central team can run it | The hub team is a bottleneck if many domains want changes at once |

## Decision

**B, hub and spoke.**

- **Hub:** `hh-dataplatform-{env}` keeps all ingestion, Bronze, Silver and the one Gold warehouse. The new sources land there like the existing ones.
- **Spokes:** one BI workspace family per consuming domain, holding its semantic models, reports and app, each matching a part of the organisation:

  | Spoke | Serves | Workspaces | Model |
  |---|---|---|---|
  | Audience & Development | Marketing, Ticketing Services, Development | `hh-audience-{env}` | `sm_audience_development` |
  | Education & Community | Music Education and Community Programs | `hh-education-{env}` | `sm_education_impact` |
  | **Finance** | Finance, CFO office | `hh-finance-{env}` | `sm_finance` |
  | **Operations** | Hall Operations, Event Services, Rentals | `hh-operations-{env}` | `sm_operations` |

- **Finance and Operations are separate spokes**, not one: they answer to different leaders, and the ledger is far more sensitive than the hall calendar. With separate spokes, the ledger never reaches the operations workspace, and the calendar can go to a wider operations audience. The cost is three more workspaces, a deployment pipeline and an app. The cross-question ("rental revenue vs the ledger") still works because both spokes read the same Gold in the hub: the reconciliation lives in Finance and reads Diese's side from Gold.
- **Isolation for sensitive data** comes from security, not from separate platforms: finance tables live in their own Gold schema (`fin.*`) with their own grants, and their own model with its own roles (ADR-006).

## Data design

**Ingestion (ADR-003 rules applied):**

| Source | Tool | Why |
|---|---|---|
| Venue bookings | API notebook, the `nb_05` pattern, or a shortcut if the vendor drops files | Booking systems usually expose a REST API; confirm what the vendor offers |
| General ledger | Incremental Copy job through the gateway, read-only login, after the nightly close | Finance needs exact, auditable copies; a Dataflow can't run without a user (ADR-003) |

**Gold additions:**

| Object | Grain or role | Notes |
|---|---|---|
| `dim.event` | One row per booked event (bridge) | Links a booking-system event to a ticketing performance when one exists. Columns: `event_key`, `booking_event_id`, `performance_key` (or -1), `venue_key`, `event_type` (Concert, Rental, Rehearsal, Education), `status`. Many bookings, such as rentals and rehearsals, have no ticketed performance, so the link is optional by design. Unmatched public events are counted on the integrity view. |
| `fact.venue_booking` | One event per room per day | `event_key`, `venue_key`, `date_key`, `hours_booked`. Answers hall utilisation across concerts, rentals and rehearsals. |
| `dim.venue` | Existing | `capacity` already drives sell-through; it's now shared by ticketing and venue operations |
| `fin.fact_gl_entry` | One journal line | With `fin.dim_account`, `fin.dim_department` and the existing `dim.fund` (ADR-001) |

**Reconciliation, the first finance deliverable:** Tessitura posts ticket, subscription and gift revenue to the ledger, and Diese's rental fees are invoiced through it, so the two sides must agree.

- `fin.recon_revenue_to_gl`, rebuilt by every Gold load: month × revenue stream (single tickets, subscriptions, contributions by fund, venue rentals) × fund, with source amount, ledger amount, variance, tolerance (the larger of $1,000 or 1%) and a status (Matched, Within tolerance, Investigate).
- It's a table computed by the load, not a view, because the load runs as the ETL identity and sees every gift, anonymous ones included; people only ever see the monthly totals.
- Finance explains variances in `fin.recon_note` (cause, note, resolution, owner); the next load copies the note onto the line, and `rpt.vw_recon_revenue_to_gl` shows it live.
- Shown on the finance model's Reconciliation and Data Trust pages; open items over tolerance block certification of that month's numbers.
- `sm_finance` holds the ledger and the reconciliation; `sm_operations` holds the hall calendar and has no ledger tables at all, so no hiding rules are needed.

## Build order

1. Data freshness and the cube-style semantic model on the existing Gold (no new source needed).
2. Venue bookings: synthetic data, ingestion, `dim.event`, `fact.venue_booking`.
3. General ledger: synthetic data, ingestion, `fin.*`, the reconciliation view.
4. The `hh-finance-{env}` and `hh-operations-{env}` families in `tenant.yaml`, scripts 00 to 05, then their models.

## Consequences

- The hub team owns more sources; the config-driven loads (`sources.yaml`) keep each new source to config plus one ingestion item.
- The event bridge needs an owner: Operations confirms the performance-to-event mapping for unmatched public events.
- Domains follow data ownership, not the org chart for its own sake: if rentals turn out to be owned by Finance rather than Event Services, the Diese tables move spokes with a `tenant.yaml` change, not a rebuild.
- Cross-domain questions stay simple: one Gold warehouse, shared dimensions.

> [!NOTE]
> *"Hub and spoke: one governed platform owns the shared data, and each domain owns its own models and reports. Venue and finance join through the same date, venue and event dimensions, so 'concerts vs rentals by hall' and 'box office vs the ledger' are one query, not a project. I'd split the platform by domain only when each domain has its own data team."*

**Revisit when:**

- A domain gets its own data engineers and wants to own its pipelines: move that domain to its own data workspaces (data mesh), keeping the shared dimensions in the hub.
- The hub team becomes a bottleneck for changes across several domains at once.
