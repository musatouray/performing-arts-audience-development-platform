/* =============================================================================
   wh_gold 80: how current is each source?
   One row per source system, answering the first question anyone asks of a report
   that replaced a cube: "how old is this number?"
     last_loaded_utc   when the platform last confirmed that system's data in Silver is current
                       (a run that found nothing new counts: the source was checked)
     data_through      the latest business date Gold holds for it (last order, posting, booking...)
     freshness_status  Fresh within the source's expected refresh (sources.yaml: daily = 26 hours,
                       weekly = 8 days), else Stale
   Every semantic model's Data Trust page shows it.
   ============================================================================= */

CREATE   VIEW rpt.vw_source_freshness AS
WITH loads AS (
    -- Silver's run log: one row per table processed. The system is the part before the dot.
    SELECT LEFT(entity, CHARINDEX('.', entity + '.') - 1) AS source_system,
           MAX(ended_at) AS last_loaded_utc
    FROM [lh_silver].[audit].[run_log]
    WHERE stage = 'silver' AND [status] = 'Succeeded'      -- includes "checked, nothing new"; not failures or skips
    GROUP BY LEFT(entity, CHARINDEX('.', entity + '.') - 1)
),
expected AS (
    -- How often each system should refresh, from sources.yaml (written to Silver by nb_20).
    SELECT source_system, MAX(expected_refresh) AS expected_refresh, MIN(sla_hours) AS sla_hours
    FROM [lh_silver].[audit].[source_config]
    GROUP BY source_system
),
data_through AS (
    SELECT 'tessitura' AS source_system, 'Tessitura' AS source_label, 'Tessitura (ticketing, CRM, fundraising)' AS source_name,
           MAX(d.[date]) AS data_through, 'last ticket order' AS measured_by
    FROM fact.ticket_sales AS t JOIN dim.[date] AS d ON d.date_key = t.order_date_key WHERE t.order_date_key > 0
    UNION ALL
    SELECT 'mip', 'MIP', 'MIP Fund Accounting (general ledger)', MAX(d.[date]), 'last journal posting'
    FROM fin.fact_gl_entry AS g JOIN dim.[date] AS d ON d.date_key = g.effective_date_key WHERE g.effective_date_key > 0
    UNION ALL
    SELECT 'diese', 'Diese', 'Diese (hall bookings)', MAX(d.[date]), 'last completed event'
    FROM dim.event AS e JOIN dim.[date] AS d ON d.date_key = e.event_date_key WHERE e.[status] = 'Completed'
    UNION ALL
    SELECT 'marketing', 'Marketing', 'Email and ad platforms', MAX(d.[date]), 'last day of ad spend'
    FROM fact.ad_spend_daily AS a JOIN dim.[date] AS d ON d.date_key = a.ad_date_key WHERE a.ad_date_key > 0
    UNION ALL
    SELECT 'education', 'Education', 'Education team workbooks', MAX(d.[date]), 'last session'
    FROM fact.education_sessions AS s JOIN dim.[date] AS d ON d.date_key = s.session_date_key WHERE s.session_date_key > 0
)
SELECT dt.source_system, dt.source_label, dt.source_name, l.last_loaded_utc,
       CAST(l.last_loaded_utc AT TIME ZONE 'UTC' AT TIME ZONE 'Eastern Standard Time' AS datetime2(0)) AS last_loaded_et,
       dt.data_through, dt.measured_by,
       ISNULL(e.expected_refresh, 'daily') AS expected_refresh, ISNULL(e.sla_hours, 26) AS sla_hours,
       DATEDIFF(hour, l.last_loaded_utc, SYSUTCDATETIME()) AS hours_since_load,
       CASE WHEN l.last_loaded_utc IS NULL THEN 'Never loaded'
            WHEN DATEDIFF(hour, l.last_loaded_utc, SYSUTCDATETIME()) <= ISNULL(e.sla_hours, 26) THEN 'Fresh'
            ELSE 'Stale' END AS freshness_status
FROM data_through AS dt
LEFT JOIN loads AS l ON l.source_system = dt.source_system
LEFT JOIN expected AS e ON e.source_system = dt.source_system;

GO