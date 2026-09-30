# Build runbook: from an empty Fabric trial to a governed platform

Work through the phases in order. Each one ends with a ✅ **checkpoint**: what you should see, plus a screenshot to take for your portfolio (save them in `docs/screenshots/`).
Allow roughly 6–8 hours in total. Phases 1–7 set up the platform (about 2 hours); phases 8–13 build the data product; phases 14–16 cover promotion and operations.

> Run commands from the repo root in PowerShell. Every provisioning script accepts `--dry-run`, so **always dry-run first**: it's also good interview practice ("I preview every tenant change").

---

## Phase 0 — Prerequisites (15 min)

```powershell
uv --version                              # uv already installed? skip the next line
# winget install --id astral-sh.uv          # installs uv itself (only if the line above fails)
winget install --id Microsoft.AzureCLI    # optional: 'az login' for sign-in; scripts fall back to a browser pop-up
az login --allow-no-subscriptions         # sign in as your Fabric admin account
uv sync --group dev                       # creates .venv with dependencies
uv run python main.py                     # prints the build order
uv run python scripts/validate_config.py  # lint the tenant design
uv run pytest -q                          # generator unit tests
```

- Confirm the **Fabric trial** is active: Settings (gear) › **Admin portal** › Capacity settings › Trial.
- Confirm you're a **Fabric administrator**: the Admin portal opens and shows Tenant settings.

✅ `validate_config.py` prints `OK: 7 groups, 4 domains, 9 workspaces, 14 entities, 23 DQ rules`.

---

## Phase 1 — Identity: Entra security groups (step 00)

```powershell
uv run python scripts/00_create_security_groups.py --dry-run
uv run python scripts/00_create_security_groups.py --add-me-to fabric_admins
```

- This creates the seven `sg-hh-*` groups and writes `config/.generated/principals.json`.
- To **test RLS** later, create one or two test users in Entra (e.g. `audience.tester@…`) and add them to `sg-hh-analysts-audience`.

✅ Entra admin center › Groups shows `sg-hh-*`.

---

## Phase 2 — Tenant settings (Admin portal, 15 min)

These are set by a human on purpose, and audited by script in step 08. In **Admin portal › Tenant settings**:

| Setting group › setting | Value | Why |
|---|---|---|
| Microsoft Fabric › *Users can create Fabric items* | Enabled for specific groups: `sg-hh-fabric-admins`, `sg-hh-data-engineers`, `sg-hh-bi-developers` | Stops "shadow" items |
| Workspace settings › *Create workspaces* | Specific groups: `sg-hh-fabric-admins` | Topology stays as designed |
| Export and sharing › *Publish to web* | **Disabled** | Donor data leak vector |
| Export and sharing › *External data sharing* | Disabled | No cross-tenant sharing without review |
| Git integration › *Users can synchronize workspace items with their Git repositories* | Enabled | ADR-005 |
| Git integration › *Users can sync workspace items with GitHub repositories* | Enabled | We use GitHub |
| Developer settings › *Service principals can use Fabric APIs* | Enabled for a dedicated group (optional) | fabric-cicd scale-up path |
| Domain management › *Allow tenant and domain admins to override workspace assignments* | Enabled | Script 02 assigns workspaces |
| OneLake › *Users can access data stored in OneLake with apps external to Fabric* | Enabled | Script 06 uploads over the ADLS API |
| Information protection › *Allow users to apply sensitivity labels for content* | Enabled (if your tenant has Purview labels) | ADR-006 |

✅ Screenshot the Tenant settings page.

---

## Phase 3 — Domains (step 01)

```powershell
uv run python scripts/01_create_domains.py --dry-run
uv run python scripts/01_create_domains.py
```

✅ In **Admin portal › Domains** you see Harmonia Hall › Data Platform / Audience & Development / Education & Community. Screenshot it.

Domain admins appear on **Harmonia Hall** only; the subdomains inherit them. Domain roles don't give access to any workspace or data. Access comes from the workspace roles set in Phase 4.

Optional, in the UI, on the **parent domain** (subdomains have no image or admin settings of their own; they inherit from the parent): pick a cover image from the gallery, set a **default sensitivity label**, and delegate settings to domain admins.

---

## Phase 4 — Workspaces (step 02)

```powershell
uv run python scripts/02_create_workspaces.py --dry-run
uv run python scripts/02_create_workspaces.py
```

✅ There are nine workspaces (`hh-{dataplatform|audience|education}-{dev|test|prod}`), each on the trial capacity, assigned to its domain, with **group** roles only (Manage access). Screenshot the workspace list filtered by domain.

---

## Phase 5 — Core items (step 03)

```powershell
uv run python scripts/03_create_items.py
```

✅ Each `hh-dataplatform-*` workspace has `lh_bronze`, `lh_silver` (with the *schemas* feature on) and `wh_gold`.

> Why before deployment pipelines? When a workspace is assigned to a stage, items with the **same name and type are paired**. That way the Test and Prod lakehouses become the deployment targets, instead of duplicates being created.

---

## Phase 6 — Deployment pipelines (step 04)

