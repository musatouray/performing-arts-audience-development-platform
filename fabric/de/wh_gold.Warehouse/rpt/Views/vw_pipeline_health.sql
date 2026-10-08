CREATE   VIEW rpt.vw_pipeline_health AS
SELECT 'gold' AS layer, procedure_name AS step, target_table AS entity, rows_inserted AS rows_out,
       status, message, started_at, ended_at
FROM etl.load_log
UNION ALL
SELECT stage, notebook, entity, rows_out, status, message, started_at, ended_at
FROM [lh_bronze].[audit].[run_log]       -- API and Bronze steps log to Bronze
UNION ALL
SELECT stage, notebook, entity, rows_out, status, message, started_at, ended_at
FROM [lh_silver].[audit].[run_log];      -- Silver steps log to Silver

GO