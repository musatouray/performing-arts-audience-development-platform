# Project to-do

What's built, and what's left. Ticked items run in the tenant today; unticked items are open, ordered by priority within each section.

*Last updated: 27 October 2026*

---

## 1. Platform foundation

- [x] Entra security groups and two tier-separated service accounts (`svc-fabric-dataflows-nonprod`, `-prod`)
- [x] Six domains (Harmonia Hall plus five business domains) and 15 workspaces (5 families × DEV/TEST/PROD), created from `config/tenant.yaml`
- [x] Core items in every stage: `lh_bronze`, `lh_silver`, `wh_gold`
- [x] Five deployment pipelines `dp-hh-*`
- [x] Git integration on the DEV workspaces; CI on every push (lint, config validation, tests)
- [x] Workspace identities per stage, each with *Storage Blob Data Reader* on the marketing container
- [ ] Run the tenant-settings audit (`scripts/08_audit_tenant_settings.py`) and commit the result
- [ ] Install the Capacity Metrics app and record the daily load's CU cost

## 2. Ingestion (six sources, four patterns)

- [x] Tessitura database and MIP ledger: Copy jobs through the on-premises gateway, read-only login per system, incremental
- [x] Tessitura API and Diese API: one config-driven notebook (`nb_05_api_ingest`)
- [x] Education: Dataflow Gen2 owned by the tier's service account, one connection set per tier
- [x] Marketing: OneLake shortcut to ADLS Gen2 with workspace-identity access
- [ ] Move the gateway off a personal laptop (an always-on VM or a VNet data gateway), so loads don't depend on one computer being awake

## 3. Bronze and Silver

- [x] Bronze reconciliation against source manifests (a mismatch stops the pipeline)
- [x] 43 data-quality rules in YAML (28 error, 15 warn), quarantine with the rule broken, pass rates per run
- [x] Deduplication, hash-based MERGE, identity resolution into `core.patron`
- [x] OneLake security on Silver: one role, *DataScienceReaders*
- [ ] Build `pl_weekly_maintenance` (runs `nb_90_maintenance`: `OPTIMIZE` and `VACUUM`) and schedule it for Sunday night

## 4. Gold warehouse

- [x] Star schema: conformed dimensions, SCD2 patron, incremental facts in transactions, unknown members
- [x] Finance: ledger, budget spread to days, cash flow by source module, revenue-to-ledger reconciliation (22 planted exceptions caught)
- [x] Source freshness view and snapshot; load log tied to the pipeline `run_id`
- [x] SQL security: grants per group, masked contact details, row-level security on anonymous gifts
- [x] Schema deployed to every stage from the repo (`scripts/13_deploy_gold_sql.py`), every file safe to re-run
- [ ] Redeploy DEV's objects with the script, so the deployment-pipeline comparison stops flagging comment-only differences

## 5. Finance product

- [x] `sm_finance` (Direct Lake on OneLake): *Time Intelligence* calculation group, DAX user-defined functions, field parameter, Statement of Activities layout table
- [x] RLS role *Finance* (analyst and executive groups); fixed-identity connection with single sign-on off
- [x] `rp_finance` generated from code: Overview, Statement of Activities, Cash Flow, Reconciliation, two detail pages, About this Data
- [x] *Finance Pulse* app in PROD: *Finance team* (with Build) and *Leadership*
- [x] Excel live connection tested as a finance user (PivotTable and `CUBEVALUE`)
- [x] Endorsement in PROD: `wh_gold` Certified, `lh_silver` Promoted
- [ ] Endorse `sm_finance` Certified; remove the *Master data* badge from `lh_bronze` (raw data stays unendorsed)
- [ ] Refresh `sm_finance` as the last step of `pl_daily_load` and turn off automatic updates, so users never see a half-finished load
- [ ] Bind the fixed-identity connection to a **service principal** instead of a personal account
- [ ] Remove obsolete measures (`Statement FYTD`, `Statement PY FYTD`, `Statement vs PY`, `Statement vs PY %`); move the older "vs PY" pills onto the UDFs
- [ ] Add descriptions to every table, column and measure (also needed by the AI items in section 9)

## 6. Release and environments

- [x] Data platform and finance promoted DEV › TEST › PROD through deployment pipelines
- [x] Stage-specific values from variable libraries (`vl_platform`, `vl_finance`); Direct Lake rebind notebook after each deployment
- [x] Two-pass first load for a new stage, documented in the operator manual
- [ ] Replace the `%pip install` cell in `nb_rebind_sm_finance` with a Fabric **Environment** that has `semantic-link-labs` pinned
- [ ] Pull-request-gated deployments with `fabric-cicd` and a service principal (the documented scale-up path in ADR-005)

## 7. Security and governance

- [x] Groups only; builders in workspaces, consumers through apps; Viewer-only for builders in PROD
- [ ] Sensitivity labels: Public, Internal, Confidential created and published in Purview (waiting up to 24 hours to propagate), then:
  - [ ] Enable the three *Information protection* tenant settings
  - [ ] Label PROD `wh_gold` and `lh_silver` *Confidential*; check `sm_finance`, `rp_finance` and Excel exports inherit it
