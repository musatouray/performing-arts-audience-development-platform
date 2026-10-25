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

✅ `validate_config.py` prints `OK: 9 groups, 4 domains, 9 workspaces, 17 entities, 27 DQ rules`. The WARN lines about placeholders are expected until Phase 8.

---

## Phase 1 — Identity: Entra security groups (step 00)

```powershell
uv run python scripts/00_create_security_groups.py --dry-run
uv run python scripts/00_create_security_groups.py --add-me-to fabric_admins
```

- This creates the eleven `sg-hh-*` groups and writes `config/.generated/principals.json`: nine for people (including `sg-hh-analysts-finance` and `sg-hh-analysts-operations`), and two service groups, `sg-hh-svc-dataflows-nonprod` and `sg-hh-svc-dataflows-prod`.
- **Service accounts** are created by hand in Entra, because only an admin should hold their passwords. There are two, split by prod and non-prod:

  | Account | Group | Workspaces | Who uses the password |
  |---|---|---|---|
  | `svc-fabric-dataflows-nonprod@<tenant>` | `sg-hh-svc-dataflows-nonprod` | `hh-dataplatform-dev`, `-test` (Contributor) | Engineers, to take over and fix Dataflows |
  | `svc-fabric-dataflows-prod@<tenant>` | `sg-hh-svc-dataflows-prod` | `hh-dataplatform-prod` (Contributor) | Platform owner only, once per prod deploy |

  Why two and not one: engineers sign in as the non-prod account every day, so if it could also write to prod, anyone who knew its password could change prod data without going through the deployment pipeline. Each account goes **only** into its own service group, never into a human group such as `sg-hh-data-engineers`. Give each a Fabric licence, no mailbox, a long random password kept in a password manager or Key Vault, and a named owner. Leave MFA on: you complete it once when the account takes over a Dataflow.
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

✅ In **Admin portal › Domains** you see Harmonia Hall › Data Platform / Audience & Development / Education & Community / Finance / Operations. Screenshot it.

Domain admins appear on **Harmonia Hall** only; the subdomains inherit them. Domain roles don't give access to any workspace or data. Access comes from the workspace roles set in Phase 4.

Optional, in the UI, on the **parent domain** (subdomains have no image or admin settings of their own; they inherit from the parent): pick a cover image from the gallery, set a **default sensitivity label**, and delegate settings to domain admins.

---

## Phase 4 — Workspaces (step 02)

```powershell
uv run python scripts/02_create_workspaces.py --dry-run
uv run python scripts/02_create_workspaces.py
```

✅ There are fifteen workspaces (`hh-{dataplatform|audience|education|finance|operations}-{dev|test|prod}`), each on the trial capacity, assigned to its domain, with **group** roles only (Manage access). Each description says who it's for, e.g. `DEV - Marketing, Ticketing Services, Development` (from `serves` in `tenant.yaml`; re-running the script updates existing workspaces). Screenshot the workspace list filtered by domain.

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

✅ There are five pipelines (`dp-hh-dataplatform`, `dp-hh-audience`, `dp-hh-education`, `dp-hh-finance`, `dp-hh-operations`), each Development › Test › Production with its workspaces assigned. Screenshot one.

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

✅ Each DEV workspace shows Source control connected to `main`, in folders `fabric/de`, `fabric/bi-audience`, `fabric/bi-education`, `fabric/bi-finance` and `fabric/bi-operations`. Commits appear in GitHub.

---

## Phase 8 — Land the data: six source systems, four patterns (about 3 hours)

Each source reaches Fabric the way it would in real life (see [ADR-003](adr/ADR-003-ingestion-tools.md) and [`src/ingestion/`](../src/ingestion/README.md)):

