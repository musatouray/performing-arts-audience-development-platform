/* =============================================================================
   wh_gold · 40 — fact load procedures
   * ticket_sales, gifts : INCREMENTAL. Watermark on Silver _silver_updated_at.
                           Changed business keys are DELETEd then re-INSERTed inside a
                           transaction -> idempotent, handles late-arriving changes
                           (e.g. an order returned 3 days after purchase).
   * subscriptions, education_sessions : small -> full refresh (TRUNCATE + INSERT).
   * Patron lookup is POINT-IN-TIME: the SCD2 version valid at the transaction time.
   * Every lookup falls back to -1 (unknown) so no fact row is silently dropped.
   ============================================================================= */

CREATE OR ALTER PROCEDURE etl.usp_load_fact_ticket_sales @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @wm datetime2(6), @new_wm datetime2(6), @del int, @ins int;
    EXEC etl.usp_get_watermark 'fact.ticket_sales', @wm OUTPUT;

    SELECT @new_wm = MAX(x) FROM (
        SELECT MAX(_silver_updated_at) AS x FROM [lh_silver].[ticketing].[order_lines]
        UNION ALL SELECT MAX(_silver_updated_at) FROM [lh_silver].[ticketing].[orders]) AS t;

    -- Changed lines = lines that changed OR whose parent order changed (status -> Returned).
    DROP TABLE IF EXISTS etl.stg_ticket_sales;
    CREATE TABLE etl.stg_ticket_sales AS
    SELECT ol.order_line_id, ol.order_id,
           ISNULL(p.patron_key, -1)                         AS patron_key,
           ISNULL(dp.performance_key, -1)                   AS performance_key,
           ISNULL(v.venue_key, -1)                          AS venue_key,
           ISNULL(c.channel_key, -1)                        AS channel_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(o.order_datetime AS date), 112)), -1) AS order_date_key,
           ISNULL(dp.performance_date_key, -1)              AS performance_date_key,
           DATEDIFF(day, o.order_datetime, dp.performance_datetime) AS days_before_show,
           ol.price_zone,
           ISNULL(ol.quantity, 0)                                                         AS quantity,
           ISNULL(ol.unit_price, 0)                                                       AS unit_price,
           CAST(ISNULL(ol.quantity, 0) * ISNULL(ol.unit_price, 0) AS decimal(14,2))       AS gross_amount,
           CAST(ISNULL(ol.discount_amount, 0) AS decimal(14,2))                           AS discount_amount,
           CAST(ISNULL(ol.quantity, 0) * ISNULL(ol.unit_price, 0) - ISNULL(ol.discount_amount, 0) AS decimal(14,2)) AS net_amount,
           CAST(ISNULL(ol.is_comp, 0) AS bit)                                             AS is_comp,
           CAST(CASE WHEN o.[status] = 'Returned' THEN 1 ELSE 0 END AS bit)               AS is_returned,
           SYSUTCDATETIME()                                                               AS loaded_at
    FROM [lh_silver].[ticketing].[order_lines] AS ol
    LEFT JOIN [lh_silver].[ticketing].[orders]      AS o  ON o.order_id = ol.order_id
    LEFT JOIN [lh_silver].[core].[patron_xref]      AS x  ON x.source_system = 'ticketing' AND x.source_id = o.customer_id
    LEFT JOIN dim.patron                            AS p  ON p.patron_id = x.patron_id
                                                         AND o.order_datetime >= p.valid_from AND o.order_datetime < p.valid_to
    LEFT JOIN dim.performance                       AS dp ON dp.performance_id = ol.performance_id
    LEFT JOIN dim.venue                             AS v  ON v.venue_id = dp.venue_id
    LEFT JOIN dim.channel                           AS c  ON c.channel_name = o.channel
    WHERE ol._silver_updated_at > @wm OR o._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.ticket_sales
            WHERE order_line_id IN (SELECT order_line_id FROM etl.stg_ticket_sales);
            SET @del = @@ROWCOUNT;
            INSERT INTO fact.ticket_sales SELECT * FROM etl.stg_ticket_sales;
            SET @ins = @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fact.ticket_sales', @new_wm;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_fact_ticket_sales', 'fact.ticket_sales', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;

    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_ticket_sales', 'fact.ticket_sales', @ins, 0, @del, 'Succeeded',
         CONCAT('watermark ', CONVERT(varchar(30), @wm, 126), ' -> ', CONVERT(varchar(30), @new_wm, 126)), @started;
END;
GO

