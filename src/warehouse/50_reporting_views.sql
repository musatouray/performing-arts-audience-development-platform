/* =============================================================================
   wh_gold 50: reporting views for people who use SQL or paginated reports
   Most people use the Power BI reports. These views use the same definitions
   (sell-through, lapsed donors, renewals) so the numbers match.
   People are counted by patron_id. patron_key can't be used because one person
   can have several rows when their address changes.
   ============================================================================= */

-- Sell-through per performance (tickets sold vs capacity), excluding returns.
CREATE OR ALTER VIEW rpt.vw_performance_sell_through AS
SELECT p.performance_id, p.title, p.series, p.genre, p.season_name, p.fiscal_year, p.venue_name,
       p.performance_datetime, p.day_part, p.capacity, p.[status],
       SUM(CASE WHEN s.is_returned = 0 THEN s.quantity ELSE 0 END)                        AS tickets_sold,
       SUM(CASE WHEN s.is_returned = 0 AND s.is_comp = 1 THEN s.quantity ELSE 0 END)      AS comps,
       SUM(CASE WHEN s.is_returned = 0 THEN s.net_amount ELSE 0 END)                      AS net_revenue,
       CAST(SUM(CASE WHEN s.is_returned = 0 THEN s.quantity ELSE 0 END) AS decimal(12,4))
           / NULLIF(p.capacity, 0)                                                        AS sell_through_pct,
       CAST(SUM(CASE WHEN s.is_returned = 0 THEN s.net_amount ELSE 0 END) AS decimal(14,2))
           / NULLIF(p.capacity, 0)                                                        AS revenue_per_available_seat
FROM dim.performance AS p
LEFT JOIN fact.ticket_sales AS s ON s.performance_key = p.performance_key
WHERE p.performance_key > 0
GROUP BY p.performance_id, p.title, p.series, p.genre, p.season_name, p.fiscal_year, p.venue_name,
         p.performance_datetime, p.day_part, p.capacity, p.[status];
GO

-- Each donor's status per fiscal year: New, Retained, Reactivated, LYBUNT or SYBUNT.
--   LYBUNT = gave Last Year But Unfortunately Not This year
--   SYBUNT = gave Some Year (before last) But Unfortunately Not This year
CREATE OR ALTER VIEW rpt.vw_donor_status_by_fy AS
WITH giving AS (
    SELECT dp.patron_id, d.fiscal_year, SUM(g.amount) AS amount
    FROM fact.gifts AS g
    JOIN dim.[date]  AS d  ON d.date_key = g.gift_date_key
    JOIN dim.patron  AS dp ON dp.patron_key = g.patron_key
    WHERE g.patron_key > 0 AND g.amount > 0
    GROUP BY dp.patron_id, d.fiscal_year
),
years AS (SELECT DISTINCT fiscal_year FROM giving),
flags AS (
    SELECT y.fiscal_year, g.patron_id,
           MAX(CASE WHEN g.fiscal_year = y.fiscal_year     THEN 1 ELSE 0 END) AS gave_this_year,
           MAX(CASE WHEN g.fiscal_year = y.fiscal_year - 1 THEN 1 ELSE 0 END) AS gave_last_year,
           MAX(CASE WHEN g.fiscal_year < y.fiscal_year - 1 THEN 1 ELSE 0 END) AS gave_earlier,
           SUM(CASE WHEN g.fiscal_year = y.fiscal_year     THEN g.amount ELSE 0 END) AS amount_this_year,
           SUM(CASE WHEN g.fiscal_year = y.fiscal_year - 1 THEN g.amount ELSE 0 END) AS amount_last_year
    FROM years AS y
    JOIN giving AS g ON g.fiscal_year <= y.fiscal_year
    GROUP BY y.fiscal_year, g.patron_id
)
SELECT fiscal_year, patron_id, amount_this_year, amount_last_year,
       CASE WHEN gave_this_year = 1 AND gave_last_year = 1 THEN 'Retained'
            WHEN gave_this_year = 1 AND gave_earlier = 1   THEN 'Reactivated'
            WHEN gave_this_year = 1                        THEN 'New'
            WHEN gave_last_year = 1                        THEN 'LYBUNT'
            ELSE 'SYBUNT' END AS donor_status
FROM flags;
GO

