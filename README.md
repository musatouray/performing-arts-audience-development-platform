# Performing Arts Audience & Development Platform, on Microsoft Fabric

An end-to-end, **governed** Microsoft Fabric platform for a (fictional) NYC performing-arts nonprofit, *Harmonia Hall*. It covers ticketing, subscriptions, fundraising and music-education data.
The whole tenant design (Entra groups, domains, nine workspaces, deployment pipelines, Git, OneLake security) is **config-as-code, applied through the Fabric REST APIs**. The data product runs a medallion flow from three source systems to certified Direct Lake semantic models.

![Platform architecture](docs/diagrams/01-platform-architecture.png)

## What it demonstrates

| Capability | Where |
|---|---|
| Microsoft **deployment Pattern 2** (multiple workspaces, single capacity: hub and spoke + domains), with a documented path to Pattern 3 | [architecture §9](docs/02-architecture.md#9-microsoft-fabric-deployment-pattern) |
| Tenant topology as code: domains, workspaces × environments, group roles, capacity | [`config/tenant.yaml`](config/tenant.yaml), [`scripts/00–04`](scripts) |
| Fabric REST API automation: idempotent, LRO-aware, throttle-aware, `--dry-run` | [`scripts/lib/fabric.py`](scripts/lib/fabric.py) |
| Git integration (GitHub) and deployment pipelines Dev › Test › Prod | [`scripts/04`, `05`](scripts), [ADR-005](docs/adr/ADR-005-cicd.md) |
| Metadata-driven ingestion with source-to-Bronze reconciliation | [`config/sources.yaml`](config/sources.yaml), [`nb_10_bronze_ingest`](src/notebooks/nb_10_bronze_ingest.py) |
| Declarative DQ with quarantine, CDC dedupe, hash-based MERGE | [`config/dq_rules.yaml`](config/dq_rules.yaml), [`nb_20_silver_transform`](src/notebooks/nb_20_silver_transform.py) |
| Identity resolution: ticket buyers and donors in one golden patron | `nb_20_silver_transform` → `core.patron` |
| T-SQL star schema: SCD2, point-in-time lookups, incremental facts, transactions | [`src/warehouse`](src/warehouse) |
| Nonprofit KPIs: sell-through, LYBUNT/SYBUNT, donor retention, subscriber renewal, education reach | [`50_reporting_views.sql`](src/warehouse/50_reporting_views.sql), [`measures.dax`](src/semantic_model/measures.dax) |
| Layered security: OneLake security, SQL GRANT/DDM/RLS, model RLS/OLS incl. dynamic RLS | [ADR-006](docs/adr/ADR-006-security-model.md), [`rls_roles.md`](src/semantic_model/rls_roles.md) |
| Direct Lake on OneLake with fixed identity, calculation groups | [`model.md`](src/semantic_model/model.md) |
| Governance standards: RACI, certification criteria, DQ SLA, tenant-settings audit | [`docs/03-governance-standards.md`](docs/03-governance-standards.md), [`scripts/08`](scripts/08_audit_tenant_settings.py) |
| CI: lint, config validation, tests, notebook build; fabric-cicd scale-up path | [`.github/workflows`](.github/workflows) |

## Tenant topology

![Tenant topology](docs/diagrams/02-tenant-topology.png)

## Quick start

```powershell
az login --allow-no-subscriptions
uv sync --group dev
uv run python main.py                                   # build order
uv run python scripts/validate_config.py                # lint the design
uv run python scripts/00_create_security_groups.py --dry-run
```

Then follow the **[build runbook](docs/01-runbook.md)** (16 phases, each with a checkpoint).

## Repository layout

```
config/            tenant.yaml (topology) · sources.yaml (ingestion contract) · dq_rules.yaml
scripts/           00-08 provisioning via Fabric/Graph/OneLake APIs · validate_config · build_notebooks · teardown
data_generator/    stdlib-only synthetic source systems (full + incremental CDC, with injected defects)
src/notebooks/     Bronze, Silver, maintenance notebooks (.py source → ipynb/ for import)
src/warehouse/     wh_gold T-SQL: schemas, dims, facts, SCD2 procs, rpt views, security
src/semantic_model model spec, DAX measures, RLS/OLS roles
src/pipelines/     pl_daily_load / pl_weekly_maintenance build spec
fabric/            Git-integration folders (written by Fabric, one per DEV workspace)
docs/              runbook · architecture · governance standards · demo script · capacity sizing · ADRs · diagrams
tests/             generator unit tests
```

## Architecture decisions

| ADR | Decision |
|---|---|
| [001](docs/adr/ADR-001-medallion-storage.md) | Lakehouse Bronze/Silver, **Warehouse Gold** |
| [002](docs/adr/ADR-002-ingestion-tools.md) | Ingestion tool follows the source |
| [003](docs/adr/ADR-003-semantic-model-mode.md) | **Direct Lake on OneLake** + fixed identity |
| [004](docs/adr/ADR-004-workspace-domain-topology.md) | 3 workspace families × 3 environments, grouped by domain |
| [005](docs/adr/ADR-005-cicd.md) | Git on DEV + deployment pipelines; fabric-cicd scale-up |
| [006](docs/adr/ADR-006-security-model.md) | Layered security, enforced where each audience queries |
| [007](docs/adr/ADR-007-data-quality.md) | Declarative DQ gate with quarantine |
| [008](docs/adr/ADR-008-capacity-cost.md) | Capacity sizing and cost controls (details: [capacity sizing reference](docs/05-capacity-sizing.md)) |

---

*All data is synthetic. Harmonia Hall is fictional; the design mirrors the typical needs of a large performing-arts presenter (ticketing, subscriptions, fundraising, education programs).*
