/* =============================================================================
   wh_gold 80: how current is each source?
   One row per source system, answering the first question anyone asks of a report
   that replaced a cube: "how old is this number?"
     last_loaded_utc   when the platform last processed that system's data into Silver
     data_through      the latest business date Gold holds for it (last order, posting, booking...)
     freshness_status  Fresh if loaded within 26 hours (daily load plus slack), else Stale
   Every semantic model's Data Trust page shows it.
   ============================================================================= */

CREATE OR ALTER VIEW rpt.vw_source_freshness AS
WITH loads AS (
    -- Silver's run log: one row per table processed. The system is the part before the dot.
    SELECT LEFT(entity, CHARINDEX('.', entity + '.') - 1) AS source_system,
           MAX(ended_at) AS last_loaded_utc
    FROM [lh_silver].[audit].[run_log]
    WHERE stage = 'silver'
    GROUP BY LEFT(entity, CHARINDEX('.', entity + '.') - 1)
),
data_through AS (
    SELECT 'tessitura' AS source_system, 'Tessitura (ticketing, CRM, fundraising)' AS source_name,
           MAX(d.[date]) AS data_through, 'last ticket order' AS measured_by
    FROM fact.ticket_sales AS t JOIN dim.[date] AS d ON d.date_key = t.order_date_key WHERE t.order_date_key > 0
    UNION ALL
    SELECT 'mip', 'MIP Fund Accounting (general ledger)', MAX(d.[date]), 'last journal posting'
    FROM fin.fact_gl_entry AS g JOIN dim.[date] AS d ON d.date_key = g.effective_date_key WHERE g.effective_date_key > 0
    UNION ALL
    SELECT 'diese', 'Diese (hall bookings)', MAX(d.[date]), 'last completed event'
    FROM dim.event AS e JOIN dim.[date] AS d ON d.date_key = e.event_date_key WHERE e.[status] = 'Completed'
    UNION ALL
    SELECT 'education', 'Education team workbooks', MAX(d.[date]), 'last session'
    FROM fact.education_sessions AS s JOIN dim.[date] AS d ON d.date_key = s.session_date_key WHERE s.session_date_key > 0
)
SELECT dt.source_system, dt.source_name, l.last_loaded_utc, dt.data_through, dt.measured_by,
       DATEDIFF(hour, l.last_loaded_utc, SYSUTCDATETIME()) AS hours_since_load,
       CASE WHEN l.last_loaded_utc IS NULL THEN 'Never loaded'
            WHEN DATEDIFF(hour, l.last_loaded_utc, SYSUTCDATETIME()) <= 26 THEN 'Fresh'
            ELSE 'Stale' END AS freshness_status
FROM data_through AS dt
LEFT JOIN loads AS l ON l.source_system = dt.source_system;
GO

-- The same, saved as a table at the end of each Gold load, for the semantic models:
-- Direct Lake reads tables, not views. The models work out "hours since load" themselves.
CREATE TABLE rpt.source_freshness (
    source_system    varchar(20)   NOT NULL,
    source_name      varchar(100)  NULL,
    last_loaded_utc  datetime2(6)  NULL,
    data_through     date          NULL,
    measured_by      varchar(50)   NULL,
    snapshot_at      datetime2(6)  NOT NULL
);
GO

CREATE OR ALTER PROCEDURE etl.usp_snapshot_source_freshness @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @ins int;
    DELETE FROM rpt.source_freshness;
    INSERT INTO rpt.source_freshness
    SELECT source_system, source_name, CAST(last_loaded_utc AS datetime2(6)), data_through, measured_by,
           CAST(SYSUTCDATETIME() AS datetime2(6))
    FROM rpt.vw_source_freshness;
    SET @ins = @@ROWCOUNT;
    EXEC etl.usp_log @run_id, 'etl.usp_snapshot_source_freshness', 'rpt.source_freshness', @ins, 0, 0, 'Succeeded', NULL, @started;
END;
GO

GRANT SELECT ON OBJECT::rpt.vw_source_freshness TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_source_freshness TO [sg-hh-analysts-operations];
GO