| Source | You put it in | Fabric reads it with |
|---|---|---|
| Tessitura (database) | SQL Server on your computer, through the on-premises data gateway | Copy job `cj_tessitura` |
| Tessitura (REST API) | A GitHub Pages site (mock API) | Notebook `nb_05_api_ingest` |
| MIP (general ledger) | A second SQL Server database on your computer, through the same gateway | Copy job `cj_mip` |
| Diese (hall bookings) | A second GitHub Pages site (mock API) | The same notebook, `nb_05_api_ingest` |
| Education | A SharePoint document library | Dataflow Gen2 `df_education_sharepoint` |
| Marketing | An ADLS Gen2 container | Shortcut `lh_bronze/Files/landing/marketing` |

### 8.0 Generate the data

```powershell
uv run python -m data_generator.generate full --start 2023-07-01 --end 2026-10-10
```

This writes six folders under `data/`: `tessitura_db`, `tessitura_api`, `education_sharepoint`, `marketing_adls`, `mip_db` and `diese_api`. About 680k rows in total, with **deliberate defects** for the quality checks to catch: duplicate patrons, bad emails and zip codes, orphan and negative order lines, future-dated gifts, sessions with no participants, clicks exported twice, overlapping API pages and negative ad spend.

Copy the config to the lakehouse (run it again whenever you change `.env` or the config):

```powershell
uv run python scripts/validate_config.py     # WARN lines disappear once .env has every value
uv run python scripts/06_upload_config.py --env dev
```

### 8.1 Tessitura database: on-premises SQL Server → gateway → Copy job

The mock Tessitura runs on SQL Server on your own computer. Fabric reaches it through the **on-premises data gateway**, which is how most real ticketing databases are reached: they sit inside the organization's network, not in the cloud.

