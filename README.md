# Harmonia Hall: a governed analytics platform on Microsoft Fabric

**One trusted set of numbers for a performing-arts organization: ticketing, fundraising, finance and venue operations brought together in Microsoft Fabric, checked every night, and delivered to the tools people already use, including Excel.**

Harmonia Hall is a fictional New York concert hall with the systems a real one runs on: **Tessitura** (ticketing and CRM), **MIP Fund Accounting** (the general ledger), **Diese** (hall bookings), plus spreadsheets and marketing exports. This repository builds, end to end, the platform such an organization needs to replace scattered reports and server-hosted cubes, and runs it in a real Fabric tenant from development to production.

![Platform architecture](docs/diagrams/01-platform-architecture.png)

## Why it matters

- **Finance can trust the numbers.** Every night, ticketing and gift revenue from Tessitura is reconciled to the general ledger by month, revenue stream and fund. Differences outside tolerance stay visible until finance records the cause. In the sample data, 278 of 300 lines tie out and the 22 planted exceptions are caught.
- **People keep working in Excel.** The certified finance model is used live from Excel PivotTables and `CUBEVALUE` formulas, the same experience as a cube, with security applied per user.
- **Everyone sees how fresh the data is.** Each report page and each Excel workbook can show, per source, when it was last loaded and the latest business date it holds, and whether that's within its daily or weekly service level.
- **Changes reach production safely.** DEV, TEST and PROD are separate. Releases go through deployment pipelines, and stage-specific settings come from variable libraries, so nothing is re-pointed by hand.
- **Access follows least privilege.** Entra groups only; builders and consumers are separated; security is enforced where each audience queries: the semantic model for Power BI and Excel, SQL rules for SQL users, OneLake security for data science.

## What's in it

| Area | What's built |
|---|---|
| Sources | Six systems through four ingestion patterns: Copy jobs from on-premises SQL Server through a gateway (Tessitura, MIP), one config-driven REST API notebook (Tessitura API, Diese), Dataflow Gen2 over SharePoint (education), an ADLS shortcut (marketing) |
| Bronze and Silver | Lakehouses: everything kept as received, reconciled to source manifests, then typed, deduplicated and checked by 43 data-quality rules written as YAML; failed rows quarantined; duplicate constituents merged into one patron |
| Gold | A T-SQL star schema in a Fabric Warehouse: conformed dimensions, SCD2 patrons, incremental facts, ledger and budget, cash flow, reconciliation, source freshness; deployed to every stage from the repo by one script that is safe to re-run |
| Finance product | `sm_finance` (Direct Lake, calculation group for time intelligence, DAX user-defined functions, RLS) and the `rp_finance` report: overview, statement of activities vs budget and last year, cash flow, reconciliation, detail pages; the report layout is generated from code |
| Platform as code | Entra groups, 6 domains, 15 workspaces, 5 deployment pipelines, Git integration, OneLake security and item shares, created and checked by idempotent scripts against the Fabric REST APIs |
| Release | Git integration on DEV, deployment pipelines DEV › TEST › PROD, variable libraries for stage values, CI on every push |

**Status:** the data platform and the Finance product run in DEV, TEST and PROD. The Audience, Education and Operations models are designed (model specs, DAX, roles) and read the same Gold. Open items and the AI roadmap (data agent, Fabric IQ ontology, Fabric Apps) are in [TODO.md](TODO.md).

## How it works

| Layer | Item | Guarantee |
|---|---|---|
| Ingestion | Copy jobs, API notebook, Dataflow, shortcut | Each source arrives through the tool that fits its owner and access ([ADR-003](docs/adr/ADR-003-ingestion-tools.md)) |
| Bronze | `lh_bronze` | Every version received; file loads reconciled to the source's row counts |
| Silver | `lh_silver` | Typed, one row per business key, quality-gated, identity-resolved |
| Gold | `wh_gold` | Star schema with declared grain, unknown members, business definitions, audit and freshness tables |
| Semantic | `sm_finance` (+ designed: audience, education, operations) | Certified measures, RLS, Direct Lake: no refresh to schedule |
| Consumption | Org apps, Excel, SQL endpoint | The only things business users touch |

One pipeline, `pl_daily_load`, runs it all daily, retries transient failures and posts to Teams on failure.

![CI/CD](docs/diagrams/03-cicd-flow.png)

## Engineering highlights

