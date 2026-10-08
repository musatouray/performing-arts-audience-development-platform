# Data pipelines: build spec

Pipelines are built in the **DEV Data Platform workspace** UI, then Git-synced into `fabric/de/` and promoted by deployment pipeline.

## pl_daily_load (runs the whole daily flow)

**Schedule:** daily at 05:00 America/New_York, so data is ready before the 9am stand-up.
**Parameter:** `load_date` (String, default empty = everything pending).

The four sources load side by side, because none of them depends on another. Silver waits for all four.

```
┌──────────────────────┐
│ cj_ticketing          │ Copy job          SQL Server (gateway) → lh_bronze.ticketing.*
├──────────────────────┤
│ df_education          │ Dataflow          SharePoint → lh_bronze.dbo.*      
├──────────────────────┤      ┌──────────────────────┐
│ nb_api                │ ───▶ │ nb_bronze             │ files (API + marketing shortcut)
│ nb_05_fundraising_api │  ✔   │ nb_10_bronze_ingest   │ → lh_bronze.fundraising.*, marketing.*
└──────────┬───────────┘      └──────────┬───────────┘
           │ all ✔                        │ ✔
           ▼                              ▼
    ┌────────────────────────┐    ┌──────────────────────────┐
    │ nb_silver               │──▶│ sp_load_gold              │
    │ nb_20_silver_transform  │ ✔ │ wh_gold.etl.usp_load_gold │
    └────────────────────────┘    └──────────────────────────┘

    sp_load_gold ✖ or skipped ──▶ notify_failure (Teams or Outlook) ──▶ fail_run (Fail)
    (if any earlier step fails, everything after it is skipped, so this one check covers the whole run)
```

| # | Activity | Type | Settings |
|---|---|---|---|
| 1 | `cj_ticketing` | Copy job | Copy job: `cj_ticketing`. Retry 2, interval 120s. |
| 2 | `df_education` | Dataflow | Dataflow: `df_education_sharepoint`. Retry 1. |
| 3 | `nb_api` | Notebook | Notebook: `nb_05_fundraising_api`. Base parameter `load_date` = `@pipeline().parameters.load_date`. Retry 2, interval 120s (the API can be busy). |
| 4 | `nb_bronze` | Notebook | Notebook: `nb_10_bronze_ingest`. Depends on 3 = **Succeeded**. Base parameter `load_date` as above. Retry 2. Timeout 1h. |
| 5 | `nb_silver` | Notebook | Notebook: `nb_20_silver_transform`. Depends on 1, 2 and 4 = **Succeeded**. Retry 1. |
| 6 | `sp_load_gold` | Stored procedure | Connection: `wh_gold` (same workspace). Proc: `etl.usp_load_gold`. Param `@run_id` (String) = `@pipeline().RunId`. Depends on 5 = **Succeeded**. |
| 7 | `notify_failure` | Teams (or Office 365 Outlook) | One arrow from 6, with **two** conditions ticked on it: **Failed** and **Skipped**. Message: `@concat('pl_daily_load failed. Run ID: ', pipeline().RunId)`. |
| 8 | `fail_run` | Fail | Depends on 7 = **Completed**. Message: `pl_daily_load failed, see the activity runs`. Error code: `500`. |

**Why the alert hangs off the last step, not every step.** When an activity has arrows from several activities, it waits for *all* of them (AND, not OR). So "one Failed arrow from each step" would only alert when every step failed at once, which never happens. Instead: a failure anywhere makes the steps after it *skip*, so `sp_load_gold` always ends up Failed or Skipped when something went wrong. Two conditions on one arrow work as OR.

**Why the Fail activity.** Once `notify_failure` has run fine, the pipeline would report **Succeeded**, because its last activity succeeded. `fail_run` sets the run back to Failed, so the Monitoring hub and anyone watching run history see the truth.

The marketing shortcut needs no activity: the files are already visible in `Files/landing/marketing`, and `nb_bronze` loads them.

**Why this shape?** Each tool does what it's best at, and the pipeline stays thin: it only orders the steps, retries and alerts. There's no business logic in it. Running the four sources side by side keeps the whole load short, and one slow source doesn't hold up the others' Bronze steps.

**Why no semantic-model refresh step?** Direct Lake picks up new Delta data automatically. With Import you'd add a *Semantic model refresh* activity here.

**Production variants to mention:**

- Use **Mirroring** for ticketing if you own the database (see ADR-003).
- Split into one child pipeline per source (**Invoke pipeline**) when the sources need different schedules.

## pl_weekly_maintenance

**Schedule:** Sunday at 03:00. It has one Notebook activity, `nb_90_maintenance`, which runs OPTIMIZE (V-Order) and VACUUM (7 days).

## Monitoring and alerting

- **Monitoring hub** gives run history for every pipeline, Copy job, Dataflow and notebook.
- **Activator** (Real-Time Intelligence): add a rule on `lh_silver.dq.dq_results` that alerts when `severity = 'error' AND failed_rows > 0` (email or Teams to the data owner named in `sources.yaml`).
- **Capacity Metrics app** shows CU use per item. Check it weekly and before resizing. Dataflows usually use the most CU per row, so watch `df_education_sharepoint` if the education data grows.
