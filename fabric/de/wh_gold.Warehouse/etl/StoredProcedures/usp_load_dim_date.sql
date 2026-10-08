/* =============================================================================
   wh_gold 30: procedures that load the dimension tables
   * Most tables: update rows that changed, then insert new ones.
   * dim.patron keeps history: a changed patron gets a new row and the old row is closed.
   * Every table gets a -1 "Unknown" row.
   * Running a procedure twice gives the same result, so a failed pipeline can just be re-run.
   UPDATE then INSERT is used instead of MERGE because it's easier to read and
   gives exact row counts for the load log.
   ============================================================================= */

-- ---------------------------------------------------------------------------
-- dim.date is generated rather than loaded. The fiscal year runs July to June.
-- Crossing the digits 0-9 five times gives up to 100,000 days to build from.
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_dim_date
    @start date = '2020-07-01', @end date = '2030-06-30'
AS
BEGIN
    DELETE FROM dim.[date];

    WITH digits AS (SELECT v FROM (VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS t(v)),
    n AS (
        SELECT a.v + b.v * 10 + c.v * 100 + d.v * 1000 + e.v * 10000 AS i
        FROM digits a CROSS JOIN digits b CROSS JOIN digits c CROSS JOIN digits d CROSS JOIN digits e
    ),
    days AS (SELECT DATEADD(day, i, @start) AS dt FROM n WHERE i <= DATEDIFF(day, @start, @end))
    INSERT INTO dim.[date]
    SELECT
        CONVERT(int, CONVERT(varchar(8), dt, 112)),
        dt,
        DATEPART(weekday, dt),
        DATENAME(weekday, dt),
        CASE WHEN DATENAME(weekday, dt) IN ('Saturday', 'Sunday') THEN 1 ELSE 0 END,
        MONTH(dt),
        DATENAME(month, dt),
        DATEPART(quarter, dt),
        YEAR(dt),
        f.fy,
        CONCAT('FY', f.fy),
        f.fm,
        (f.fm - 1) / 3 + 1,
        CONCAT(f.fy - 1, '-', RIGHT(CAST(f.fy AS varchar(4)), 2))
    FROM days
    CROSS APPLY (SELECT YEAR(dt) + CASE WHEN MONTH(dt) >= 7 THEN 1 ELSE 0 END AS fy,
                        (MONTH(dt) + 5) % 12 + 1 AS fm) AS f;

    INSERT INTO dim.[date] VALUES (-1, '1900-01-01', 0, 'Unknown', 0, 0, 'Unknown', 0, 1900, 1900, 'Unknown', 0, 0, 'Unknown');
END;

GO