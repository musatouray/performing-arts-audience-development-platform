-- ---------------------------------------------------------------------------
-- The smaller dimensions (venue, performance, channel, campaign, fund, program, school).
-- These keep only the latest values, no history.
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_dim_reference @run_id varchar(64)
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

    /* ---- performance (includes season and venue details, so reports need fewer joins) ---- */
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

    /* ---- channel (taken from the orders) ---- */
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

    /* ---- school (-1 also covers sessions not held at a school, such as community programs) ---- */
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