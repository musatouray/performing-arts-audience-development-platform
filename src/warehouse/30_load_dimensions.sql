/* =============================================================================
   wh_gold · 30 — dimension load procedures
   Patterns shown (interview talking points):
     * Type 1 upsert  : UPDATE changed attributes + INSERT new business keys
     * SCD Type 2     : expire changed current rows, insert new versions (dim.patron)
     * Surrogate keys : MAX(key) + ROW_NUMBER()  (no IDENTITY needed)
     * Unknown member : key -1 in every dimension
     * Idempotent     : re-running produces the same result (safe pipeline retries)
   MERGE is available in Fabric Warehouse, but UPDATE + INSERT is used here because it
   is portable, easy to review, and gives exact row counts for the load log.
   ============================================================================= */

-- ---------------------------------------------------------------------------
-- dim.date — generated, not sourced. Fiscal calendar = Jul -> Jun.
-- (No recursive CTE: a 5-way cross join of digits gives 0..99,999 day offsets.)
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_dim_date
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

-- ---------------------------------------------------------------------------
-- Small Type-1 dimensions: venue, performance, channel, campaign, fund, program, school
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_dim_reference @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @max int, @ins int = 0, @upd int = 0;

    /* ---- venue ---- */
    UPDATE t SET venue_name = s.venue_name, capacity = s.capacity
    FROM dim.venue AS t JOIN [lh_silver].[ticketing].[venues] AS s ON t.venue_id = s.venue_id
    WHERE t.venue_name <> s.venue_name OR ISNULL(t.capacity, -9) <> ISNULL(s.capacity, -9);
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(venue_key), 0) FROM dim.venue WHERE venue_key > 0;
    INSERT INTO dim.venue
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.venue_id), s.venue_id, s.venue_name, s.capacity
    FROM [lh_silver].[ticketing].[venues] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.venue AS t WHERE t.venue_id = s.venue_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.venue WHERE venue_key = -1)
        INSERT INTO dim.venue VALUES (-1, 'N/A', 'Unknown', NULL);

    /* ---- performance (denormalises season + venue: a star, not a snowflake) ---- */
    WITH src AS (
        SELECT p.performance_id, p.title, p.series, p.genre, p.season_id, s.season_name, s.fiscal_year,
               p.venue_id, v.venue_name, p.performance_datetime,
               CONVERT(int, CONVERT(varchar(8), CAST(p.performance_datetime AS date), 112)) AS performance_date_key,
               CASE WHEN DATEPART(hour, p.performance_datetime) < 17 THEN 'Matinee' ELSE 'Evening' END AS day_part,
               p.capacity, p.[status]
        FROM [lh_silver].[ticketing].[performances] AS p
        LEFT JOIN [lh_silver].[ticketing].[seasons] AS s ON s.season_id = p.season_id
        LEFT JOIN [lh_silver].[ticketing].[venues]  AS v ON v.venue_id = p.venue_id
    )
    UPDATE t SET title = s.title, series = s.series, genre = s.genre, season_id = s.season_id,
                 season_name = s.season_name, fiscal_year = s.fiscal_year, venue_id = s.venue_id,
                 venue_name = s.venue_name, performance_datetime = s.performance_datetime,
                 performance_date_key = s.performance_date_key, day_part = s.day_part,
                 capacity = s.capacity, [status] = s.[status]
    FROM dim.performance AS t JOIN src AS s ON t.performance_id = s.performance_id
    WHERE ISNULL(t.[status], '') <> ISNULL(s.[status], '') OR ISNULL(t.capacity, -9) <> ISNULL(s.capacity, -9)
       OR ISNULL(t.title, '') <> ISNULL(s.title, '') OR t.performance_datetime <> s.performance_datetime;
    SET @upd += @@ROWCOUNT;

    SELECT @max = ISNULL(MAX(performance_key), 0) FROM dim.performance WHERE performance_key > 0;
    INSERT INTO dim.performance
    SELECT @max + ROW_NUMBER() OVER (ORDER BY p.performance_id), p.performance_id, p.title, p.series, p.genre,
           p.season_id, s.season_name, s.fiscal_year, p.venue_id, v.venue_name, p.performance_datetime,
           CONVERT(int, CONVERT(varchar(8), CAST(p.performance_datetime AS date), 112)),
           CASE WHEN DATEPART(hour, p.performance_datetime) < 17 THEN 'Matinee' ELSE 'Evening' END,
           p.capacity, p.[status]
    FROM [lh_silver].[ticketing].[performances] AS p
    LEFT JOIN [lh_silver].[ticketing].[seasons] AS s ON s.season_id = p.season_id
    LEFT JOIN [lh_silver].[ticketing].[venues]  AS v ON v.venue_id = p.venue_id
    WHERE NOT EXISTS (SELECT 1 FROM dim.performance AS t WHERE t.performance_id = p.performance_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.performance WHERE performance_key = -1)
        INSERT INTO dim.performance (performance_key, performance_id, title, performance_date_key, capacity)
        VALUES (-1, 'N/A', 'Unknown performance', -1, 0);

    /* ---- channel (derived from orders) ---- */
    SELECT @max = ISNULL(MAX(channel_key), 0) FROM dim.channel WHERE channel_key > 0;
    INSERT INTO dim.channel
    SELECT @max + ROW_NUMBER() OVER (ORDER BY c.channel), c.channel
    FROM (SELECT DISTINCT channel FROM [lh_silver].[ticketing].[orders] WHERE channel IS NOT NULL) AS c
    WHERE NOT EXISTS (SELECT 1 FROM dim.channel AS t WHERE t.channel_name = c.channel);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.channel WHERE channel_key = -1)
        INSERT INTO dim.channel VALUES (-1, 'Unknown');

    /* ---- campaign ---- */
    UPDATE t SET campaign_name = s.campaign_name, campaign_type = s.campaign_type,
                 fiscal_year = s.fiscal_year, goal_amount = s.goal_amount
    FROM dim.campaign AS t JOIN [lh_silver].[fundraising].[campaigns] AS s ON t.campaign_id = s.campaign_id
    WHERE ISNULL(t.goal_amount, -1) <> ISNULL(s.goal_amount, -1) OR ISNULL(t.campaign_name, '') <> ISNULL(s.campaign_name, '');
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(campaign_key), 0) FROM dim.campaign WHERE campaign_key > 0;
    INSERT INTO dim.campaign
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.campaign_id), s.campaign_id, s.campaign_name, s.campaign_type, s.fiscal_year, s.goal_amount
    FROM [lh_silver].[fundraising].[campaigns] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.campaign AS t WHERE t.campaign_id = s.campaign_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.campaign WHERE campaign_key = -1)
        INSERT INTO dim.campaign VALUES (-1, 'N/A', 'Unknown campaign', 'Unknown', NULL, NULL);

    /* ---- fund ---- */
    SELECT @max = ISNULL(MAX(fund_key), 0) FROM dim.fund WHERE fund_key > 0;
    INSERT INTO dim.fund
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.fund_id), s.fund_id, s.fund_name, s.is_restricted
    FROM [lh_silver].[fundraising].[funds] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.fund AS t WHERE t.fund_id = s.fund_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.fund WHERE fund_key = -1)
        INSERT INTO dim.fund VALUES (-1, 'N/A', 'Unknown fund', NULL);

    /* ---- program ---- */
    SELECT @max = ISNULL(MAX(program_key), 0) FROM dim.program WHERE program_key > 0;
    INSERT INTO dim.program
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.program_id), s.program_id, s.program_name, s.program_type, s.audience
    FROM [lh_silver].[education].[programs] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.program AS t WHERE t.program_id = s.program_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.program WHERE program_key = -1)
        INSERT INTO dim.program VALUES (-1, 'N/A', 'Unknown program', 'Unknown', NULL);

    /* ---- school (-1 also means "not a school-based session", e.g. community programs) ---- */
    SELECT @max = ISNULL(MAX(school_key), 0) FROM dim.school WHERE school_key > 0;
    INSERT INTO dim.school
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.school_id), s.school_id, s.school_name, s.borough, s.is_title_i
    FROM [lh_silver].[education].[schools] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.school AS t WHERE t.school_id = s.school_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.school WHERE school_key = -1)
        INSERT INTO dim.school VALUES (-1, 'N/A', 'Community / not school-based', NULL, NULL);

    EXEC etl.usp_log @run_id, 'etl.usp_load_dim_reference', 'dim.*', @ins, @upd, 0, 'Succeeded', NULL, @started;
