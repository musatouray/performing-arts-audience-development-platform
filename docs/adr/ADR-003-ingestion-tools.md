# ADR-003: Ingestion tool selection

**Status:** Accepted (revised: each source now lands through its own tool, instead of all four being simulated as files in `lh_bronze/Files/landing`).

**Rule of thumb:** *don't move data you can mirror or shortcut. Copy in bulk. Use code for APIs. Use low-code only where the business owns the logic.*

## Context

Harmonia Hall's data lives in four places, each with different owners, volumes and access rules:

- **Tessitura's database** (ticketing, CRM, constituents) is relational, usually hosted by the vendor. Hundreds of thousands of rows, a few hundred changes a day.
- **Tessitura's REST API** serves the fundraising side (campaigns, funds, contributions) a page at a time. The mock splits Tessitura this way to show both patterns; both land under one `tessitura` schema.
- **Education** records are Excel workbooks the program team keeps in SharePoint. A few thousand rows.
- **Marketing** exports (email and paid ads) are dropped daily into an Azure storage account the marketing team already owns.

## Decision

| Source | Lives in (this lab) | Tool | Lands in Bronze as | Why | Alternative rejected |
|---|---|---|---|---|---|
| Tessitura database | On-premises SQL Server 2022, schema `tix`, reached through the **on-premises data gateway** | **Copy job**, incremental on `updated_at`, append | `lh_bronze.tessitura.*` tables, typed | Built-in watermarking with nothing to maintain. Only needs a read-only login. The gateway connects outbound only, so no firewall port is opened. | **Mirroring** needs admin rights on the source server to turn on change tracking, which a vendor-hosted Tessitura doesn't give you. A **Dataflow** costs more capacity per GB at this volume. |
| Tessitura REST API | REST API with paging (mock on GitHub Pages) | **Notebook** `nb_05_api_ingest` | Raw records in `Files/landing/tessitura_api`, then `lh_bronze.tessitura.*` | Paging, retries on 429/5xx, record-count checks and auth all need code. Raw responses are kept, so a Bronze reload never calls the API again. | A **Copy activity** with the REST connector gets brittle with nested JSON, custom paging and OAuth. |
| MIP general ledger | On-premises SQL Server, database `HarmoniaMIP` | **Copy job** `cj_mip`, incremental, append, **its own read-only login** | `lh_bronze.mip.*` tables, typed | Same pattern as Tessitura: on-premises, read-only access, changes found by `updated_at`. A separate login because finance owns the ledger and must be able to revoke access to it alone. | A shared login with Tessitura: one secret fewer, but one leak exposes both systems. |
| Diese bookings | REST API with paging (mock on GitHub Pages) | **The same notebook** `nb_05_api_ingest` | Raw records in `Files/landing/diese_api`, then `lh_bronze.diese.*` | A second API source is a `sources.yaml` entry, not new code: the notebook reads every `notebook_api` source. | A copy of the notebook per API: twice the code to maintain and to fix. |
| Education | Excel in SharePoint | **Dataflow Gen2** `df_education_sharepoint` | `lh_bronze.dbo.*` tables, replaced each run (Dataflow Gen2 can't choose a schema yet) | Small, and the clean-up rules belong to the business. The analyst can read and change Power Query. | A **notebook** would make IT the bottleneck for a spreadsheet. |
| Marketing | ADLS Gen2 container `marketing-exports` | **OneLake shortcut** `Files/landing/marketing` | Read in place, then `lh_bronze.marketing.*` | Zero copy and zero pipeline. The marketing team keeps owning its storage. | **Copying** the files would store them twice and add a step that can fail. |

Specs: [`src/ingestion/`](../../src/ingestion/README.md). Settings per source: the `ingestion` block in [`config/sources.yaml`](../../config/sources.yaml).

Two kinds of Bronze come out of this, and Silver handles both:

- **File sources** (Tessitura API, Diese API, marketing) land as files, and `nb_10` loads them as text with lineage columns and checks the row counts against a manifest. Silver picks up new rows by `_load_date`.
- **Table sources** (Tessitura database, MIP, education) are written straight into Bronze by the tool. Silver picks up new Tessitura and MIP rows by `updated_at`, and re-reads the small education tables in full.

## Consequences

- **Four tools to monitor instead of one.** All four run from `pl_daily_load`, so failures still surface in one place, with one alert.
- **Typed Bronze for database sources.** Data from a database already has reliable types, so there's nothing to protect by storing it as text. File sources still land as text.
- **Credentials live in Fabric connections**, not in code. Copy jobs, notebooks and pipelines can run as a workspace identity or service principal, so no person's account is involved.
- **The Dataflow is the exception: it always runs as a user.** Dataflow Gen2 needs a user as its owner, and its Lakehouse destination only accepts an organizational account; service principals and workspace identities aren't supported there yet. We accept this for education because the business owning its Power Query rules matters more here. To limit the risk, the Dataflow is owned by a service account, not a person: `svc-fabric-dataflows-nonprod` in DEV and TEST, `svc-fabric-dataflows-prod` in PROD. Each sits only in its own group (`sg-hh-svc-dataflows-nonprod` / `-prod`), which has Read on the one SharePoint site and Contributor on its Data Platform workspaces, nothing else. Two accounts rather than one because engineers sign in as the non-prod account day to day; a single account would let them write to prod outside the deployment pipeline. Two rather than three because a separate test account adds admin work without protecting anything that matters.
- **Each environment needs its own connections.** Dev, test and prod each point at their own source (or the same source, read-only, in this lab).

> [!NOTE]
> *"The tool follows the source. Tessitura's database is vendor-hosted and I only get read access, so it's an incremental Copy job on `updated_at`. Its REST API is paged, so it's a notebook that handles paging and retries and keeps the raw responses. Education is a few Excel files the team owns, so it's a Dataflow they can maintain. Marketing exports already sit in ADLS, so a shortcut reads them in place with no copy at all."*

**Revisit when:**

- We get admin rights on the ticketing database, or move to a Tessitura version that supports Mirroring. Switch to **Mirroring** for near-real-time data.
- Real-time door scans at the venue are needed. Use **Eventstream → Eventhouse**.
- Tessitura offers webhooks or a bulk export. Replace polling with events or a file drop.
- Dataflow Gen2 supports a service principal or workspace identity for Lakehouse destinations. Move `df_education_sharepoint` to the workspace identity. If running without any user becomes a hard requirement first, replace the Dataflow with a notebook that reads the workbooks through Microsoft Graph as the workspace identity (`scripts/12` already grants it read access to the site), landing files in `Files/landing/education` for `nb_10`.