CREATE OR ALTER PROCEDURE etl.usp_load_fact_gifts @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @wm datetime2(6), @new_wm datetime2(6), @del int, @ins int;
    EXEC etl.usp_get_watermark 'fact.gifts', @wm OUTPUT;
    SELECT @new_wm = MAX(_silver_updated_at) FROM [lh_silver].[fundraising].[gifts];

    DROP TABLE IF EXISTS etl.stg_gifts;
    CREATE TABLE etl.stg_gifts AS
    SELECT g.gift_id,
           ISNULL(p.patron_key, -1)   AS patron_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), g.gift_date, 112)), -1) AS gift_date_key,
           ISNULL(ca.campaign_key, -1) AS campaign_key,
           ISNULL(f.fund_key, -1)      AS fund_key,
           CAST(ISNULL(g.amount, 0) AS decimal(14,2)) AS amount,
           g.gift_type,
           CAST(ISNULL(g.is_anonymous, 0) AS bit) AS is_anonymous,
           SYSUTCDATETIME() AS loaded_at
    FROM [lh_silver].[fundraising].[gifts]      AS g
    LEFT JOIN [lh_silver].[core].[patron_xref]  AS x  ON x.source_system = 'fundraising' AND x.source_id = g.donor_id
    LEFT JOIN dim.patron                        AS p  ON p.patron_id = x.patron_id
                                                     AND CAST(g.gift_date AS datetime2(6)) >= p.valid_from
                                                     AND CAST(g.gift_date AS datetime2(6)) <  p.valid_to
    LEFT JOIN dim.campaign                      AS ca ON ca.campaign_id = g.campaign_id
    LEFT JOIN dim.fund                          AS f  ON f.fund_id = g.fund_id
    WHERE g._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.gifts WHERE gift_id IN (SELECT gift_id FROM etl.stg_gifts);
            SET @del = @@ROWCOUNT;
            INSERT INTO fact.gifts SELECT * FROM etl.stg_gifts;
            SET @ins = @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fact.gifts', @new_wm;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gifts', 'fact.gifts', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;

    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gifts', 'fact.gifts', @ins, 0, @del, 'Succeeded', NULL, @started;
END;
GO

CREATE OR ALTER PROCEDURE etl.usp_load_fact_subscriptions_and_education @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @n1 int, @n2 int;

    TRUNCATE TABLE fact.subscriptions;
    INSERT INTO fact.subscriptions
    SELECT s.subscription_id,
           ISNULL(p.patron_key, -1),
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(s.purchased_at AS date), 112)), -1),
           s.season_id, se.fiscal_year, s.package_name, ISNULL(s.seats, 0), ISNULL(s.package_amount, 0),
           CAST(ISNULL(s.is_renewal, 0) AS bit), SYSUTCDATETIME()
    FROM [lh_silver].[ticketing].[subscriptions] AS s
    JOIN [lh_silver].[ticketing].[seasons]       AS se ON se.season_id = s.season_id
    LEFT JOIN [lh_silver].[core].[patron_xref]   AS x  ON x.source_system = 'ticketing' AND x.source_id = s.customer_id
    LEFT JOIN dim.patron                         AS p  ON p.patron_id = x.patron_id
                                                      AND s.purchased_at >= p.valid_from AND s.purchased_at < p.valid_to;
    SET @n1 = @@ROWCOUNT;

    TRUNCATE TABLE fact.education_sessions;
    INSERT INTO fact.education_sessions
    SELECT e.enrollment_id, ISNULL(pr.program_key, -1), ISNULL(sc.school_key, -1),
           ISNULL(CONVERT(int, CONVERT(varchar(8), e.session_date, 112)), -1),
           ISNULL(e.participants, 0), e.teaching_artist_hours, SYSUTCDATETIME()
    FROM [lh_silver].[education].[enrollments] AS e
    LEFT JOIN dim.program AS pr ON pr.program_id = e.program_id
    LEFT JOIN dim.school  AS sc ON sc.school_id  = e.school_id;
    SET @n2 = @@ROWCOUNT;

    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_subscriptions_and_education', 'fact.subscriptions+education_sessions',
         @n1 + @n2, 0, 0, 'Succeeded', NULL, @started;
END;
GO

-- ---------------------------------------------------------------------------
-- Orchestrator: the ONE procedure the pipeline calls (Stored procedure activity).
-- Pipeline passes @run_id = @pipeline().RunId for end-to-end lineage in the logs.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_gold @run_id varchar(64) = NULL
AS
BEGIN
    SET @run_id = ISNULL(@run_id, CONVERT(varchar(64), NEWID()));
    IF NOT EXISTS (SELECT 1 FROM dim.[date]) EXEC etl.usp_load_dim_date;
    EXEC etl.usp_load_dim_reference @run_id;
    EXEC etl.usp_load_dim_patron @run_id;          -- dims BEFORE facts (facts look up surrogate keys)
    EXEC etl.usp_load_fact_ticket_sales @run_id;
    EXEC etl.usp_load_fact_gifts @run_id;
    EXEC etl.usp_load_fact_subscriptions_and_education @run_id;
    SELECT * FROM etl.load_log WHERE run_id = @run_id ORDER BY started_at;
END;
GO