```powershell
uv run python scripts/04_create_deployment_pipelines.py
```

✅ There are three pipelines (`dp-hh-dataplatform`, `dp-hh-audience`, `dp-hh-education`), each Development › Test › Production with its workspaces assigned. Screenshot one.

---

## Phase 7 — Git integration (step 05)

1. **Push this repo** to GitHub: `musatouray/performing-arts-audience-development-platform`.
2. Create a **fine-grained PAT** in GitHub › Settings › Developer settings. Scope it to this repo only, with *Contents: Read and write*.
3. In Fabric, go to Settings › **Manage connections and gateways** › New › *GitHub – Source control*. Paste the PAT and name the connection `github-hh-platform`. Copy its **Connection ID** into `config/tenant.yaml › git.connection_id`.
4. Run the script:

   ```powershell
   uv run python scripts/05_connect_git.py --dry-run
   uv run python scripts/05_connect_git.py
   ```

✅ Each DEV workspace shows Source control connected to `main`, in folders `fabric/de`, `fabric/bi-audience` and `fabric/bi-education`. Commits appear in GitHub.

---

## Phase 8 — Land the data (step 06)

```powershell
uv run python -m data_generator.generate full --start 2023-07-01 --end 2026-09-27
uv run python scripts/06_upload_landing_files.py --env dev
```

The load is about 560k rows across 14 entities and 3 source systems. It includes **deliberate defects**: duplicate patrons, bad emails and zip codes, orphan and negative order lines, re-sent rows, and future-dated gifts.

✅ `lh_bronze › Files › landing` holds `ticketing/`, `fundraising/`, `education/` and `_manifests/`, and `Files/config` holds `sources.json` and `dq_rules.json`.

---

## Phase 9 — Notebooks: Bronze and Silver (DEV)

```powershell
uv run python scripts/build_notebooks.py        # -> src/notebooks/ipynb/*.ipynb
```

1. In `hh-dataplatform-dev`, use **Import › Notebook › From this computer** and select all four `.ipynb` files.
2. Open each notebook and attach lakehouses:
   - `nb_10_bronze_ingest`: **lh_bronze** (default) + lh_silver
   - `nb_20_silver_transform`: **lh_silver** (default) + lh_bronze
   - `nb_00_common` and `nb_90_maintenance`: **lh_silver** (default) + lh_bronze
3. Run `nb_10_bronze_ingest`, then `nb_20_silver_transform`.

✅ You should see:

- Bronze has tables under schemas `ticketing`, `fundraising` and `education`.
- `audit.reconciliation` shows all rows **OK**.
- Silver has typed tables, `dq.dq_results`, `dq.quarantine` (a few hundred rows), `core.patron_xref` and `core.patron`.
- The run log message reads "N source records → M patrons (x% de-duplicated)". **Screenshot the DQ results and the identity-resolution message**; they're strong interview material.

> If `CREATE SCHEMA` with a lakehouse prefix errors on your runtime, create the schemas once in the Lakehouse explorer (**New schema**) and re-run.

---

## Phase 10 — Gold warehouse (DEV)

Open `wh_gold` › **New SQL query** (or connect SSMS or VS Code to the SQL connection string). Run the files **in order**:

| File | What it does |
|---|---|
| `00_schemas_and_etl_framework.sql` | Schemas, load log, watermarks |
| `10_dimensions_ddl.sql` | Dimension tables |
| `20_facts_ddl.sql` | Fact tables |
| `30_load_dimensions.sql` | Date, reference and SCD2 patron procedures |
| `40_load_facts.sql` | Incremental facts + `etl.usp_load_gold` |
| `50_reporting_views.sql` | Sell-through, LYBUNT, renewal, education, DQ and ops views |
| `60_security.sql` | **Edit the UPNs first.** GRANT, DDM, RLS |

Then run:

```sql
EXEC etl.usp_load_gold @run_id = 'manual-001';
SELECT * FROM rpt.vw_donor_retention ORDER BY fiscal_year;
SELECT TOP 20 * FROM rpt.vw_performance_sell_through ORDER BY sell_through_pct DESC;
SELECT * FROM rpt.vw_gold_integrity;
```

✅ You should see a load log with row counts, a donor retention rate per FY, and sell-through per show. Screenshot the query results.

---

## Phase 11 — Orchestration pipeline

Build `pl_daily_load` and `pl_weekly_maintenance` in `hh-dataplatform-dev` exactly as specified in [`src/pipelines/pl_daily_load.md`](../src/pipelines/pl_daily_load.md), then run it.

✅ The Monitoring hub shows a green run. `rpt.vw_pipeline_health` shows the Bronze, Silver and Gold steps under one `run_id`. Screenshot the pipeline canvas.

---

## Phase 12 — OneLake security (step 07)

1. Open `lh_silver` › **Manage OneLake security** › enable it (one-time).
2. Run the script:

   ```powershell
   uv run python scripts/07_apply_onelake_security.py --env dev --dry-run
   uv run python scripts/07_apply_onelake_security.py --env dev
   ```

