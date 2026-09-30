# Data pipelines: build spec

Pipelines are built in the **DEV Data Platform workspace** UI (the practice counts in an interview), then Git-synced into `fabric/de/` and promoted by deployment pipeline.

## pl_daily_load (orchestrates the medallion flow)

**Schedule:** daily at 05:00 America/New_York, after the ticketing extract lands, so data is ready before the 9am stand-up.
**Parameter:** `load_date` (String, default empty = everything pending).

```
┌─────────────────────┐    ┌──────────────────────┐    ┌────────────────────────┐    ┌──────────────────┐
│ nb_bronze            │──▶│ nb_silver             │──▶│ sp_load_gold            │──▶│ (success) done    │
│ Notebook activity    │ ✔ │ Notebook activity     │ ✔ │ Stored procedure act.   │    └──────────────────┘
│ nb_10_bronze_ingest  │    │ nb_20_silver_transform│    │ wh_gold.etl.usp_load_gold│
└─────────┬───────────┘    └─────────┬────────────┘    └──────────┬─────────────┘
          │ ✖ on failure              │ ✖                            │ ✖
          └────────────────┬──────────┴──────────────────────────────┘
                           ▼
                ┌─────────────────────────┐
                │ notify_failure           │  Teams activity (or Office 365 Outlook)
                │ "pl_daily_load failed"   │  → #data-platform-alerts channel
                └─────────────────────────┘
```

| # | Activity | Type | Settings |
|---|---|---|---|
| 1 | `nb_bronze` | Notebook | Notebook: `nb_10_bronze_ingest`. Base parameter `load_date` = `@pipeline().parameters.load_date`. Retry **2**, interval 120s (transient Spark or OneLake errors). Timeout 1h. |
| 2 | `nb_silver` | Notebook | Notebook: `nb_20_silver_transform`. Depends on 1 = **Succeeded**. Retry 1. |
| 3 | `sp_load_gold` | Stored procedure | Connection: `wh_gold` (Fabric Warehouse, same workspace). Proc: `etl.usp_load_gold`. Param `@run_id` (String) = `@pipeline().RunId`. Depends on 2 = **Succeeded**. |
| 4 | `notify_failure` | Teams (or Office 365 Outlook) | Depends on 1, 2, 3 = **Failed** (one arrow from each). Message: `@concat('pl_daily_load failed: ', pipeline().RunId, ' in ', pipeline().DataFactory)`. |

**Why Notebook → Notebook → Stored procedure?** Each engine does what it's best at. Spark handles files, schema drift and heavy transforms (Bronze and Silver). T-SQL handles dimensional modeling, which the four-person BI team can read and maintain (Gold). The pipeline itself stays thin: orchestration, retries and alerts, with no business logic.

**Why no semantic-model refresh step?** Direct Lake reframes automatically when the Delta tables change. With Import you'd add a *Semantic model refresh* activity here.

**Production variants to mention:**

- A **Copy job / Copy activity** in front of step 1 lands the ticketing DB extract. Use **Mirroring** instead if the source DB is supported.
- A **Dataflow Gen2** owned by the Education analyst lands the education spreadsheet from SharePoint.
- Use an **Invoke pipeline** activity to split ingestion per source when schedules differ.

## pl_weekly_maintenance

**Schedule:** Sunday at 03:00. It has one Notebook activity, `nb_90_maintenance`, which runs OPTIMIZE (V-Order) and VACUUM (7 days).

## Monitoring and alerting

- **Monitoring hub** gives run history for every pipeline and notebook.
- **Activator** (Real-Time Intelligence): add a rule on `lh_silver.dq.dq_results` that alerts when `severity = 'error' AND failed_rows > 0` (email or Teams to the data owner named in `sources.yaml`).
- **Capacity Metrics app** shows CU consumption per item. Check it weekly and before resizing.
