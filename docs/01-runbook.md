# Build runbook: from an empty Fabric trial to a governed platform

Work through the phases in order. Each one ends with a ✅ **checkpoint**: what you should see, plus a screenshot to take for your portfolio (save them in `docs/screenshots/`).
Allow roughly 8–10 hours in total. Phases 1–7 set up the platform (about 2 hours); phases 8–13 build the data product; phases 14–16 cover promotion and operations.

> Run commands from the repo root in PowerShell. Every provisioning script accepts `--dry-run`, so **always dry-run first**: preview every tenant change before applying it.

---

## Phase 0 — Prerequisites (15 min)

```powershell
uv --version                              # uv already installed? skip the next line
# winget install --id astral-sh.uv          # installs uv itself (only if the line above fails)
winget install --id Microsoft.AzureCLI    # optional: 'az login' for sign-in; scripts fall back to a browser pop-up
az login --allow-no-subscriptions         # sign in as your Fabric admin account
uv sync --group dev                       # creates .venv with dependencies
Copy-Item .env.example .env               # your tenant-specific values go here, never in a committed file
uv run python main.py                     # prints the build order
uv run python scripts/validate_config.py  # lint the tenant design
uv run pytest -q                          # generator unit tests
```

- Confirm the **Fabric trial** is active: Settings (gear) › **Admin portal** › Capacity settings › Trial.
- Confirm you're a **Fabric administrator**: the Admin portal opens and shows Tenant settings.

✅ `validate_config.py` prints `OK: 7 groups, 4 domains, 9 workspaces, 17 entities, 27 DQ rules`. The WARN lines about placeholders are expected until Phase 8.

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
3. In Fabric, go to Settings › **Manage connections and gateways** › New › *GitHub – Source control*. Paste the PAT and name the connection `github-hh-platform`. Put its **Connection ID** in `.env` as `FABRIC_GIT_CONNECTION_ID`.
4. Run the script:

   ```powershell
   uv run python scripts/05_connect_git.py --dry-run
   uv run python scripts/05_connect_git.py
   ```

✅ Each DEV workspace shows Source control connected to `main`, in folders `fabric/de`, `fabric/bi-audience` and `fabric/bi-education`. Commits appear in GitHub.

---

## Phase 8 — Land the data: four sources, four patterns (about 2 hours)

Each source reaches Fabric the way it would in real life (see [ADR-003](adr/ADR-003-ingestion-tools.md) and [`src/ingestion/`](../src/ingestion/README.md)):

| Source | You put it in | Fabric reads it with |
|---|---|---|
| Ticketing | SQL Server on your computer, through the on-premises data gateway | Copy job `cj_ticketing` |
| Fundraising | A GitHub Pages site (mock API) | Notebook `nb_05_fundraising_api` |
| Education | A SharePoint document library | Dataflow Gen2 `df_education_sharepoint` |
| Marketing | An ADLS Gen2 container | Shortcut `lh_bronze/Files/landing/marketing` |

### 8.0 Generate the data

```powershell
uv run python -m data_generator.generate full --start 2023-07-01 --end 2026-09-27
```

This writes four folders under `data/`: `ticketing_db`, `fundraising_api`, `education_sharepoint` and `marketing_adls`. About 645k rows in total, with **deliberate defects** for the quality checks to catch: duplicate patrons, bad emails and zip codes, orphan and negative order lines, future-dated gifts, sessions with no participants, clicks exported twice, overlapping API pages and negative ad spend.

Copy the config to the lakehouse (run it again whenever you change `.env` or the config):

```powershell
uv run python scripts/validate_config.py     # WARN lines disappear once .env has every value
uv run python scripts/06_upload_config.py --env dev
```

### 8.1 Ticketing: on-premises SQL Server → gateway → Copy job

The mock Tessitura runs on SQL Server on your own computer. Fabric reaches it through the **on-premises data gateway**, which is how most real ticketing databases are reached: they sit inside the organization's network, not in the cloud.