1. **Driver.** The loader needs the ODBC Driver 18 for SQL Server. Check with `Get-OdbcDriver -Name "ODBC Driver 18*"`; if nothing comes back, [install it](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
2. **Settings in `.env`:** `TESSITURA_SQL_SERVER=localhost` (or `localhost\INSTANCE` for a named instance), `TESSITURA_SQL_DATABASE=HarmoniaTessitura`, `TESSITURA_SQL_AUTH=windows`, and `TESSITURA_SQL_TRUST_SERVER_CERT=yes`. A local SQL Server uses a self-signed certificate, which is fine to trust on your own computer only.
3. **Load the data** with your Windows account. The script creates the database the first time:

   ```powershell
   uv run python scripts/11_load_source_db.py --source tessitura_db --dry-run   # prints the CREATE TABLE statements
   uv run python scripts/11_load_source_db.py --source tessitura_db  # ~510k rows, a few minutes
   ```

4. **A read-only login for Fabric.** Fabric should never use your own account. In SSMS:
   1. Server › Properties › Security › **SQL Server and Windows Authentication mode**, then restart the SQL Server service. (Mixed mode is off by default.)
   2. Run this, with a strong password you keep only in the Fabric connection:

      ```sql
      CREATE LOGIN svc_fabric_reader WITH PASSWORD = '<strong password>', CHECK_POLICY = ON;
      USE HarmoniaTessitura;
      CREATE USER svc_fabric_reader FOR LOGIN svc_fabric_reader;
      GRANT SELECT ON SCHEMA::tix TO svc_fabric_reader;   -- read the Tessitura tables, nothing else
      ```

5. **Gateway.** Your gateway shows *Microsoft Fabric: Ready*. Two things before you rely on it:
   - Install the **update** the gateway app offers. New Copy job features need a recent gateway, and Microsoft only supports the last few versions.
   - The gateway runs on your computer, so the Copy job only works while that computer is on and awake.
6. **Connection.** Fabric › Settings › **Manage connections and gateways** › New › **On-premises**:
   - Gateway cluster: your gateway. Connection type: **SQL Server**. Server `localhost`, database `HarmoniaTessitura`.
   - Authentication: **Basic**, as `svc_fabric_reader`.
   - If the test fails on the certificate, untick encryption for this lab connection. The traffic never leaves your computer. In production you'd install a trusted certificate instead.
7. Build the Copy job: [`src/ingestion/copy_job_tessitura.md`](../src/ingestion/copy_job_tessitura.md).

✅ `tix` has seven tables, and `lh_bronze` › Tables › `tessitura` has the same seven after the Copy job runs. The source is on-premises, read through a gateway with a read-only service login, and loaded incrementally.

### 8.2 Tessitura REST API: a mock API on GitHub Pages

The API is a set of static JSON files with paging, so it costs nothing and needs no server. It lives in its own public repo so your portfolio site stays clean (the data is synthetic, so public is fine).

1. On GitHub, create a public repo `harmonia-hall-api` with a README, then:

   ```powershell
   cd C:\dev
   git clone https://github.com/musatouray/harmonia-hall-api.git
   # /MIR makes the repo an exact copy (old files are removed); /XD .git leaves git's folder alone
   robocopy .\performing-arts-audience-development-platform\data\tessitura_api .\harmonia-hall-api /MIR /XD .git /NJH /NP
   cd harmonia-hall-api
   git add -A; git commit -m "Tessitura API data"; git push
   cd ..\performing-arts-audience-development-platform
   ```

2. In the repo: **Settings › Pages › Deploy from a branch**, branch `main`, folder `/ (root)`.
3. After a minute or two, open `https://musatouray.github.io/harmonia-hall-api/v1/index.json`. It lists the available days.
4. Set `TESSITURA_API_BASE_URL=https://musatouray.github.io/harmonia-hall-api/v1` in `.env`.

✅ The index opens in a browser, and `.../v1/gifts/2026-09-27/page-1.json` shows `count`, `value` and `next_link`. The notebook runs in Phase 9.

### 8.2b MIP general ledger: a second on-premises database

Finance's ledger lives on-premises like Tessitura, so it uses the same pattern, with its own login: finance owns it, so its access is granted and revoked on its own.

1. `MIP_SQL_SERVER`, `MIP_SQL_DATABASE=HarmoniaMIP`, `MIP_SQL_AUTH`, `MIP_SQL_TRUST_SERVER_CERT` in `.env` (see `.env.example`).
2. `uv run python scripts/11_load_source_db.py --source mip_db` creates `HarmoniaMIP` and loads about 11.7k journal lines.
3. Login, connection and Copy job `cj_mip`: [`src/ingestion/copy_job_mip.md`](../src/ingestion/copy_job_mip.md).

✅ `lh_bronze` › Tables › `mip` has four tables, and every journal balances.

### 8.2c Diese bookings: a second mock API

Diese is a separate system, so it gets its own GitHub Pages repo, `harmonia-hall-diese-api` (Settings › Pages › branch `main`, `/ (root)`):

```powershell
cd C:\dev
robocopy .\performing-arts-audience-development-platform\data\diese_api .\harmonia-hall-diese-api /MIR /XD .git /NJH /NP
cd .\harmonia-hall-diese-api; git add -A; git commit -m "Diese booking API data"; git push
```

Set `DIESE_API_BASE_URL=https://<you>.github.io/harmonia-hall-diese-api/v1` in `.env`. No new notebook: `nb_05_api_ingest` reads every `notebook_api` source in `sources.yaml`.

✅ `.../v1/index.json` lists `room`, `event` and `booking`.

### 8.3 Education: SharePoint → Dataflow Gen2

1. Upload `data/education_sharepoint/` to a SharePoint document library as described in [`src/ingestion/dataflow_education.md`](../src/ingestion/dataflow_education.md).
2. Set `EDUCATION_SHAREPOINT_SITE` in `.env` (for your records; the Dataflow has its own `SiteUrl` parameter).
3. Build `df_education_sharepoint` from the spec.
4. **Run the Dataflow as a service account.** Dataflow Gen2 always runs as its owner, and its Lakehouse destination only accepts an organizational account (no service principal or workspace identity yet). Use `svc-fabric-dataflows-nonprod` from Phase 1, which is in `sg-hh-svc-dataflows-nonprod` and so already Contributor on `hh-dataplatform-dev` (`tenant.yaml`). Give that **group** (and `sg-hh-svc-dataflows-prod`) Read on the SharePoint site (site › Settings › Site permissions › Share site only, *Read*) and make the account a **User** of the SharePoint and Lakehouse connections. Then sign in as the account, take over the Dataflow (**Settings › Take over**) and sign in to both connections. See ADR-003.
5. **Optional, for a notebook-based alternative: let the workspace identity read the site.** This does *not* make the Dataflow user-independent (see step 4), but a notebook calling Microsoft Graph as the workspace identity can use it. An app identity can't be added with the site's Share button; it needs `Sites.Selected`, which gives no access until one site is granted. As a tenant admin, in PowerShell:

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
   - `nb_05_api_ingest` and `nb_10_bronze_ingest`: **lh_bronze** only. They read and write Bronze, nothing else.
   - `nb_20_silver_transform`: **lh_silver** (default) + lh_bronze. It reads Bronze and writes Silver.
   - `nb_90_maintenance`: **lh_silver** (default) + lh_bronze. It maintains tables in both.
   - `nb_00_common`: nothing. It's a helper that runs inside whichever notebook calls it (`%run`).
3. Run `nb_05_api_ingest`, then `nb_10_bronze_ingest`, then `nb_20_silver_transform`.

✅ You should see:

- `nb_05` prints a note that gifts and donors returned more records than their count. That's the overlapping-pages defect; Silver removes the duplicates.
- Bronze has tables under schemas `tessitura`, `mip`, `diese`, `marketing` and `dbo` (education).
- `audit.reconciliation` shows all Tessitura API, Diese API and marketing rows **OK** (the Tessitura and MIP databases and education are checked in their Copy job and Dataflow run history).
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
| `70_finance_and_venue_ops.sql` | Finance and Operations: ledger, hall calendar, revenue-to-ledger reconciliation and their grants. Needs the `sg-hh-analysts-finance` and `sg-hh-analysts-operations` groups (step 00). |
| `80_source_freshness.sql` | How current each source is (`rpt.vw_source_freshness`, and a snapshot table for the models) |
| `75_marketing.sql` | Marketing in Gold: email campaigns, clicks linked to patrons (no email addresses), paid ad spend, and two `rpt` views |

Run `40_load_facts.sql` again after 70, 75 and 80: the orchestrator calls their procedures.

Then run:

```sql
EXEC etl.usp_load_gold @run_id = 'manual-001';
SELECT * FROM rpt.vw_donor_retention ORDER BY fiscal_year;
SELECT TOP 20 * FROM rpt.vw_performance_sell_through ORDER BY sell_through_pct DESC;
SELECT * FROM rpt.vw_gold_integrity;
SELECT * FROM rpt.vw_finance_integrity;
SELECT [status], COUNT(*) FROM fin.recon_revenue_to_gl GROUP BY [status];
SELECT * FROM rpt.vw_source_freshness;
```

✅ You should see a load log with row counts, a donor retention rate per FY, and sell-through per show. Screenshot the query results.

---

## Phase 11 — Orchestration pipeline

Build `pl_daily_load` and `pl_weekly_maintenance` in `hh-dataplatform-dev` exactly as specified in [`src/pipelines/pl_daily_load.md`](../src/pipelines/pl_daily_load.md), then run it. It runs both Copy jobs (`cj_tessitura`, `cj_mip`) side by side; `nb_silver` waits for both.

✅ The Monitoring hub shows a green run. `rpt.vw_pipeline_health` shows the Bronze, Silver and Gold steps under one `run_id`. Screenshot the pipeline canvas.

---

## Phase 12 — OneLake security (step 07)

1. Open `lh_silver` › **Manage OneLake security** › enable it (one-time).
2. Run the script:

   ```powershell
   uv run python scripts/07_apply_onelake_security.py --env dev --dry-run
   uv run python scripts/07_apply_onelake_security.py --env dev
   ```

✅ One role, **DataScienceReaders**, with `sg-hh-data-science` as its member, and no DefaultReader. Analysts read Gold, not Silver (ADR-006); engineers reach Silver through their workspace role. The script replaces all roles each time, so roles removed from `tenant.yaml` disappear too. DevelopmentReaders can't see `email`, `phone` or `address_line1` on `core.patron`. Screenshot the role editor.

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
7. Repeat a lighter version for `sm_education_impact` in `hh-education-dev`, `sm_finance` in `hh-finance-dev` and `sm_operations` in `hh-operations-dev` (tables, relationships and measures in `model.md`, `finance_measures.dax` and `operations_measures.dax`).
8. **Commit** every BI workspace to Git (Source control › Commit).

✅ Screenshot the model diagram view, the RLS test as the Audience role (donor visuals empty), and the report.

---

## Phase 14a — Variable libraries: what changes between stages (set up once, in DEV)

Deployment pipelines copy definitions as they are. Anything that names a *specific* item by ID would still point at DEV after a deploy. References inside the same workspace rebind on their own (the pipeline's notebook, Copy job and Dataflow activities use logical IDs), so only these need a variable:

| Consumer | What would stay on DEV | Fix |
|---|---|---|
| `pl_daily_load` › `sp_load_gold` | wh_gold's item ID and SQL endpoint | `vl_platform` variables in the activity's connection |
| Notebooks' default lakehouse | lh_bronze / lh_silver IDs in the notebook metadata | `%%configure` from `vl_platform` (below) |
| `cj_tessitura`, `cj_mip`, `df_education_sharepoint` destinations | lh_bronze's ID | `vl_platform` in the destination, where the item offers it; otherwise check the destination once after the first deploy |
| `sm_finance` (Direct Lake on OneLake) | DEV wh_gold in the source URL | Semantic models can't read a variable library: `nb_rebind_sm_finance` reads `vl_finance` and rewrites the source |

Values are IDs, not secrets, but they are tenant-specific, so they live in the variable library inside Fabric and never in the repo. Look them up in each item's URL (or `GET /v1/workspaces/{id}/items`). The warehouse SQL endpoint is under wh_gold › Settings › SQL endpoint.

1. **`vl_platform`** in `hh-dataplatform-dev` (New item › Variable library). All variables are String, even the GUIDs:
   `workspace_id`, `lh_bronze_id`, `lh_silver_id`, `wh_gold_id`, `wh_gold_endpoint`.
   The default value set holds DEV's values. Add the value sets **TEST** and **PROD** with those workspaces' values. Save.
2. **Pipeline:** open `pl_daily_load` › *Library variables* (bottom pane) and add the three Gold ones. In `sp_load_gold` › Settings, switch the warehouse connection to dynamic content: workspace ID `@pipeline().libraryVariables.workspace_id`, warehouse ID `@pipeline().libraryVariables.wh_gold_id`, SQL connection string `@pipeline().libraryVariables.wh_gold_endpoint`.
3. **Notebooks:** make this the first cell of `nb_20_silver_transform` and `nb_90_maintenance` (`lh_bronze` / `lh_bronze_id` for `nb_05` and `nb_10`):
   ```text
   %%configure
   { "defaultLakehouse": { "name": "lh_silver",
                           "id": { "variableName": "$(/**/vl_platform/lh_silver_id)" },
                           "workspaceId": { "variableName": "$(/**/vl_platform/workspace_id)" } } }
   ```
   The code itself already finds lakehouses by name in its own workspace (`nb_00_common`), so this cell is the only stage-specific part.
4. **Copy jobs and Dataflow:** set the destination lakehouse from `vl_platform` where the editor offers it.
5. **`vl_finance`** in `hh-finance-dev`: `gold_workspace_id` and `gold_warehouse_id` (String), with DEV / TEST / PROD value sets pointing at each stage's `hh-dataplatform-*` / `wh_gold`. Then create the notebook `nb_rebind_sm_finance` from [`scripts/bi/rebind_direct_lake.py`](../scripts/bi/rebind_direct_lake.py).
6. **Prove DEV still works:** run `pl_daily_load` in DEV, then **Commit** both workspaces and bring the commit down (`git checkout main; git pull; git checkout dev; git merge --no-ff main`).

After the **first** deploy to a stage, open that stage's variable library and make its value set active (TEST in TEST, PROD in PROD). Each stage keeps its own active set, so later deploys don't change it. Check that once after the second deploy.

✅ After deploying to TEST, the run's `sp_load_gold` input shows TEST's warehouse ID, and `nb_rebind_sm_finance` prints TEST's IDs on the "now:" line.

---

## Phase 14 — Promote DEV › TEST › PROD

1. In `dp-hh-dataplatform`, **Deploy** Development › Test.
   - Select the variable library, notebooks, Copy jobs, the Dataflow and the pipeline. **Leave out** `lh_bronze`, `lh_silver`, `wh_gold` (they already exist in each stage, and Gold's schema comes from the repo) and the `Staging*` items the Dataflow creates by itself.
   - Stage-specific values come from `vl_platform` (Phase 14a), not from deployment rules. After the first deploy, make the **TEST** value set active in TEST.
2. Set up TEST's ingestion: run `06_upload_config.py --env test` and `10_create_shortcuts.py --env test`. Open `cj_tessitura` and `df_education_sharepoint` in TEST and check their destination is **TEST's** `lh_bronze`; fix it if it still points at DEV. A deployment copies item definitions, **not data**: TEST and PROD start empty and load their own data by running `pl_daily_load` from their own connections. The person who deploys a Dataflow becomes its owner, so after each deploy have the right service account take it over (Phase 8.3, step 4): `svc-fabric-dataflows-nonprod` in TEST, `svc-fabric-dataflows-prod` in PROD. (In this lab all three environments read the same sources. In production each one would have its own connection.) In TEST, deploy the Gold schema from the repo with `uv run python scripts/13_deploy_gold_sql.py --env test` (the same files, in the same order, as Phase 10; `--dry-run` lists them), then run the pipeline. Warehouses are left out of the deployment on purpose: Gold's schema always comes from the repo. The **first** time in a new stage, three views that read Silver tables (`rpt.vw_dq_latest`, `rpt.vw_pipeline_health`, `rpt.vw_source_freshness`) can't be created yet: the script sets them aside and exits with code 2. Run the pipeline once (`sp_load_gold` fails at the freshness snapshot, once), run the script again, then rerun the pipeline from the failed activity. **Share TEST `wh_gold` with `sg-hh-bi-developers`** as in Phase 13, step 0, and run `09_verify_item_shares.py --env test`. Do the same for PROD before promoting the BI models.
3. In `dp-hh-audience` (and `dp-hh-finance`, `dp-hh-operations`), **Deploy** Development › Test. **Rebind the model** to TEST's `wh_gold`: a Direct Lake on OneLake model keeps DEV's workspace and item IDs in its source URL, so without this the TEST model reads DEV data. Run `nb_rebind_sm_finance` ([`scripts/bi/rebind_direct_lake.py`](../scripts/bi/rebind_direct_lake.py)), which the deployment carried over: it reads that stage's Gold IDs from `vl_finance` and refreshes the model (Phase 14a). Then bind the model to a fixed-identity cloud connection (Phase 13, step 4). For a Direct Lake on SQL model the older call below also works:

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
uv run python scripts/11_load_source_db.py         # Tessitura and MIP changes into SQL Server
```

Then hand the other three sources their new data:

- **Tessitura API:** copy `data/tessitura_api/*` into your `harmonia-hall-api` clone again and push (same commands as 8.2).
- **Diese API:** the same for `data/diese_api/*` and `harmonia-hall-diese-api` (8.2c).
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

## Phase 15b — Add Finance and Operations to a running platform (ADR-009)

Use this if the platform already runs the original sources (Phases 0–9 at least). It adds MIP (the ledger), Diese (hall bookings) and the Finance and Operations spokes **without rebuilding anything**, in three parts: the structure first, then the data, then Gold and the models. Each step links to the full instructions above.

### Part A — Structure: workspaces, domains, groups, Git (no new data needed)

1. **Push the repo, then pull it into Fabric.** First make sure `hh-dataplatform-dev` › Source control shows **no uncommitted changes** (commit them if it does), so your push goes on top of Fabric's work:
   ```powershell
   git checkout dev; git add -A; git commit -m "MIP, Diese, Finance and Operations spokes"
   git checkout main; git pull
   git checkout dev; git merge --no-ff main -m "Sync Fabric"
   git checkout main; git merge --no-ff dev; git push; git push origin dev
   ```
   Then `hh-dataplatform-dev` › Source control › **Update all**. `nb_05_tessitura_api` is renamed `nb_05_api_ingest` (Phase 9). Don't run the pipeline yet: the Diese API isn't published until Part B.
2. **Tenant.** Each script skips what already exists; add `--dry-run` to preview:
   ```powershell
   uv run python scripts/validate_config.py
   uv run python scripts/00_create_security_groups.py      # + sg-hh-analysts-finance, sg-hh-analysts-operations (Phase 1)
   uv run python scripts/01_create_domains.py              # + Finance, Operations (Phase 3)
   uv run python scripts/02_create_workspaces.py           # + hh-finance-*, hh-operations-*; updates every description (Phase 4)
   uv run python scripts/04_create_deployment_pipelines.py # + dp-hh-finance, dp-hh-operations (Phase 6)
   uv run python scripts/05_connect_git.py                 # + fabric/bi-finance, fabric/bi-operations (Phase 7)
   ```

✅ Admin portal › Domains shows Finance and Operations. There are fifteen workspaces, and each description says who it's for (`DEV - Hall Operations, Event Services, Rentals`). `hh-finance-dev` and `hh-operations-dev` show Source control connected.

### Part B — Data and sources (your computer, GitHub, Fabric)

1. Generate with the **same end date as your current data**, so Tessitura comes out byte-for-byte identical and only MIP and Diese are new (the date is `end` in `data/state.json`):
   ```powershell
   uv run python -m data_generator.generate full --end <end in data/state.json>
   ```
2. MIP: load it, then give it its own read-only login, connection and Copy job `cj_mip` (8.2b).
3. Diese: publish `data/diese_api` to its own GitHub Pages repo and set `DIESE_API_BASE_URL` in `.env` (8.2c).
4. Upload the config, now listing `mip` and `diese`: `uv run python scripts/06_upload_config.py --env dev` (8.0).
5. In `hh-dataplatform-dev`, add `cj_mip` to `pl_daily_load` (same connection and retry as `cj_tessitura`, **On success** → `nb_silver`), save, and **Commit** `cj_mip` and the pipeline (Phase 11). Then bring that commit down: `git checkout main; git pull; git checkout dev; git merge --no-ff main`.

✅ `HarmoniaMIP` has four tables, the Diese API's `index.json` lists `room`, `event` and `booking`, and `cj_mip` has run once.

### Part C — Gold, first run, security and models

1. **Gold (Phase 10):** in `wh_gold`, run `70_finance_and_venue_ops.sql`, then `75_marketing.sql`, then `80_source_freshness.sql`, then `40_load_facts.sql` again (its orchestrator calls the new procedures). 70 needs the two groups from Part A.
2. **Run `pl_daily_load`** with `load_date` blank, then check:
   ```sql
   SELECT procedure_name, rows_inserted, status, message FROM etl.load_log
   WHERE run_id = (SELECT TOP 1 run_id FROM etl.load_log ORDER BY started_at DESC) ORDER BY started_at;
   SELECT [status], COUNT(*) AS lines FROM fin.recon_revenue_to_gl GROUP BY [status];
   SELECT * FROM rpt.vw_finance_integrity;
   SELECT * FROM rpt.vw_source_freshness;
   ```
   ✅ Every step Succeeded. The reconciliation is mostly Matched or Within tolerance, with about 22 lines to Investigate, each a planted exception (see `data_generator/finance_ops.py`). No unbalanced journals.
3. **Access (Phase 12):**
   - `uv run python scripts/00_create_security_groups.py` (adds `sg-hh-data-science`; put only approved people in it).
   - `uv run python scripts/07_apply_onelake_security.py --env dev`: leaves exactly one role on `lh_silver`, DataScienceReaders.
   - Share `lh_silver` with `sg-hh-data-science` (Read only, no extra boxes), and `wh_gold` with the five analyst groups (Read only, no ReadData), then check with `uv run python scripts/09_verify_item_shares.py --env dev`.
4. **Models (Phase 13):** `sm_audience_development`, `sm_education_impact`, `sm_finance` in `hh-finance-dev` and `sm_operations` in `hh-operations-dev`, from `model.md`.

---

## Phase 15c — Add budget and cash to MIP

MIP now carries what finance needs for budget vs actual and a cash flow: an opening cash balance, biweekly payroll runs (every other Friday, `PAYROLL_PAYMENT`), payables paid 30 days after month end (`AP_PAYMENT`), and each year's adopted budget (`gl_budget`). Payments use their own journal numbers (`JS`/`GS`), so no existing ledger line changes, and their `updated_at` is the backfill time, so the Copy job and Silver pick them up without a reset.

1. **Regenerate** with the same end date as your data (`end` in `data/state.json`). Tessitura, Diese and the existing ledger lines come out identical:
   ```powershell
   uv run python -m data_generator.generate full --end <end in data/state.json>
   uv run python scripts/11_load_source_db.py --source mip_db --load-date <same date> --reload
   ```
   ✅ The loader shows `gl_account` 1 new (3100 Net Assets), `gl_transaction` ~248 new, `gl_budget` ~872 new.
2. **Sync:** commit and push as usual, then `hh-dataplatform-dev` › Source control › **Update all**. `cj_mip` gains a `gl_budget` table; `nb_silver` processes `mip.gl_budget`. Upload the config: `uv run python scripts/06_upload_config.py --env dev`.
3. **Gold:** in `wh_gold`, run `72_budget_and_cash.sql`, then `40_load_facts.sql` again.
4. **Run `pl_daily_load`** (`load_date` blank), then check:
   ```sql
   SELECT fiscal_year, SUM(budget_amount) AS budget FROM fin.fact_budget GROUP BY fiscal_year ORDER BY 1;
   SELECT TOP 12 * FROM rpt.vw_cash_flow_monthly ORDER BY month_start DESC;
   ```
   ✅ Four budget years; cash never goes below zero and ends around $30M.

---

## Phase 16 — Operate and govern

- **Tenant settings audit:** run `uv run python scripts/08_audit_tenant_settings.py` and commit `docs/tenant-settings-audit.md`.
- **Capacity Metrics app:** install it from AppSource and note CU for the pipeline run.
- **Activator:** add a rule on `dq.dq_results` (severity = error, failed_rows > 0) that sends an email or Teams message.
- **OneLake catalog › Govern tab:** screenshot it (ownership, labels, endorsement coverage).
- **Purview:** apply sensitivity labels if your tenant has them.

## Teardown

Run `uv run python scripts/99_teardown.py` to preview, then add `--confirm` to delete.
