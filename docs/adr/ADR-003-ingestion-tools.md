# ADR-003: Ingestion tool selection

**Status:** Accepted (revised: each source now lands through its own tool, instead of all four being simulated as files in `lh_bronze/Files/landing`).

**Rule of thumb:** *don't move data you can mirror or shortcut. Copy in bulk. Use code for APIs. Use low-code only where the business owns the logic.*

## Context

Harmonia Hall's data lives in four places, each with different owners, volumes and access rules:

- **Ticketing** (Tessitura-style) is a relational database, usually hosted by the vendor. Hundreds of thousands of rows, a few hundred changes a day.
- **Fundraising** is a SaaS product. The only way in is its REST API, which returns data a page at a time.
- **Education** records are Excel workbooks the program team keeps in SharePoint. A few thousand rows.
- **Marketing** exports (email and paid ads) are dropped daily into an Azure storage account the marketing team already owns.

## Decision

| Source | Lives in (this lab) | Tool | Lands in Bronze as | Why | Alternative rejected |
|---|---|---|---|---|---|
| Ticketing | On-premises SQL Server 2022, schema `tix`, reached through the **on-premises data gateway** | **Copy job**, incremental on `updated_at`, append | `lh_bronze.ticketing.*` tables, typed | Built-in watermarking with nothing to maintain. Only needs a read-only login. The gateway connects outbound only, so no firewall port is opened. | **Mirroring** needs admin rights on the source server to turn on change tracking, which a vendor-hosted Tessitura doesn't give you. A **Dataflow** costs more capacity per GB at this volume. |
| Fundraising | REST API with paging (mock on GitHub Pages) | **Notebook** `nb_05_fundraising_api` | Raw records in `Files/landing/fundraising`, then `lh_bronze.fundraising.*` | Paging, retries on 429/5xx, record-count checks and auth all need code. Raw responses are kept, so a Bronze reload never calls the API again. | A **Copy activity** with the REST connector gets brittle with nested JSON, custom paging and OAuth. |
| Education | Excel in SharePoint | **Dataflow Gen2** `df_education_sharepoint` | `lh_bronze.dbo.*` tables, replaced each run (Dataflow Gen2 can't choose a schema yet) | Small, and the clean-up rules belong to the business. The analyst can read and change Power Query. | A **notebook** would make IT the bottleneck for a spreadsheet. |
| Marketing | ADLS Gen2 container `marketing-exports` | **OneLake shortcut** `Files/landing/marketing` | Read in place, then `lh_bronze.marketing.*` | Zero copy and zero pipeline. The marketing team keeps owning its storage. | **Copying** the files would store them twice and add a step that can fail. |

Specs: [`src/ingestion/`](../../src/ingestion/README.md). Settings per source: the `ingestion` block in [`config/sources.yaml`](../../config/sources.yaml).

Two kinds of Bronze come out of this, and Silver handles both:

- **File sources** (fundraising, marketing) land as files, and `nb_10` loads them as text with lineage columns and checks the row counts against a manifest. Silver picks up new rows by `_load_date`.
- **Table sources** (ticketing, education) are written straight into Bronze by the tool. Silver picks up new ticketing rows by `updated_at`, and re-reads the small education tables in full.

## Consequences

- **Four tools to monitor instead of one.** All four run from `pl_daily_load`, so failures still surface in one place, with one alert.
- **Typed Bronze for database sources.** Data from a database already has reliable types, so there's nothing to protect by storing it as text. File sources still land as text.
- **Credentials live in Fabric connections**, not in code. In this lab they use an organizational account. In production they'd use a service principal or workspace identity, with secrets in Key Vault.
- **Each environment needs its own connections.** Dev, test and prod each point at their own source (or the same source, read-only, in this lab).

> [!NOTE]
> *"The tool follows the source. Ticketing is a vendor-hosted database where I only get read access, so it's an incremental Copy job on `updated_at`. Fundraising is a SaaS API, so it's a notebook that handles paging and retries and keeps the raw responses. Education is a few Excel files the team owns, so it's a Dataflow they can maintain. Marketing exports already sit in ADLS, so a shortcut reads them in place with no copy at all."*

**Revisit when:**

- We get admin rights on the ticketing database, or move to a Tessitura version that supports Mirroring. Switch to **Mirroring** for near-real-time data.
- Real-time door scans at the venue are needed. Use **Eventstream → Eventhouse**.
- The fundraising vendor offers webhooks or a bulk export. Replace polling with events or a file drop.
