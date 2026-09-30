# ADR-002: Ingestion tool selection

**Rule of thumb:** *don't move data you can mirror or shortcut. Copy in bulk. Use code for APIs. Use low-code only where the business owns the logic.*

| Source | Pattern chosen | Why | Alternative rejected |
|---|---|---|---|
| Ticketing / CRM database (Tessitura-style) | **Mirroring** if the DB engine is supported; otherwise a **Copy job** (incremental on `updated_at`) into `Files/landing` | Near-real-time with no pipeline to maintain; Copy job handles watermarks natively | A Dataflow Gen2 costs more CU per GB at this volume |
| Fundraising SaaS (REST API) | **Notebook** (paging, OAuth, retries, schema drift) | Needs code: pagination and error handling | Copy activity's REST connector gets brittle with nested JSON and custom auth |
| Education spreadsheet (SharePoint) | **Dataflow Gen2** owned by the Education analyst | Low volume; the business owns the logic; a self-service win | A notebook would make IT a bottleneck for a spreadsheet |
| Data already in ADLS/S3 (e.g. marketing exports) | **Shortcut** | Zero copy, zero pipeline | Copying duplicates storage and adds latency |

In this repo, all three sources are simulated as files landed in `lh_bronze/Files/landing` (see `data_generator/`). Everything downstream of landing is identical to production.

**Say it in 30 seconds:** "The tool follows the source. Mirroring or a shortcut if I can avoid moving data, Copy for bulk, a notebook when it needs code, and a Dataflow when the business owns the logic."

**Revisit when:** volumes or latency needs change. For example, real-time door scans at the venue would go to **Eventstream → Eventhouse**.