-- Donor retention by fiscal year: donors who gave again / donors last year.
CREATE OR ALTER VIEW rpt.vw_donor_retention AS
SELECT fiscal_year,
       SUM(CASE WHEN donor_status = 'Retained' THEN 1 ELSE 0 END)                        AS retained_donors,
       SUM(CASE WHEN donor_status IN ('Retained', 'LYBUNT') THEN 1 ELSE 0 END)           AS donors_last_year,
       SUM(CASE WHEN donor_status = 'LYBUNT' THEN 1 ELSE 0 END)                          AS lybunt_donors,
       SUM(CASE WHEN donor_status = 'LYBUNT' THEN amount_last_year ELSE 0 END)           AS lybunt_revenue_at_risk,
       CAST(SUM(CASE WHEN donor_status = 'Retained' THEN 1 ELSE 0 END) AS decimal(12,4))
         / NULLIF(SUM(CASE WHEN donor_status IN ('Retained', 'LYBUNT') THEN 1 ELSE 0 END), 0) AS donor_retention_rate
FROM rpt.vw_donor_status_by_fy
GROUP BY fiscal_year;
GO

-- Subscriber renewal by season: subscribers who renewed / last season's subscribers.
CREATE OR ALTER VIEW rpt.vw_subscriber_renewal AS
WITH subs AS (
    SELECT DISTINCT s.fiscal_year, dp.patron_id, s.is_renewal
    FROM fact.subscriptions AS s JOIN dim.patron AS dp ON dp.patron_key = s.patron_key
    WHERE s.patron_key > 0
),
per_year AS (
    SELECT fiscal_year, COUNT(DISTINCT patron_id) AS subscribers,
           COUNT(DISTINCT CASE WHEN is_renewal = 1 THEN patron_id END) AS renewing_subscribers
    FROM subs GROUP BY fiscal_year
)
SELECT cur.fiscal_year, cur.subscribers, cur.renewing_subscribers, prev.subscribers AS prior_year_subscribers,
       CAST(cur.renewing_subscribers AS decimal(12,4)) / NULLIF(prev.subscribers, 0) AS renewal_rate
FROM per_year AS cur
LEFT JOIN per_year AS prev ON prev.fiscal_year = cur.fiscal_year - 1;
GO

-- Education reach, for grant and board reports. Counts only, no student details.
CREATE OR ALTER VIEW rpt.vw_education_impact AS
SELECT d.fiscal_year, pr.program_type, pr.program_name, sc.borough,
       CAST(ISNULL(sc.is_title_i, 0) AS bit) AS is_title_i_school,
       COUNT(*)                          AS sessions,
       SUM(e.participants)               AS participant_touchpoints,
       SUM(e.teaching_artist_hours)      AS teaching_artist_hours,
       COUNT(DISTINCT e.school_key)      AS schools_served
FROM fact.education_sessions AS e
JOIN dim.[date]   AS d  ON d.date_key = e.session_date_key
JOIN dim.program  AS pr ON pr.program_key = e.program_key
JOIN dim.school   AS sc ON sc.school_key = e.school_key
GROUP BY d.fiscal_year, pr.program_type, pr.program_name, sc.borough, CAST(ISNULL(sc.is_title_i, 0) AS bit);
GO

-- ---------------------------------------------------------------------------
-- Data quality and load status: can today's numbers be trusted?
-- ---------------------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_dq_latest AS
SELECT r.entity, r.[rule], r.column_name, r.severity, r.failed_rows, r.total_rows, r.pass_rate, r.checked_at
FROM [lh_silver].[dq].[dq_results] AS r
WHERE r.run_id = (SELECT TOP 1 run_id FROM [lh_silver].[dq].[dq_results] ORDER BY checked_at DESC);
GO

CREATE OR ALTER VIEW rpt.vw_gold_integrity AS
SELECT 'fact.ticket_sales' AS fact_table, 'unknown patron'     AS check_name, COUNT(*) AS rows_failing FROM fact.ticket_sales WHERE patron_key = -1
UNION ALL SELECT 'fact.ticket_sales', 'unknown performance', COUNT(*) FROM fact.ticket_sales WHERE performance_key = -1
UNION ALL SELECT 'fact.gifts',        'unknown patron',      COUNT(*) FROM fact.gifts WHERE patron_key = -1
UNION ALL SELECT 'fact.gifts',        'unknown campaign',    COUNT(*) FROM fact.gifts WHERE campaign_key = -1
UNION ALL SELECT 'fact.gifts',        'duplicate gift_id',
                 COUNT(*) FROM (SELECT gift_id FROM fact.gifts GROUP BY gift_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'fact.ticket_sales', 'duplicate order_line_id',
                 COUNT(*) FROM (SELECT order_line_id FROM fact.ticket_sales GROUP BY order_line_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'dim.patron',        'multiple current versions',
                 COUNT(*) FROM (SELECT patron_id FROM dim.patron WHERE is_current = 1 GROUP BY patron_id HAVING COUNT(*) > 1) AS x;
GO

CREATE OR ALTER VIEW rpt.vw_pipeline_health AS
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
