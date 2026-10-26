# Operator manual

How to build the platform from an empty Fabric tenant, run it every day, change it safely and promote it from DEV to TEST to PROD.

**How to read this manual**

- Work through Parts 1 to 5 in order the first time. After that, Parts 6 to 8 are the day-to-day reference.
- Every step ends with ✅ **Check**: what you should see before you move on.
- Run commands from the repo root in PowerShell. Every provisioning script accepts `--dry-run`: **preview first, then apply.**
- Anything that identifies your tenant (IDs, server names, URLs) goes in `.env`, never in a committed file. Passwords live only in Fabric connections or a password manager.

| Part | What you do | Time |
|---|---|---|
| [1. Before you start](#1-before-you-start) | Tools, accounts, tenant settings | 30 min |
| [2. Set up the tenant](#2-set-up-the-tenant) | Groups, domains, workspaces, items, deployment pipelines, Git | 1 h |
| [3. Connect the sources](#3-connect-the-sources) | Six source systems, four ingestion patterns | 3 h |
| [4. Build DEV](#4-build-dev) | Bronze, Silver, Gold, pipeline, security, models, report, variable libraries | 3 h |
| [5. Promote to TEST and PROD](#5-promote-to-test-and-prod) | Deployment pipelines, first load in a new stage, apps | 1 h per stage |
| [6. Run it every day](#6-run-it-every-day) | Schedules, health checks, a "next day" of data | — |
| [7. Change something](#7-change-something) | Git workflow, report, Gold SQL, models | — |
| [8. Troubleshooting](#8-troubleshooting) | Errors seen in practice and their fixes | — |
| [9. Govern and tear down](#9-govern-and-tear-down) | Audits, monitoring, removing everything | — |

---

## 1. Before you start

### 1.1 What you need

| Need | Detail |
|---|---|
| Fabric capacity | A trial or F-SKU. Below F64, every report or Excel viewer needs a Power BI Pro licence. |
| Your account | Fabric administrator (Admin portal opens and shows Tenant settings), with MFA. |
| Azure | A subscription for the marketing storage account; *Storage Blob Data Contributor* on it to upload. |
| On your computer | SQL Server (Developer or Express), the on-premises data gateway, ODBC Driver 18, Git, `uv`, Azure CLI (optional). |
| GitHub | This repo, plus two small public repos for the mock APIs. |
| Microsoft 365 | A SharePoint site for the education workbooks. |

### 1.2 Install and validate

```powershell
uv --version                              # install uv first if this fails: winget install --id astral-sh.uv
az login --allow-no-subscriptions         # sign in as your Fabric admin; scripts fall back to a browser window
uv sync --group dev                       # creates .venv with the dependencies
Copy-Item .env.example .env               # then fill in your values as you go
uv run python scripts/validate_config.py  # lints the tenant design
uv run pytest -q                          # data generator tests
```

✅ **Check:** `validate_config.py` prints `OK: 13 groups, 6 domains, 15 workspaces, 24 entities, 43 DQ rules`. WARN lines about empty `.env` values are expected until Part 3.

### 1.3 Tenant settings (Admin portal › Tenant settings)

Set by a person on purpose, and audited by script later (Part 9).

| Setting | Value | Why |
|---|---|---|
| *Users can create Fabric items* | Specific groups: `sg-hh-fabric-admins`, `sg-hh-data-engineers`, `sg-hh-bi-developers` | No "shadow" items |
| *Create workspaces* | `sg-hh-fabric-admins` | The topology stays as designed |
| *Publish to web* | Disabled | Donor data must never be public |
| *External data sharing* | Disabled | No cross-tenant sharing without review |
| *Users can synchronize workspace items with their Git repositories* / *with GitHub* | Enabled | Git integration |
| *Service principals can use Fabric APIs* | Enabled for a dedicated group (optional) | fabric-cicd later |
| *Allow tenant and domain admins to override workspace assignments* | Enabled | Script 02 assigns domains |
| *Users can access data stored in OneLake with apps external to Fabric* | Enabled | Script 06 uploads config files |
| *Users can work with semantic models in Excel using a live connection* | Enabled for the analyst groups | Excel is a main way to use the models |
| *Allow users to apply sensitivity labels for content* | Enabled, if your tenant has Purview labels | Models are labelled Confidential |

---

## 2. Set up the tenant

### 2.1 Security groups and service accounts

```powershell
uv run python scripts/00_create_security_groups.py --dry-run
uv run python scripts/00_create_security_groups.py --add-me-to fabric_admins
```

This creates the `sg-hh-*` groups and writes `config/.generated/principals.json`.

Create two **service accounts** by hand in Entra (only an admin should hold their passwords):

| Account | Put it in | Used for |
|---|---|---|
| `svc-fabric-dataflows-nonprod@<tenant>` | `sg-hh-svc-dataflows-nonprod` | Owns the Dataflow in DEV and TEST |
| `svc-fabric-dataflows-prod@<tenant>` | `sg-hh-svc-dataflows-prod` | Owns the Dataflow in PROD; password held by the platform owner only |

Each account goes only into its own service group, never a human group. Give each a Fabric licence, no mailbox, a long random password in a password manager, and keep MFA on. For testing security later, create one or two test users and add them to an analyst group.

✅ **Check:** Entra › Groups lists the `sg-hh-*` groups.

### 2.2 Domains, workspaces, core items, deployment pipelines

```powershell
uv run python scripts/01_create_domains.py --dry-run;               uv run python scripts/01_create_domains.py
uv run python scripts/02_create_workspaces.py --dry-run;            uv run python scripts/02_create_workspaces.py
uv run python scripts/03_create_items.py
uv run python scripts/04_create_deployment_pipelines.py
```

Run 03 before 04: when a workspace is assigned to a pipeline stage, items with the same name and type are **paired**, so TEST and PROD's lakehouses become deployment targets instead of duplicates.

✅ **Check:**
- Admin portal › Domains: Harmonia Hall › Data Platform, Audience & Development, Education & Community, Finance, Operations.
- 15 workspaces `hh-{dataplatform|audience|education|finance|operations}-{dev|test|prod}`, each on your capacity, in its domain, with **group** roles only. Each description says who it serves.
- Each `hh-dataplatform-*` has `lh_bronze`, `lh_silver` (schemas on) and `wh_gold`.
- Five deployment pipelines `dp-hh-*`, each Development › Test › Production with workspaces assigned.

### 2.3 Git integration

1. Push this repo to GitHub.
2. Create a **fine-grained PAT** for this repo only, with *Contents: Read and write*.
3. Fabric › Settings › Manage connections and gateways › New › *GitHub – Source control*, name it `github-hh-platform`. Put its connection ID in `.env` as `FABRIC_GIT_CONNECTION_ID`.
4. Connect the DEV workspaces:

   ```powershell
   uv run python scripts/05_connect_git.py --dry-run
   uv run python scripts/05_connect_git.py
   ```

✅ **Check:** each DEV workspace shows Source control connected to `main`, in `fabric/de` and `fabric/bi-*`.

---

## 3. Connect the sources

Each source reaches Fabric the way it would in real life ([ADR-003](adr/ADR-003-ingestion-tools.md), build specs in [`src/ingestion`](../src/ingestion/README.md)):

| Source | Lives in | Fabric reads it with |
|---|---|---|
| Tessitura database (ticketing, CRM) | SQL Server on your computer, through the gateway | Copy job `cj_tessitura` |
| MIP Fund Accounting (ledger, budget) | A second SQL Server database, same gateway | Copy job `cj_mip` |
| Tessitura REST API (fundraising) | GitHub Pages (mock API) | Notebook `nb_05_api_ingest` |
| Diese (hall bookings) | A second GitHub Pages site | The same notebook |
| Education workbooks | SharePoint | Dataflow Gen2 `df_education_sharepoint` |
| Marketing exports | ADLS Gen2 | OneLake shortcut |

### 3.1 Generate the data

```powershell
uv run python -m data_generator.generate full --start 2023-07-01 --end 2026-10-10
```

This writes six folders under `data/` (about 700k rows) with **deliberate defects** for the quality checks to find: duplicate patrons, bad emails, orphan and negative order lines, future-dated gifts, duplicated clicks, overlapping API pages, negative ad spend, and 22 planted revenue-to-ledger differences.

### 3.2 Tessitura and MIP databases (gateway + Copy jobs)

1. Check the ODBC driver: `Get-OdbcDriver -Name "ODBC Driver 18*"`.
2. In `.env`: `TESSITURA_SQL_SERVER`, `TESSITURA_SQL_DATABASE=HarmoniaTessitura`, `MIP_SQL_SERVER`, `MIP_SQL_DATABASE=HarmoniaMIP`, `*_SQL_AUTH=windows`, `*_SQL_TRUST_SERVER_CERT=yes` (local self-signed certificate only).
3. Load both databases (the script creates them the first time):

   ```powershell
   uv run python scripts/11_load_source_db.py --source tessitura_db
   uv run python scripts/11_load_source_db.py --source mip_db
   ```

4. Give Fabric a **read-only login per system** (switch SQL Server to mixed authentication first and restart it):

   ```sql
   CREATE LOGIN svc_fabric_reader WITH PASSWORD = '<strong password>', CHECK_POLICY = ON;
   USE HarmoniaTessitura;  CREATE USER svc_fabric_reader FOR LOGIN svc_fabric_reader;  GRANT SELECT ON SCHEMA::tix TO svc_fabric_reader;
   ```

   Do the same for MIP with its own login (finance owns that access).
5. Keep the gateway updated; it only works while your computer is on.
6. Create one **on-premises SQL Server connection** per database (Basic authentication with the read-only login).
7. Build the Copy jobs from [`copy_job_tessitura.md`](../src/ingestion/copy_job_tessitura.md) and [`copy_job_mip.md`](../src/ingestion/copy_job_mip.md).

✅ **Check:** after a run, `lh_bronze` › Tables › `tessitura` has seven tables and `mip` has five; every journal balances.

### 3.3 Mock APIs (Tessitura and Diese)

1. Create public repos `harmonia-hall-api` and `harmonia-hall-diese-api`, and copy the data in:

   ```powershell
   cd C:\dev
   robocopy .\performing-arts-audience-development-platform\data\tessitura_api .\harmonia-hall-api /MIR /XD .git /NJH /NP
   robocopy .\performing-arts-audience-development-platform\data\diese_api .\harmonia-hall-diese-api /MIR /XD .git /NJH /NP
   # in each repo: git add -A; git commit -m "API data"; git push
   ```

2. In each repo: Settings › Pages › deploy from `main`, `/ (root)`.
3. Set `TESSITURA_API_BASE_URL` and `DIESE_API_BASE_URL` (ending in `/v1`) in `.env`.

✅ **Check:** `…/v1/index.json` opens in a browser for both.

### 3.4 Education (SharePoint + Dataflow Gen2)

1. Upload `data/education_sharepoint/` to the site as described in [`dataflow_education.md`](../src/ingestion/dataflow_education.md), and build `df_education_sharepoint` from it.
2. Give `sg-hh-svc-dataflows-nonprod` and `-prod` **Read** on the SharePoint site.
3. Make the service account a **user** of the SharePoint and Lakehouse connections, sign in as it, and **Take over** the Dataflow. A Dataflow always runs as its owner, so ownership is part of the setup (and of every deployment).
4. Create the connections **per tier**, each signed in as that tier's service account: `harmonia-hall-education-sharepoint-nonprod` and `harmonia-hall-lakehouse-nonprod` (as `svc-fabric-dataflows-nonprod`), and the same two with `-prod` (as `svc-fabric-dataflows-prod`). A connection writes with the identity stored in it, and the non-prod account has no access to PROD.

✅ **Check:** `lh_bronze` has `programs`, `schools` and `enrollments`.

### 3.5 Marketing (ADLS Gen2 + shortcut)

1. Create a storage account with **hierarchical namespace** and one container, `marketing-exports`. Upload the *contents* of `data/marketing_adls/`:

   ```powershell
   az storage blob upload-batch --account-name <account> -d marketing-exports -s data/marketing_adls --auth-mode login
   ```

2. In each `hh-dataplatform-*` workspace: Workspace settings › **Workspace identity** › create.
3. On the **container**, grant **Storage Blob Data Reader** to each workspace identity (IAM › Add role assignment › Managed identity). Each stage has its own identity, so each needs its own role.
4. Create a connection: Cloud › *Azure Data Lake Storage Gen2*, URL `https://<account>.dfs.core.windows.net`, authentication **Workspace identity**. Put the URL and connection ID in `.env` (`MARKETING_ADLS_ACCOUNT_URL`, `MARKETING_ADLS_CONNECTION_ID`).
5. Upload the config and create the shortcut:

   ```powershell
   uv run python scripts/06_upload_config.py --env dev
   uv run python scripts/10_create_shortcuts.py --env dev --dry-run
   uv run python scripts/10_create_shortcuts.py --env dev
   ```

✅ **Check:** `lh_bronze` › Files › landing › `marketing` (shortcut icon) lists `email_campaigns`, `email_clicks`, `ad_spend_daily` and `_manifests`.

Run `06_upload_config.py` again whenever `.env`, `sources.yaml` or `dq_rules.yaml` changes. Both scripts are safe to run again.

---

## 4. Build DEV

### 4.1 Bronze and Silver notebooks

1. In `hh-dataplatform-dev` › Source control › **Update all**. The notebooks, Copy jobs, Dataflow and pipeline come from [`fabric/de`](../fabric/de).
2. Run `nb_05_api_ingest`, `nb_10_bronze_ingest`, then `nb_20_silver_transform` (or wait for the pipeline in 4.3).

✅ **Check:**
- Bronze has schemas `tessitura`, `mip`, `diese`, `marketing` and the education tables.
- `audit.reconciliation` is **OK** for every file source.
- Silver has typed tables, `dq.dq_results`, `dq.quarantine` (several hundred rows) and `core.patron` (duplicate constituents merged).

### 4.2 Gold warehouse

Deploy the schema from the repo. Every file is safe to run again.

```powershell
uv run python scripts/13_deploy_gold_sql.py --env dev --dry-run
uv run python scripts/13_deploy_gold_sql.py --env dev
```

| File | Creates |
|---|---|
| `00` | Schemas, load log, watermarks |
| `10`, `20` | Dimension and fact tables |
| `30`, `40` | Load procedures, including the orchestrator `etl.usp_load_gold` |
| `50` | Reporting views (sell-through, donor retention, DQ, pipeline health) |
| `60` + `61_security_users.local.sql` | SQL security: grants, masking, row-level security. Copy `61_…example.sql` to `.local.sql` (ignored by Git) and put in real sign-in names first. |
| `70`, `72` | Finance and operations: ledger, budget, cash flow, revenue-to-ledger reconciliation |
| `75`, `80` | Marketing; source freshness |

✅ **Check:** the script ends with `Done.` In a brand-new warehouse it may instead set aside three views that read Silver tables and exit with code 2: run the pipeline once, then run the script again (see [5.3](#53-first-load-in-a-new-stage)).

### 4.3 Daily pipeline

`pl_daily_load` ([spec](../src/pipelines/pl_daily_load.md)) runs the Copy jobs and the Dataflow side by side, then Bronze, Silver and Gold, retries transient failures and posts to Teams on failure. Run it with `load_date` blank.

✅ **Check** in `wh_gold`:

```sql
SELECT procedure_name, rows_inserted, status, message FROM etl.load_log
WHERE run_id = (SELECT TOP 1 run_id FROM etl.load_log ORDER BY started_at DESC) ORDER BY started_at;
SELECT * FROM rpt.vw_finance_integrity;                       -- 0 unbalanced journals
SELECT [status], COUNT(*) FROM fin.recon_revenue_to_gl GROUP BY [status];   -- 22 to investigate
SELECT * FROM rpt.vw_source_freshness;                        -- every source Fresh
```

### 4.4 Access

1. **OneLake security on Silver:** `lh_silver` › Manage OneLake security › enable, then:

   ```powershell
   uv run python scripts/07_apply_onelake_security.py --env dev
   ```

2. **Share `wh_gold`** (… › Share; the API can't do this):
   - `sg-hh-bi-developers`: Read, **ReadData**, **ReadAll** (Direct Lake needs ReadAll).
   - Analyst groups: **not in DEV**. They get Read in PROD (and TEST for sign-off) only.
3. Verify: `uv run python scripts/09_verify_item_shares.py --env dev`.

✅ **Check:** one OneLake role, *DataScienceReaders*; the share check prints `OK` for each group.

### 4.5 Semantic model and report (Finance)

1. `sm_finance` lives in `hh-finance-dev` (Direct Lake on OneLake, reading `wh_gold`). Definitions: [`model.md`](../src/semantic_model/model.md), [`finance_measures.dax`](../src/semantic_model/finance_measures.dax), roles in [`rls_roles.md`](../src/semantic_model/rls_roles.md).
2. Bind it to a **fixed-identity cloud connection** (Settings › Gateway and cloud connections).
3. The report `rp_finance` is generated from code. To change it, edit the script and regenerate (see [7.2](#72-change-the-finance-report)).
4. Endorse the model as *Promoted*; label it *Confidential*.

✅ **Check:** the report opens on Overview with FY2026: revenue $39.6M against a $35.8M budget, cash $13.9M, 150 days cash on hand.

### 4.6 Variable libraries (stage-specific values)

A deployment copies definitions as they are, so anything that names a specific item by ID would still point at DEV. References inside the same workspace rebind on their own. These don't, so they read a **variable library** (all variables of type String):

| Consumer | Reads | From |
|---|---|---|
| `pl_daily_load` › `sp_load_gold` | connection, workspace, warehouse ID, SQL endpoint | `vl_platform` (`wh_gold_connection`, `workspace_id`, `wh_gold_id`, `wh_gold_endpoint`) |
| Notebooks (first cell, `%%configure`) | default lakehouse | `vl_platform` (`lh_bronze_id` or `lh_silver_id`, `workspace_id`) |
| `df_education_sharepoint` (`DefaultDestination`) | destination lakehouse | `vl_platform` (`workspace_id`, `lh_bronze_id`) |
| `sm_finance` | which Gold it reads | `vl_finance` (`gold_workspace_id`, `gold_warehouse_id`), applied by `nb_rebind_sm_finance` |

Copy jobs need nothing: their destination is a same-workspace reference.

1. **`vl_platform`** in `hh-dataplatform-dev`: the default value set holds DEV's IDs; add value sets **TEST** and **PROD**. The warehouse connection IDs come from two Warehouse connections, `harmonia-hall-warehouse-nonprod` (DEV, TEST) and `harmonia-hall-warehouse-prod`.
2. **`vl_finance`** in `hh-finance-dev`, same pattern.
3. **`nb_rebind_sm_finance`** in `hh-finance-dev`, from [`scripts/bi/rebind_direct_lake.py`](../scripts/bi/rebind_direct_lake.py): the `%pip install` cell first, then the parameters cell, then the code.
4. Run `pl_daily_load` and the rebind notebook in DEV (it should report no change), then **Commit** both workspaces.

✅ **Check:** the DEV run is green, and the notebook prints the same address on its `was:` and `now:` lines.

---

## 5. Promote to TEST and PROD

A deployment copies **definitions, not data**. Each stage loads its own data from its own run. Do TEST completely, then repeat for PROD.

### 5.1 Prepare the stage (from your computer)

Use `--env test`, then later `--env prod`:

```powershell
uv run python scripts/13_deploy_gold_sql.py --env test
uv run python scripts/06_upload_config.py --env test
uv run python scripts/10_create_shortcuts.py --env test       # needs the stage's storage role (3.5)
uv run python scripts/07_apply_onelake_security.py --env test
```

### 5.2 Deploy the data platform

1. `dp-hh-dataplatform` › select the target stage › deploy from the previous stage.
2. Select `vl_platform`, the five notebooks, `cj_tessitura`, `cj_mip`, `df_education_sharepoint` and `pl_daily_load`.
3. **Leave out** `wh_gold` (its schema comes from the repo), `lh_bronze`, `lh_silver` and any `Staging…` items.
4. In the target workspace:
   - `vl_platform` › set the stage's value set (**TEST** or **PROD**) as **active**. Until you do, the stage still points at DEV.
   - `df_education_sharepoint` › **Take over** as the stage's service account (`-nonprod` for TEST, `-prod` for PROD) and check its connections.
   - Share `wh_gold`: BI developers (Read, ReadData, ReadAll); analyst groups Read (PROD; TEST only if sign-off needs SQL). Then run `09_verify_item_shares.py --env <stage>`.

### 5.3 First load in a new stage

Three views read Silver tables that only exist after the first run, so a new stage takes two passes:

1. Run `pl_daily_load`. Bronze and Silver succeed; `sp_load_gold` fails at the source-freshness snapshot. Expected, once.
2. Run `uv run python scripts/13_deploy_gold_sql.py --env <stage>` again. It ends with `Done.`
3. Monitoring hub › the failed run › **Rerun from failed activity**.

✅ **Check:** the queries in 4.3 give the same results as DEV (same sources): 26,538 budget rows, 300 reconciliation lines with 22 to investigate, 0 unbalanced journals. In the run, `sp_load_gold`'s input shows the stage's own warehouse ID.

### 5.4 Deploy the finance model and report

1. `dp-hh-finance` › deploy `vl_finance`, `sm_finance`, `rp_finance` and `nb_rebind_sm_finance`.
2. `vl_finance` › set the stage's value set as **active**.
3. Run `nb_rebind_sm_finance`. The `now:` line must show the stage's own `hh-dataplatform-*` workspace and `wh_gold` IDs.
4. `sm_finance` › Settings: bind the fixed-identity connection.

In a **new** stage, run the notebook (or one manual refresh of `sm_finance`) once more **after** the first green `pl_daily_load`. Its first refresh fails while Gold is still empty, and a failed refresh suspends the model's automatic updates until a refresh succeeds. After that, no refresh schedule is needed: *Keep your Direct Lake data up to date* reframes the model whenever Gold changes.

✅ **Check:** the report in the stage shows the same FY2026 numbers as DEV.

### 5.5 PROD only: govern and publish

1. `sm_finance` › Security › role **Finance**: add `sg-hh-analysts-finance` and `sg-hh-executives`. Use *Test as role*.
2. Endorse **Certified**; label **Confidential**.
3. Create the **Finance** app from `hh-finance-prod`:
   - Audience *Finance team* = `sg-hh-analysts-finance`, with *Allow users to build content with the semantic models* (needed for Excel).
   - Audience *Leadership* = `sg-hh-executives`, view only.

### 5.6 Check Excel access as a finance user

1. The user is in `sg-hh-analysts-finance` and has a licence (Pro below F64).
2. Excel › Data › Get Data › From Power Platform › **From Power BI semantic models** › the Certified `sm_finance` › PivotTable.
3. Rows: `dim_date[fiscal_year_label]`; values: *Revenue FYTD*, *Revenue Budget FYTD*.
4. Optional: PivotTable Analyze › OLAP Tools › **Convert to Formulas** gives `CUBEVALUE` formulas, as in a cube workbook. `=CUBEVALUE("<connection>","[Measures].[Data Freshness Banner]")` shows when each source was last loaded.

✅ **Check:** the numbers match the report; the user sees the app, not the workspaces; querying an `etl` table over SQL is denied.

---

## 6. Run it every day

- **Schedule:** `pl_daily_load` daily before the working day (DEV and TEST can run less often to save capacity). Weekly maintenance (`OPTIMIZE`, `VACUUM`) runs `nb_90_maintenance` on Sunday night.
- **Morning check (2 minutes):**

  ```sql
  SELECT * FROM rpt.vw_pipeline_health;        -- last run per step
  SELECT * FROM rpt.vw_source_freshness;       -- Fresh / Stale per source
  SELECT * FROM rpt.vw_dq_latest;              -- rule failures in the last run
  SELECT * FROM rpt.vw_finance_integrity;      -- open reconciliation items
  ```

- **A "next day" of data** (shows incremental loads and SCD2):

  ```powershell
  uv run python -m data_generator.generate incremental --days 3
  uv run python scripts/11_load_source_db.py
  ```

  Push the API folders again (3.3), upload changed education workbooks and marketing files, then run the pipeline. Expect small row counts, moving watermarks, and new SCD2 versions for patrons who moved.
- **Finance notes:** finance records the cause of each reconciliation difference in `fin.recon_note`; it shows in the report the next morning.

---

## 7. Change something

### 7.1 Git workflow

Work on `dev`; Fabric DEV syncs from `main`. To publish:

```powershell
git add -A; git commit -m "<what changed>"
git fetch origin; git merge --no-ff origin/main -m "Merge origin/main into dev"
git checkout main; git merge --ff-only origin/main; git merge --no-ff dev; git push; git checkout dev
```

Then the DEV workspace › Source control › **Update all**. Changes made in Fabric go the other way: **Commit** in the workspace, then bring them down:

```powershell
git checkout main; git pull; git checkout dev; git merge --no-ff main -m "Sync Fabric"
```

CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) lints, validates the config and runs the tests on every push.

### 7.2 Change the finance report

`rp_finance` is generated by [`scripts/bi/build_rp_finance.py`](../scripts/bi/build_rp_finance.py) (layout standard: 1920×1080, 30 px margins and gaps, 8 px corners, one KPI card visual per page). Edits made in the Fabric UI are overwritten on the next run.

```powershell
python scripts/bi/build_rp_finance.py fabric/bi-finance/rp_finance.Report
```

Then publish (7.1) and **Update all** in `hh-finance-dev`.

### 7.3 Change the Gold schema

Edit the file in `src/warehouse`, keeping it safe to re-run (`CREATE OR ALTER`, or `IF OBJECT_ID(...) IS NULL`). Deploy with `13_deploy_gold_sql.py --env dev`, then the same for TEST and PROD as part of the release. The anonymous-gift security rule is the exception: changing it is a deliberate migration (drop the policy, change the function, recreate the policy).

### 7.4 Promote a change

Deploy through the pipelines (Part 5). The variable libraries' active value sets stay as they are; run `nb_rebind_sm_finance` after every model deployment, and take over the Dataflow again if it was redeployed.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `sp_load_gold` error 952, "lh_silver is in transition" | Silver's SQL endpoint is still syncing a new table | The activity retries twice, 3 minutes apart. If it still fails, rerun from the failed activity. |
| First run in a new stage: "Invalid object name `rpt.vw_source_freshness`" | Views that read Silver couldn't be created before Silver existed | Run the Gold script again, then rerun from the failed activity (5.3). |
| The TEST or PROD report shows DEV's numbers | The model still points at DEV's Gold | Set the stage's value set active in `vl_finance`, run `nb_rebind_sm_finance`. |
| `NameError` in the rebind notebook | `%pip` restarts Python and clears variables set before it | Keep the `%pip` cell first. |
| Dataflow opens view-only | Only the owner can edit a Dataflow | Sign in as the stage's service account (private window) and edit, or take it over. |
| PROD Dataflow fails after about 90 seconds with `ActionUserFailure` | It still uses the non-prod connections, whose stored identity can't write to PROD's `lh_bronze` | As `svc-fabric-dataflows-prod`, bind the Dataflow to the `-prod` SharePoint and Lakehouse connections (3.4), save, refresh. |
| Report or Excel shows blank visuals in a new stage | Gold hadn't loaded when the model last refreshed, and the failed refresh suspended automatic updates | After a green `pl_daily_load`, refresh `sm_finance` once (5.4). Automatic updates resume after a successful refresh. |
| Shortcut script: "Access to target location … denied" | The stage's workspace identity has no role on the container | Grant *Storage Blob Data Reader* to that workspace identity (3.5). |
| `az` asks for `--claims-challenge` / AADSTS50076 | Conditional Access requires MFA for Azure Resource Manager | `az logout`, then the `az login … --claims-challenge` command the error prints. |
| Pipeline connection field: "Expression of type Object does not match … string" | A *connection reference* variable returns an object; pipelines need a string | Store the connection ID as a String variable. |
| Stored procedure name box shows "Failed" with a dynamic connection | The editor can't browse a warehouse resolved at run time | Type the name; validate with a run. |
| `CREATE SCHEMA` fails with "already exists" | An old copy of the SQL files | Pull the latest `src/warehouse`; every file checks before creating. |

---

## 9. Govern and tear down

- **Tenant settings audit:** `uv run python scripts/08_audit_tenant_settings.py`.
- **Capacity Metrics app:** watch CU for the pipeline and report use before changing SKU ([capacity sizing](04-capacity-sizing.md)).
- **Alerts:** an Activator rule on `dq.dq_results` (error rules with failing rows) and on `rpt.source_freshness` (status Stale).
- **OneLake catalog › Govern:** ownership, labels and endorsement coverage.
- **Teardown:** `uv run python scripts/99_teardown.py` previews; add `--confirm` to delete everything it created.