END;
GO

-- ---------------------------------------------------------------------------
-- dim.patron — SCD Type 2 on geography/type; Type 1 on contact details.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_dim_patron @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @now datetime2(6) = SYSUTCDATETIME(),
            @max int, @ins int, @upd int, @exp int;

    -- 1) Stage the golden records with derived columns + change-detection hash (CTAS = fast, minimal logging).
    DROP TABLE IF EXISTS etl.stg_patron;
    CREATE TABLE etl.stg_patron AS
    SELECT p.patron_id, p.first_name, p.last_name,
           CAST(CONCAT_WS(' ', p.first_name, p.last_name) AS varchar(210)) AS full_name,
           p.email, p.phone, p.address_line1, p.city, p.[state], p.postal_code, p.country,
           CAST(CASE WHEN p.city IN ('New York', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island') AND p.[state] = 'NY' THEN 'NYC'
                     WHEN p.[state] IN ('NY', 'NJ', 'CT') THEN 'NY Metro'
                     WHEN p.country = 'USA' THEN 'Domestic'
                     ELSE 'Unknown' END AS varchar(30)) AS region,
           p.patron_type, p.email_opt_in, p.source_systems, p.first_seen_date,
           CONVERT(varchar(64), HASHBYTES('SHA2_256',
                   CONCAT_WS('|', p.address_line1, p.city, p.[state], p.postal_code, p.patron_type)), 2) AS scd_hash
    FROM [lh_silver].[core].[patron] AS p;

    -- 2) Type 1 attributes: overwrite on the current version (no history needed for a typo fix).
    UPDATE d SET first_name = s.first_name, last_name = s.last_name, full_name = s.full_name, email = s.email,
                 phone = s.phone, email_opt_in = s.email_opt_in, source_systems = s.source_systems
    FROM dim.patron AS d JOIN etl.stg_patron AS s ON d.patron_id = s.patron_id
    WHERE d.is_current = 1
      AND (ISNULL(d.email, '') <> ISNULL(s.email, '') OR ISNULL(d.phone, '') <> ISNULL(s.phone, '')
           OR ISNULL(d.full_name, '') <> ISNULL(s.full_name, '') OR ISNULL(d.source_systems, '') <> ISNULL(s.source_systems, '')
           OR ISNULL(CAST(d.email_opt_in AS int), -1) <> ISNULL(CAST(s.email_opt_in AS int), -1));
    SET @upd = @@ROWCOUNT;

    -- 3) Type 2: close the current version when a tracked attribute changed.
    UPDATE d SET valid_to = @now, is_current = 0
    FROM dim.patron AS d JOIN etl.stg_patron AS s ON d.patron_id = s.patron_id
    WHERE d.is_current = 1 AND d.scd_hash <> s.scd_hash;
    SET @exp = @@ROWCOUNT;

    -- 4) Insert a current version for (a) brand-new patrons and (b) patrons just expired in step 3.
    --    New patrons get valid_from = 1900-01-01 so their historical orders/gifts join to them.
    SELECT @max = ISNULL(MAX(patron_key), 0) FROM dim.patron WHERE patron_key > 0;
    INSERT INTO dim.patron
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.patron_id),
           s.patron_id, s.first_name, s.last_name, s.full_name, s.email, s.phone, s.address_line1, s.city, s.[state],
           s.postal_code, s.country, s.region, s.patron_type, s.email_opt_in, s.source_systems, s.first_seen_date, s.scd_hash,
           CASE WHEN h.patron_id IS NULL THEN CAST('1900-01-01' AS datetime2(6)) ELSE @now END,
           CAST('9999-12-31' AS datetime2(6)), 1
    FROM etl.stg_patron AS s
    LEFT JOIN (SELECT DISTINCT patron_id FROM dim.patron) AS h ON h.patron_id = s.patron_id
    WHERE NOT EXISTS (SELECT 1 FROM dim.patron AS d WHERE d.patron_id = s.patron_id AND d.is_current = 1);
    SET @ins = @@ROWCOUNT;

    IF NOT EXISTS (SELECT 1 FROM dim.patron WHERE patron_key = -1)
        INSERT INTO dim.patron (patron_key, patron_id, full_name, region, valid_from, valid_to, is_current)
        VALUES (-1, 'N/A', 'Unknown patron', 'Unknown', '1900-01-01', '9999-12-31', 1);

    EXEC etl.usp_log @run_id, 'etl.usp_load_dim_patron', 'dim.patron', @ins, @upd, 0, 'Succeeded',
         CONCAT(@exp, ' version(s) expired (SCD2)'), @started;
END;
GO
