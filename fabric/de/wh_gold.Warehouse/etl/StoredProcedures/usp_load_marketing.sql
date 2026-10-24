-- ---------------------------------------------------------------------------
-- Load
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_marketing @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @max int, @ins int = 0, @upd int = 0, @del int = 0,
            @wm datetime2(6), @new_wm datetime2(6);

    /* ---- dim.email_campaign ---- */
    UPDATE t SET campaign_name = s.campaign_name, campaign_type = s.campaign_type, series_promoted = s.series_promoted,
                 audience_segment = s.audience_segment, send_datetime = s.send_datetime,
                 send_date_key = ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(s.send_datetime AS date), 112)), -1)
    FROM dim.email_campaign AS t JOIN [lh_silver].[marketing].[email_campaigns] AS s ON t.email_campaign_id = s.email_campaign_id
    WHERE ISNULL(t.campaign_name, '') <> ISNULL(s.campaign_name, '') OR ISNULL(t.send_datetime, '1900-01-01') <> ISNULL(s.send_datetime, '1900-01-01');
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(email_campaign_key), 0) FROM dim.email_campaign WHERE email_campaign_key > 0;
    INSERT INTO dim.email_campaign
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.email_campaign_id), s.email_campaign_id, s.campaign_name, s.campaign_type,
           NULLIF(s.series_promoted, ''), s.audience_segment, CAST(s.send_datetime AS datetime2(6)),
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(s.send_datetime AS date), 112)), -1)
    FROM [lh_silver].[marketing].[email_campaigns] AS s
    WHERE NOT EXISTS (SELECT 1 FROM dim.email_campaign AS t WHERE t.email_campaign_id = s.email_campaign_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.email_campaign WHERE email_campaign_key = -1)
        INSERT INTO dim.email_campaign VALUES (-1, 'N/A', 'Unknown campaign', NULL, NULL, NULL, NULL, -1);

    BEGIN TRY
        BEGIN TRANSACTION;
            /* ---- campaign results: small and restated for a week, so rebuilt ---- */
            DELETE FROM fact.email_campaign_results;
            INSERT INTO fact.email_campaign_results
            SELECT d.email_campaign_key, d.send_date_key, ISNULL(s.recipients, 0), ISNULL(s.delivered, 0), ISNULL(s.bounces, 0),
                   ISNULL(s.unique_opens, 0), ISNULL(s.unique_clicks, 0), ISNULL(s.unsubscribes, 0),
                   CAST(s.updated_at AS datetime2(6)), CAST(SYSUTCDATETIME() AS datetime2(6))
            FROM [lh_silver].[marketing].[email_campaigns] AS s
            JOIN dim.email_campaign AS d ON d.email_campaign_id = s.email_campaign_id;
            SET @ins += @@ROWCOUNT;

            /* ---- ad spend: platforms restate the last days, and it's small, so rebuilt ---- */
            DELETE FROM fact.ad_spend_daily;
            INSERT INTO fact.ad_spend_daily
            SELECT ISNULL(CONVERT(int, CONVERT(varchar(8), a.ad_date, 112)), -1), a.platform, a.ad_campaign_id, a.ad_campaign_name,
                   a.utm_campaign, NULLIF(a.series_promoted, ''), ISNULL(a.impressions, 0), ISNULL(a.clicks, 0),
                   CAST(ISNULL(a.spend, 0) AS decimal(12,2)), CAST(SYSUTCDATETIME() AS datetime2(6))
            FROM [lh_silver].[marketing].[ad_spend_daily] AS a;
            SET @ins += @@ROWCOUNT;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg1 varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_marketing', 'fact.email_campaign_results+ad_spend_daily', 0, 0, 0, 'Failed', @msg1, @started;
        THROW;
    END CATCH;

    /* ---- email clicks: incremental. The address finds the patron, then is dropped. ---- */
    EXEC etl.usp_get_watermark 'fact.email_click', @wm OUTPUT;
    SELECT @new_wm = MAX(_silver_updated_at) FROM [lh_silver].[marketing].[email_clicks];

    DROP TABLE IF EXISTS etl.stg_email_click;
    CREATE TABLE etl.stg_email_click AS
    SELECT c.click_id,
           ISNULL(d.email_campaign_key, -1) AS email_campaign_key,
           ISNULL(p.patron_key, -1)         AS patron_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(c.clicked_at AS date), 112)), -1) AS click_date_key,
           CAST(c.clicked_at AS datetime2(6)) AS clicked_at,
           CAST(SYSUTCDATETIME() AS datetime2(6)) AS loaded_at
    FROM [lh_silver].[marketing].[email_clicks] AS c
    LEFT JOIN dim.email_campaign AS d ON d.email_campaign_id = c.email_campaign_id
    LEFT JOIN (SELECT LOWER(email) AS email_key, MIN(patron_id) AS patron_id      -- one patron per address
               FROM dim.patron WHERE is_current = 1 AND email IS NOT NULL GROUP BY LOWER(email)) AS e
           ON e.email_key = LOWER(c.email)
    LEFT JOIN dim.patron AS p ON p.patron_id = e.patron_id                        -- the patron as they were when they clicked
                             AND CAST(c.clicked_at AS datetime2(6)) >= p.valid_from
                             AND CAST(c.clicked_at AS datetime2(6)) <  p.valid_to
    WHERE c._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.email_click WHERE click_id IN (SELECT click_id FROM etl.stg_email_click);
            SET @del += @@ROWCOUNT;
            INSERT INTO fact.email_click SELECT * FROM etl.stg_email_click;
            SET @ins += @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fact.email_click', @new_wm;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg2 varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_marketing', 'fact.email_click', 0, 0, 0, 'Failed', @msg2, @started;
        THROW;
    END CATCH;

    EXEC etl.usp_log @run_id, 'etl.usp_load_marketing', 'dim.email_campaign+fact.email_*+fact.ad_spend_daily',
         @ins, @upd, @del, 'Succeeded', NULL, @started;
END;

GO