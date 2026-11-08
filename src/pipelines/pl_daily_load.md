# Data pipelines: build spec

Pipelines are built in the **DEV Data Platform workspace** UI, then Git-synced into `fabric/de/` and promoted by deployment pipeline.

## pl_daily_load (runs the whole daily flow)

**Schedule:** PROD only, daily at 07:00 America/New_York (the gateway's computer is always on); DEV and TEST run on demand. Schedules don't travel with deployments.
**Parameter:** `load_date` (String, default empty = everything pending).

The sources load side by side, because none of them depends on another. Silver waits for all of them.

```
┌──────────────────────┐
│ cj_tessitura          │ Copy job          SQL Server (gateway) → lh_bronze.tessitura.*
├──────────────────────┤
│ cj_mip                │ Copy job          SQL Server (gateway) → lh_bronze.mip.*
├──────────────────────┤
│ df_education          │ Dataflow          SharePoint → lh_bronze.dbo.*
├──────────────────────┤      ┌──────────────────────┐
│ nb_api                │ ───▶ │ nb_bronze             │ files (APIs + marketing shortcut)
│ nb_05_api_ingest      │  ✔   │ nb_10_bronze_ingest   │ → lh_bronze.tessitura.*, diese.*, marketing.*
└──────────┬───────────┘      └──────────┬───────────┘
           │ all ✔                        │ ✔
           ▼                              ▼
    ┌────────────────────────┐    ┌──────────────────────────┐    ┌────────────────────┐
    │ nb_silver               │──▶│ sp_load_gold              │──▶│ refresh_sm_finance  │
    │ nb_20_silver_transform  │ ✔ │ wh_gold.etl.usp_load_gold │ ✔ │ semantic model      │
    └────────────────────────┘    └──────────────────────────┘    └────────────────────┘

    refresh_sm_finance ✖ or skipped ──▶ notify_failure (Teams or Outlook) ──▶ fail_run (Fail)
    (if any earlier step fails, everything after it is skipped, so this one check covers the whole run)
```

| # | Activity | Type | Settings |
|---|---|---|---|
| 1 | `cj_tessitura` | Copy job | Copy job: `cj_tessitura`. Retry 2, interval 120s. |
| 1b | `cj_mip` | Copy job | Copy job: `cj_mip` (the ledger). Same connection and retry as `cj_tessitura`; runs in parallel with it. `nb_silver` depends on it. |
| 2 | `df_education` | Dataflow | Dataflow: `df_education_sharepoint`. Retry 1. |
| 3 | `nb_api` | Notebook | Notebook: `nb_05_api_ingest`. Base parameter `load_date` = `@pipeline().parameters.load_date`. Retry 2, interval 120s (the API can be busy). |
| 4 | `nb_bronze` | Notebook | Notebook: `nb_10_bronze_ingest`. Depends on 3 = **Succeeded**. Base parameter `load_date` as above. Retry 2. Timeout 1h. |
| 5 | `nb_silver` | Notebook | Notebook: `nb_20_silver_transform`. Depends on 1, 2 and 4 = **Succeeded**. Retry 1. |
| 6 | `sp_load_gold` | Stored procedure | Connection: dynamic, from the library variables `vl_platform_wh_gold_connection`, `vl_platform_workspace_id`, `vl_platform_wh_gold_id` and `vl_platform_wh_gold_endpoint`, so each stage loads its own `wh_gold`. Proc: `[etl].[usp_load_gold]` (typed in). Param `@run_id` (String) = `@pipeline().RunId`. Retry 2, every 180 s (Silver's SQL endpoint can briefly report error 952 after a new table). Depends on 5 = **Succeeded**. |
| 7 | `refresh_sm_finance` | Semantic model refresh | Connection, workspace and model: dynamic, from `vl_platform_sm_finance_connection`, `vl_platform_finance_workspace_id` and `vl_platform_sm_finance_id`, so each stage refreshes its own `sm_finance`. Wait on completion; refresh type Full (re-points Direct Lake at the new data and recalculates the calculated tables). Retry 1, after 300 s. Depends on 6 = **Succeeded**. |
| 8 | `notify_failure` | Teams (or Office 365 Outlook) | One arrow from 7, with **two** conditions ticked on it: **Failed** and **Skipped**. Message: `@concat('pl_daily_load failed. Run ID: ', pipeline().RunId)`. |
| 9 | `fail_run` | Fail | Depends on 8 = **Completed**. Message: `pl_daily_load failed, see the activity runs`. Error code: `500`. |

**Why the alert hangs off the last step, not every step.** When an activity has arrows from several activities, it waits for *all* of them (AND, not OR). So "one Failed arrow from each step" would only alert when every step failed at once, which never happens. Instead: a failure anywhere makes the steps after it *skip*, so `refresh_sm_finance`, the last step, always ends up Failed or Skipped when something went wrong. Two conditions on one arrow work as OR.

**Why the Fail activity.** Once `notify_failure` has run fine, the pipeline would report **Succeeded**, because its last activity succeeded. `fail_run` sets the run back to Failed, so the Monitoring hub and anyone watching run history see the truth.

The marketing shortcut needs no activity: the files are already visible in `Files/landing/marketing`, and `nb_bronze` loads them.

**Why this shape?** Each tool does what it's best at, and the pipeline stays thin: it only orders the steps, retries and alerts. There's no business logic in it. Running the four sources side by side keeps the whole load short, and one slow source doesn't hold up the others' Bronze steps.

**Why a semantic-model refresh step, when Direct Lake updates itself?** In TEST and PROD, *Keep your Direct Lake data up to date* is **off**, and the pipeline refreshes the model once, after Gold has fully loaded. Users never see a load half-way (Gold commits in several steps), and a failed refresh fails the run and alerts, where automatic updates would quietly suspend. DEV keeps automatic updates on, so changes show immediately. Each new model (audience, operations) gets its own refresh activity in parallel after `sp_load_gold`, with its own workspace and model variables.

**Production variants to mention:**

- Use **Mirroring** for ticketing if you own the database (see ADR-003).
- Split into one child pipeline per source (**Invoke pipeline**) when the sources need different schedules.

## pl_weekly_maintenance

**Schedule:** Sunday at 03:00. It has one Notebook activity, `nb_90_maintenance`, which runs OPTIMIZE (V-Order) and VACUUM (7 days).

## Monitoring and alerting

- **Monitoring hub** gives run history for every pipeline, Copy job, Dataflow and notebook.
- **Activator** (Real-Time Intelligence): add a rule on `lh_silver.dq.dq_results` that alerts when `severity = 'error' AND failed_rows > 0` (email or Teams to the data owner named in `sources.yaml`).
- **Capacity Metrics app** shows CU use per item. Check it weekly and before resizing. Dataflows usually use the most CU per row, so watch `df_education_sharepoint` if the education data grows.
