# How each source reaches Bronze

Six source systems, four landing patterns. A new source reuses a pattern: MIP is a second Copy job, Diese is one more entry for the same API notebook. The tool follows the source (see [ADR-003](../../docs/adr/ADR-003-ingestion-tools.md)).

| Source | Lives in | Tool | Lands in | Built by |
|---|---|---|---|---|
| Tessitura database | On-premises SQL Server, schema `tix`, via the on-premises data gateway | **Copy job** `cj_tessitura`, incremental on `updated_at` | `lh_bronze.tessitura.<table>` (appended) | Fabric UI, see [copy_job_tessitura.md](copy_job_tessitura.md) |
| Tessitura REST API | REST API with paging (mock on GitHub Pages) | **Notebook** `nb_05_api_ingest` | `Files/landing/tessitura_api/` → nb_10 → `lh_bronze.tessitura.<table>` | Imported notebook |
| MIP general ledger | On-premises SQL Server, database `HarmoniaMIP`, schema `dbo`, via the gateway | **Copy job** `cj_mip`, incremental on `updated_at`, its own read-only login | `lh_bronze.mip.<table>` (appended) | Fabric UI, see [copy_job_mip.md](copy_job_mip.md) |
| Diese bookings | REST API with paging (mock on GitHub Pages) | **Same notebook** `nb_05_api_ingest` (config only) | `Files/landing/diese_api/` → nb_10 → `lh_bronze.diese.<table>` | `sources.yaml` entry |
| Education programs | Excel workbooks in SharePoint | **Dataflow Gen2** `df_education_sharepoint` | `lh_bronze.dbo.<table>` (replaced each run) | Fabric UI, see [dataflow_education.md](dataflow_education.md) |
| Marketing exports | ADLS Gen2 container `marketing-exports` | **Shortcut** `Files/landing/marketing` | read in place → nb_10 → `lh_bronze.marketing.<table>` | `scripts/10_create_shortcuts.py` |

Everything after Bronze is the same for all of them: `nb_20_silver_transform` cleans, de-duplicates and checks the data, then Gold is built from Silver.

## What each pattern shows

- **Copy job:** built-in watermarking. You pick the column, Fabric remembers how far it got. There's no pipeline logic to maintain. Appending every changed row gives Bronze a full change history.
- **Notebook for an API:** paging, retries on 429/5xx, and checking the record count the API reports. Raw records land as files first, so a failed Bronze load never means calling the API again.
- **Dataflow Gen2:** low-code, so the business can own the logic (renames, Yes/No to true/false). It fits a small source; it would be the wrong tool for millions of rows.
- **Shortcut:** zero copy. The files stay in the marketing team's storage account and Fabric reads them in place. Access goes through a Fabric connection to the storage account.