- [ ] Take the analyst groups off DEV `wh_gold`: set `environments: [test, prod]` (or `[prod]`) for their share in `tenant.yaml`, then remove the DEV share
- [ ] Remove `sg-hh-analysts-finance` as Viewer on `hh-finance-test` outside sign-off periods (or create a sign-off group)
- [ ] Activator alerts: an error-severity rule with failing rows in `dq.dq_results`, and any source *Stale* in `rpt.source_freshness`
- [ ] OneLake catalog › Govern: review ownership, labels and endorsement coverage

## 8. Other business domains

- [ ] `sm_audience_development` and the *Audience & Development* app (ticketing, subscriptions, donor retention, LYBUNT)
- [ ] `sm_operations` and the *Operations* app (hall utilisation, rentals, events linked to performances)
- [ ] `sm_education_impact` and the *Education Impact* app
- [ ] A paginated report to show the SSRS migration path, for example a board pack or donor acknowledgement letters

---

## 9. AI on Fabric

The platform is built for this: governed, documented Gold, certified models with RLS, and freshness and quality signals. These items put AI on top of it.

### 9.1 Prerequisites

- [ ] **A paid capacity, F2 or larger.** Data agents need paid Fabric capacity; the trial capacity used so far isn't enough. A pay-as-you-go F2 that's paused outside working hours keeps the cost low.
- [ ] Tenant settings: Copilot and Azure OpenAI, *Users can create and share Fabric data agents*, and cross-geo processing and storage if the capacity's region requires it
- [ ] Keep the agent and its data sources on capacities **in the same region**, otherwise queries fail
- [ ] Descriptions and synonyms on `sm_finance` tables, columns and measures (section 5); agents answer better from a well-described model

### 9.2 Fabric Data Agent: *Finance Analyst*

- [ ] Create the agent in `hh-finance-dev` with two sources: `sm_finance` (certified measures) and `wh_gold` (the `rpt` views)
- [ ] Agent instructions: fiscal year runs July to June; use `sm_finance` for revenue, expenses, budget and cash; use `rpt.vw_recon_revenue_to_gl` for reconciliation questions; "donor" means a patron with a gift
- [ ] Example SQL queries for `wh_gold` (up to 100 per source; semantic models don't take examples)
- [ ] Test as the finance user: answers respect RLS, and nothing comes back she can't see in the app
- [ ] Promote through `dp-hh-finance`; publish to Microsoft Teams and Microsoft 365 Copilot
- [ ] Check answers against the report for ten common questions before sharing ("FY2026 revenue vs budget", "which funds have reconciliation issues")

### 9.3 Fabric IQ: a Harmonia Hall ontology

- [ ] Start the ontology from `sm_finance` and the Gold dimensions
- [ ] Entity types: Patron, Gift, Order, Performance, Season, Venue, Room, Event, Fund, Account
- [ ] Relationships: a patron *buys* an order *for* a performance; a patron *gives* a gift *to* a fund; an event *uses* a room *in* a venue; an event *is* a performance (the Diese-to-Tessitura link); a fund *posts to* an account
- [ ] Properties bound to Gold and the semantic model, so they stay live
- [ ] Rules: a reconciliation line outside tolerance for more than 3 days notifies finance; a source *Stale* notifies data engineering
- [ ] Graph questions that cut across systems: "ticket buyers at the Spring season who have never given", "rentals in the Recital Hall with no matching Tessitura performance"
- [ ] Add the ontology as a source of the *Finance Analyst* agent

### 9.4 Operations agent (stretch)

- [ ] Watch `rpt.source_freshness` and the reconciliation; propose an action (rerun the load, open a finance task) that needs approval before it runs

### 9.5 Fabric App: *Reconciliation Notes*

Today finance records the cause of each reconciliation difference by inserting into `fin.recon_note` with SQL. A Fabric App makes that a proper workflow.

- [ ] Show the open lines to investigate (read from `sm_finance` with DAX, reusing its measures)
- [ ] Let finance record cause, resolution and owner (written to `fin.recon_note` in `wh_gold`)
- [ ] Entra sign-in with the user's own identity, so RLS and SQL grants apply
- [ ] The next morning's load shows the note on the Reconciliation page; the line leaves "no note yet"

### 9.6 Copilot for Power BI

- [ ] Turn on Copilot for `rp_finance`: report summaries and narrative on the Overview page
- [ ] Prepare the model for Copilot (descriptions, synonyms, verified answers)

---

## 10. Documentation

- [ ] Screenshots for the README: Finance Pulse pages, the deployment pipelines in sync, the pipeline run, Excel
- [ ] ADR-010: the AI layer (data agent, ontology, Fabric App), with the capacity and security decisions
- [ ] Operator manual: a part for the AI items once they're built