| Capability | Where |
|---|---|
| Tenant topology as config, applied through REST APIs (idempotent, long-running-operation aware, `--dry-run`) | [`config/tenant.yaml`](config/tenant.yaml), [`scripts/`](scripts), [`scripts/lib/fabric.py`](scripts/lib/fabric.py) |
| Source contracts and data-quality rules as YAML | [`config/sources.yaml`](config/sources.yaml), [`config/dq_rules.yaml`](config/dq_rules.yaml) |
| Bronze and Silver notebooks (manifest reconciliation, CDC dedupe, hash-based MERGE, quarantine, identity resolution) | [`fabric/de`](fabric/de) |
| Gold in T-SQL (SCD2, point-in-time lookups, incremental facts in transactions, revenue-to-ledger reconciliation, freshness) | [`src/warehouse`](src/warehouse) |
| Schema deployment to any stage, safe to re-run, handles the first load of a new stage | [`scripts/13_deploy_gold_sql.py`](scripts/13_deploy_gold_sql.py) |
| Stage values from variable libraries; Direct Lake rebind after deployment | [runbook 4.6](docs/01-runbook.md#46-variable-libraries-stage-specific-values), [`scripts/bi/rebind_direct_lake.py`](scripts/bi/rebind_direct_lake.py) |
| Report as code (PBIR generated to a layout standard) | [`scripts/bi/build_rp_finance.py`](scripts/bi/build_rp_finance.py) |
| Layered security: OneLake security, SQL grants, masking and RLS, model RLS | [ADR-006](docs/adr/ADR-006-security-model.md), [`rls_roles.md`](src/semantic_model/rls_roles.md) |
| Governance: ownership, certification criteria, DQ service levels, tenant-settings audit | [`docs/03-governance-standards.md`](docs/03-governance-standards.md) |
| Capacity sizing and cost (the F64 licensing threshold) | [`docs/04-capacity-sizing.md`](docs/04-capacity-sizing.md) |
| Synthetic data with planted defects, and its tests | [`data_generator`](data_generator), [`tests`](tests) |

## Get started

```powershell
az login --allow-no-subscriptions
uv sync --group dev
uv run python scripts/validate_config.py
uv run python scripts/00_create_security_groups.py --dry-run
```

Then follow the **[operator manual](docs/01-runbook.md)**: set up the tenant, connect the sources, build DEV, promote to TEST and PROD, and run it every day.

## Repository layout

```
config/            tenant.yaml (topology) · sources.yaml (ingestion contract) · dq_rules.yaml
scripts/           provisioning and checks against the Fabric, Graph and OneLake APIs · source DB loader · Gold deploy
scripts/bi/        finance report generator and theme · Direct Lake rebind notebook
data_generator/    synthetic data for all six sources (full history + daily changes, with planted defects)
src/ingestion/     build specs for the Copy jobs and the Dataflow
src/pipelines/     pl_daily_load build spec
src/warehouse/     wh_gold T-SQL, in deployment order
src/semantic_model model specs, DAX measures, security roles
fabric/            Fabric Git folders, one per DEV workspace (written by Fabric)
docs/              operator manual · architecture · governance · capacity sizing · ADRs · diagrams
tests/             data generator tests
```

## Architecture decisions

| ADR | Decision |
|---|---|
| [001](docs/adr/ADR-001-workspace-domain-topology.md) | Workspace families × environments, grouped by domain |
| [002](docs/adr/ADR-002-medallion-storage.md) | Lakehouse Bronze and Silver, **Warehouse Gold** |
| [003](docs/adr/ADR-003-ingestion-tools.md) | The ingestion tool follows the source |
| [004](docs/adr/ADR-004-semantic-model-mode.md) | **Direct Lake on OneLake** with a fixed identity |
| [005](docs/adr/ADR-005-cicd.md) | Git on DEV, deployment pipelines, variable libraries; fabric-cicd as the scale-up path |
| [006](docs/adr/ADR-006-security-model.md) | Layered security, enforced where each audience queries |
| [007](docs/adr/ADR-007-data-quality.md) | Declarative data-quality gate with quarantine |
| [008](docs/adr/ADR-008-capacity-cost.md) | Capacity sizing and cost controls |
| [009](docs/adr/ADR-009-domain-expansion-hub-and-spoke.md) | Hub and spoke: adding Finance and Operations without rebuilding |

---

*All data is synthetic and Harmonia Hall is fictional. The design mirrors the needs of a large performing-arts presenter: ticketing, subscriptions, fundraising, finance, venue operations and education programs.*