✅ The roles AudienceReaders, DevelopmentReaders and EducationReaders are visible. DevelopmentReaders can't see `email`, `phone` or `address_line1` on `core.patron`. Screenshot the role editor.

---

## Phase 13 — Semantic models and reports (BI DEV workspaces)

Follow [`src/semantic_model/model.md`](../src/semantic_model/model.md).

0. **Give BI developers Gold, and only Gold.** They have no role in the Data Platform workspaces, so share the `wh_gold` *item* with them. Warehouse sharing is UI-only (no public API):
   `hh-dataplatform-dev` › `wh_gold` › **…** › **Share** › add `sg-hh-bi-developers`, then tick **Read all data using SQL (ReadData)** and **Read all OneLake data (ReadAll)**, untick email notification, and select **Grant**. ReadAll is what Direct Lake *on OneLake* needs; ReadData lets them check numbers in SQL. Then verify:

   ```powershell
   uv run python scripts/09_verify_item_shares.py --env dev
   ```

   ✅ `OK sg-hh-bi-developers: ['read', 'readall', 'readdata']`. Propagation can take up to two hours. Report viewers get no share, because models use a fixed-identity connection.
1. In `hh-audience-dev`: **New item › Semantic model (Direct Lake)**, choose the OneLake catalog, then `hh-dataplatform-dev › wh_gold`, and select the tables listed in the spec.
2. Build the relationships from the spec, mark `dim_date` as the date table, and add the measures from `measures.dax` plus the *Time Intelligence* calculation group.
3. **Security:** create the roles from `rls_roles.md`, map them to groups, and use **Test as role** to check them.
4. **Connection:** Settings › *Gateway and cloud connections*: bind to a **shareable cloud connection** with a fixed identity (your admin account, or a service principal).
5. Build the report pages from the spec.
6. **Endorse** the model as *Promoted* now, and *Certified* after review. Apply the sensitivity label **Confidential**.
7. Repeat a lighter version for `sm_education_impact` in `hh-education-dev`.
8. **Commit** both BI workspaces to Git (Source control › Commit).

✅ Screenshot the model diagram view, the RLS test as the Audience role (donor visuals empty), and the report.

---

## Phase 14 — Promote DEV › TEST › PROD

1. In `dp-hh-dataplatform`, **Deploy** Development › Test.
   - Deployment rules: for notebooks, set the *Default lakehouse* rule to the Test stage's `lh_bronze`/`lh_silver`. Same-workspace names usually auto-bind, but verify.
2. Upload data to TEST: `uv run python scripts/06_upload_landing_files.py --env test`. In TEST, run the SQL files, then the pipeline. **Share TEST `wh_gold` with `sg-hh-bi-developers`** as in Phase 13, step 0, and run `09_verify_item_shares.py --env test`. Do the same for PROD before promoting the BI models.
3. In `dp-hh-audience`, **Deploy** Development › Test. **Rebind the model** to TEST's `wh_gold`. Use a deployment rule if the UI offers the data source; otherwise run this in a notebook:

   ```python
   %pip install semantic-link-labs
   import sempy_labs.directlake as dl
   dl.update_direct_lake_model_connection(dataset="sm_audience_development", workspace="hh-audience-test",
                                          source="wh_gold", source_type="Warehouse",
                                          source_workspace="hh-dataplatform-test")
   ```

   The rebind API changes between library versions, so check the current `semantic-link-labs` docs for the exact signature. Being able to explain this gotcha is itself a senior signal.
4. Repeat Test › Production. In PROD BI workspaces, **create the Org App** (audience = the relevant groups).

✅ Screenshot a deployment pipeline showing all three stages in sync.

---

## Phase 15 — Run a "next day" (incremental + SCD2)

```powershell
uv run python -m data_generator.generate incremental --days 3
uv run python scripts/06_upload_landing_files.py --env dev
```

Run `pl_daily_load`, then check:

```sql
SELECT TOP 20 procedure_name, rows_inserted, rows_deleted, message FROM etl.load_log ORDER BY started_at DESC;
SELECT patron_id, city, valid_from, valid_to, is_current FROM dim.patron
WHERE patron_id IN (SELECT patron_id FROM dim.patron GROUP BY patron_id HAVING COUNT(*) > 1) ORDER BY patron_id, valid_from;
```

✅ You should see small incremental row counts, watermarks advancing, and **SCD2 history** for patrons who moved. Screenshot the SCD2 query.

---

## Phase 16 — Operate and govern

- **Tenant settings audit:** run `uv run python scripts/08_audit_tenant_settings.py` and commit `docs/tenant-settings-audit.md`.
- **Capacity Metrics app:** install it from AppSource and note CU for the pipeline run.
- **Activator:** add a rule on `dq.dq_results` (severity = error, failed_rows > 0) that sends an email or Teams message.
- **OneLake catalog › Govern tab:** screenshot it (ownership, labels, endorsement coverage).
- **Purview:** apply sensitivity labels if your tenant has them.

## Teardown

Run `uv run python scripts/99_teardown.py` to preview, then add `--confirm` to delete.
