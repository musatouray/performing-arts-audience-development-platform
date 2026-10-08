-- ---------------------------------------------------------------------------
-- Data quality and load status: can today's numbers be trusted?
-- ---------------------------------------------------------------------------
CREATE   VIEW rpt.vw_dq_latest AS
SELECT r.entity, r.[rule], r.column_name, r.severity, r.failed_rows, r.total_rows, r.pass_rate, r.checked_at
FROM [lh_silver].[dq].[dq_results] AS r
WHERE r.run_id = (SELECT TOP 1 run_id FROM [lh_silver].[dq].[dq_results] ORDER BY checked_at DESC);

GO