1. **Driver.** The loader needs the ODBC Driver 18 for SQL Server. Check with `Get-OdbcDriver -Name "ODBC Driver 18*"`; if nothing comes back, [install it](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
2. **Settings in `.env`:** `TICKETING_SQL_SERVER=localhost` (or `localhost\INSTANCE` for a named instance), `TICKETING_SQL_DATABASE=HarmoniaTicketing`, `TICKETING_SQL_AUTH=windows`, and `TICKETING_SQL_TRUST_SERVER_CERT=yes`. A local SQL Server uses a self-signed certificate, which is fine to trust on your own computer only.
3. **Load the data** with your Windows account. The script creates the database the first time:

   ```powershell
   uv run python scripts/11_load_ticketing_db.py --dry-run   # prints the CREATE TABLE statements
   uv run python scripts/11_load_ticketing_db.py             # ~510k rows, a few minutes
   ```

4. **A read-only login for Fabric.** Fabric should never use your own account. In SSMS:
   1. Server › Properties › Security › **SQL Server and Windows Authentication mode**, then restart the SQL Server service. (Mixed mode is off by default.)
   2. Run this, with a strong password you keep only in the Fabric connection:

      ```sql
      CREATE LOGIN svc_fabric_reader WITH PASSWORD = '<strong password>', CHECK_POLICY = ON;
      USE HarmoniaTicketing;
      CREATE USER svc_fabric_reader FOR LOGIN svc_fabric_reader;
      GRANT SELECT ON SCHEMA::tix TO svc_fabric_reader;   -- read the ticketing tables, nothing else
      ```

5. **Gateway.** Your gateway shows *Microsoft Fabric: Ready*. Two things before you rely on it:
   - Install the **update** the gateway app offers. New Copy job features need a recent gateway, and Microsoft only supports the last few versions.
   - The gateway runs on your computer, so the Copy job only works while that computer is on and awake.
6. **Connection.** Fabric › Settings › **Manage connections and gateways** › New › **On-premises**:
   - Gateway cluster: your gateway. Connection type: **SQL Server**. Server `localhost`, database `HarmoniaTicketing`.
   - Authentication: **Basic**, as `svc_fabric_reader`.
   - If the test fails on the certificate, untick encryption for this lab connection. The traffic never leaves your computer. In production you'd install a trusted certificate instead.
7. Build the Copy job: [`src/ingestion/copy_job_ticketing.md`](../src/ingestion/copy_job_ticketing.md).

✅ `tix` has seven tables, and `lh_bronze` › Tables › `ticketing` has the same seven after the Copy job runs. The source is on-premises, read through a gateway with a read-only service login, and loaded incrementally.

### 8.2 Fundraising: a mock API on GitHub Pages

The API is a set of static JSON files with paging, so it costs nothing and needs no server. It lives in its own public repo so your portfolio site stays clean (the data is synthetic, so public is fine).

1. On GitHub, create a public repo `harmonia-hall-api` with a README, then:

   ```powershell
   cd C:\dev
   git clone https://github.com/musatouray/harmonia-hall-api.git
   Copy-Item -Recurse -Force .\performing-arts-audience-development-platform\data\fundraising_api\* .\harmonia-hall-api\
   cd harmonia-hall-api
   git add -A; git commit -m "Fundraising API data"; git push
   cd ..\performing-arts-audience-development-platform
   ```

2. In the repo: **Settings › Pages › Deploy from a branch**, branch `main`, folder `/ (root)`.
3. After a minute or two, open `https://musatouray.github.io/harmonia-hall-api/v1/index.json`. It lists the available days.
4. Set `FUNDRAISING_API_BASE_URL=https://musatouray.github.io/harmonia-hall-api/v1` in `.env`.

✅ The index opens in a browser, and `.../v1/gifts/2026-09-27/page-1.json` shows `count`, `value` and `next_link`. The notebook runs in Phase 9.

### 8.3 Education: SharePoint → Dataflow Gen2

1. Upload `data/education_sharepoint/` to a SharePoint document library as described in [`src/ingestion/dataflow_education.md`](../src/ingestion/dataflow_education.md).
2. Set `EDUCATION_SHAREPOINT_SITE` in `.env` (for your records; the Dataflow has its own `SiteUrl` parameter).
3. Build `df_education_sharepoint` from the spec.
4. **Let the workspace identity read the site** (only if the SharePoint connection uses *Workspace identity*). An app identity can't be added with the site's Share button; it needs `Sites.Selected`, which gives no access until one site is granted. As a tenant admin, in PowerShell:

   ```powershell
   ./scripts/12_grant_sharepoint_site_access.ps1 -WorkspaceIdentityAppId "<app ID>" -SiteUrl "<site URL>"
   ```

   The app ID is in `hh-dataplatform-dev` › Workspace settings › **Workspace identity**. Run it once per environment, since test and prod have their own identities. Allow a few minutes, then refresh the Dataflow.

> If your SharePoint site is in a different Microsoft 365 tenant from Fabric (common with an E5 developer tenant), sign in to the SharePoint connection with an account from that tenant.

✅ `lh_bronze` › Tables › `dbo` has `programs`, `schools` and `enrollments` (Dataflow Gen2 can't choose a schema yet; Silver puts them in `education`). Screenshot the Dataflow's query view.

### 8.4 Marketing: ADLS Gen2 → shortcut

1. **Storage.** In the Azure portal, create a storage account with **Hierarchical namespace** turned on (that's what makes it ADLS Gen2), then **one** container named `marketing-exports`.
   - One container per source, with a folder per table inside it. Container names can't have underscores, but folder names can, and the folders must match the table names in `sources.yaml` (`email_campaigns`, not `email-campaigns`).
   - One container also means one place to set access, one shortcut, and one retention policy for the whole source.
2. **Upload** the *contents* of `data/marketing_adls/` to the root of the container, with Azure Storage Explorer (drag and drop) or:

   ```powershell
   az storage blob upload-batch --account-name <account> -d marketing-exports -s data/marketing_adls --auth-mode login
   ```

   `upload-batch` copies what's *inside* the folder, keeping the paths below it. The container should show four folders at the top level: `email_campaigns/`, `email_clicks/`, `ad_spend_daily/` and `_manifests/`. (You need **Storage Blob Data Contributor** on the account to upload. Owner isn't enough: it covers managing the account, not its data.)
3. **Workspace identity.** `hh-dataplatform-dev` › Workspace settings › **Workspace identity** › create it. This lets Fabric reach the storage account as the workspace itself, so no person's sign-in or secret is involved.
4. **Give the identity read access.** Storage account › Access control (IAM) › Add role assignment › **Storage Blob Data Reader** › Members: *Managed identity*, then pick the identity named after the workspace (`hh-dataplatform-dev`). Reader is enough: Fabric only reads these files. Role assignments can take a few minutes to apply.
5. **Connection.** Fabric › Settings › **Manage connections and gateways** › New › Cloud › *Azure Data Lake Storage Gen2*, URL `https://<account>.dfs.core.windows.net`, authentication **Workspace identity**. Put the account URL and the connection ID in `.env` (`MARKETING_ADLS_ACCOUNT_URL`, `MARKETING_ADLS_CONNECTION_ID`). The identity's own ID isn't needed anywhere.
6. **Check the plan** with the script, without changing anything:

   ```powershell
   uv run python scripts/10_create_shortcuts.py --env dev --dry-run
   ```

7. **Create the shortcut in the UI** (the script can do the same thing; it's kept as the repeatable version for test and prod):
   1. Open `lh_bronze` › **Files**. If there's no `landing` folder yet, create it (**…** › New subfolder).
   2. On `landing`, select **…** › **New shortcut** › *Azure Data Lake Storage Gen2*.
   3. Choose **Existing connection** › your marketing connection, then **Next**.
   4. Select the `marketing-exports` **container** itself (not the folders inside it), then **Next**.
   5. Rename the shortcut from `marketing-exports` to **`marketing`**, then **Create**. The name matters: the notebooks look for `Files/landing/marketing`.

✅ `lh_bronze` › Files › landing shows `marketing` with a shortcut icon, and opening it lists `email_campaigns`, `email_clicks`, `ad_spend_daily` and `_manifests`. No data is copied, and access uses the workspace identity, so there are no secrets to manage.

> Test and prod workspaces each need their **own** workspace identity, role assignment and shortcut. Workspace identities belong to one workspace, which is exactly what keeps environments isolated. Use `10_create_shortcuts.py --env test` there, after the identity and role are set up.

Finally, run `scripts/06_upload_config.py --env dev` again. It uploads the config with your `.env` values filled in, so the notebooks see the real settings while GitHub never does.

---

## Phase 9 — Notebooks: Bronze and Silver (DEV)

The notebooks live in [`fabric/de`](../fabric/de), which the DEV workspace syncs with through Fabric Git integration.

1. In `hh-dataplatform-dev`, open **Source control** and **Update** to pull them from Git. To change a notebook, edit it in Fabric and **Commit**; don't hand-edit the files in `fabric/de`.
2. Open each notebook and attach only the lakehouses it uses:
   - `nb_05_fundraising_api` and `nb_10_bronze_ingest`: **lh_bronze** only. They read and write Bronze, nothing else.
   - `nb_20_silver_transform`: **lh_silver** (default) + lh_bronze. It reads Bronze and writes Silver.
   - `nb_90_maintenance`: **lh_silver** (default) + lh_bronze. It maintains tables in both.
   - `nb_00_common`: nothing. It's a helper that runs inside whichever notebook calls it (`%run`).
3. Run `nb_05_fundraising_api`, then `nb_10_bronze_ingest`, then `nb_20_silver_transform`.

✅ You should see:

- `nb_05` prints a note that gifts and donors returned more records than their count. That's the overlapping-pages defect; Silver removes the duplicates.
- Bronze has tables under schemas `ticketing`, `fundraising`, `marketing` and `dbo` (education).
- `audit.reconciliation` shows all fundraising and marketing rows **OK** (ticketing and education are checked in their Copy job and Dataflow run history).
- Silver has typed tables, `dq.dq_results`, `dq.quarantine` (several hundred rows, including clicks for an unknown email campaign and negative ad spend), `core.patron_xref` and `core.patron`.
- The run log message reads "N source records → M patrons (x% de-duplicated)".

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
| `60_security.sql` | GRANT, DDM, RLS |
| `61_security_users.local.sql` | Who sees anonymous gifts and which venues each manager sees. Copy `61_security_users.example.sql` to this name (ignored by Git) and put in real sign-in names first. |

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
2. Set up TEST's ingestion: run `06_upload_config.py --env test` and `10_create_shortcuts.py --env test`. Open `cj_ticketing` and `df_education_sharepoint` in TEST and check their destination is **TEST's** `lh_bronze`; fix it if it still points at DEV. (In this lab all three environments read the same sources. In production each one would have its own connection.) In TEST, run the SQL files, then the pipeline. **Share TEST `wh_gold` with `sg-hh-bi-developers`** as in Phase 13, step 0, and run `09_verify_item_shares.py --env test`. Do the same for PROD before promoting the BI models.
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
uv run python scripts/11_load_ticketing_db.py      # ticketing changes into SQL Server
```

Then hand the other three sources their new data:

- **Fundraising:** copy `data/fundraising_api/*` into your `harmonia-hall-api` clone again and push (same commands as 8.2).
- **Education:** upload the changed `Sessions YYYY-MM.xlsx` workbook(s) to SharePoint, replacing the old ones.
- **Marketing:** upload `data/marketing_adls/` to the container again (same command as 8.4). Old files are just overwritten, and nb_10 skips days it has already loaded.

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
