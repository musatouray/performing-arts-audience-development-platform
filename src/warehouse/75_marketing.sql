/* =============================================================================
   wh_gold 75: marketing (email and paid ads), for the Audience & Development spoke
   Marketing used to stop at Silver. Analysts read Gold, never Silver (ADR-006), so
   it's modelled here like every other source. Safe to run again. Run after 70 and 80,
   then rerun 40 so the orchestrator calls etl.usp_load_marketing.

     dim.email_campaign            one row per email campaign
     fact.email_campaign_results   its latest numbers (the platform restates them for a week)
     fact.email_click              one row per click, linked to the PATRON, not the email address
     fact.ad_spend_daily           one row per day per ad campaign (platforms restate recent days)
     rpt.vw_email_campaign_performance   rates, plus buyers and ticket revenue within 7 days of a click
     rpt.vw_ad_spend_by_series           paid ads vs the promoted series' ticket revenue

   Privacy: Silver's email_clicks holds email addresses. Gold uses the address only to
   find the patron during the load and never stores it.
   ============================================================================= */

IF OBJECT_ID('dim.email_campaign') IS NULL
CREATE TABLE dim.email_campaign (
    email_campaign_key  int           NOT NULL,
    email_campaign_id   varchar(30)   NOT NULL,
    campaign_name       varchar(200)  NULL,
    campaign_type       varchar(50)   NULL,
    series_promoted     varchar(100)  NULL,   -- matches dim.performance.series; empty for general campaigns
    audience_segment    varchar(100)  NULL,
    send_datetime       datetime2(6)  NULL,
    send_date_key       int           NOT NULL
);
GO

IF OBJECT_ID('fact.email_campaign_results') IS NULL
CREATE TABLE fact.email_campaign_results (
    email_campaign_key  int           NOT NULL,   -- grain: one row per campaign (latest numbers)
    send_date_key       int           NOT NULL,
    recipients          int           NOT NULL,
    delivered           int           NOT NULL,
    bounces             int           NOT NULL,
    unique_opens        int           NOT NULL,
    unique_clicks       int           NOT NULL,
    unsubscribes        int           NOT NULL,
    stats_as_of         datetime2(6)  NULL,
    loaded_at           datetime2(6)  NOT NULL
);
GO

IF OBJECT_ID('fact.email_click') IS NULL
CREATE TABLE fact.email_click (
    click_id            varchar(40)   NOT NULL,   -- grain: one click
    email_campaign_key  int           NOT NULL,
    patron_key          int           NOT NULL,   -- -1 if the address isn't a known patron
    click_date_key      int           NOT NULL,
    clicked_at          datetime2(6)  NULL,
    loaded_at           datetime2(6)  NOT NULL
);
GO

IF OBJECT_ID('fact.ad_spend_daily') IS NULL
CREATE TABLE fact.ad_spend_daily (
    ad_date_key       int            NOT NULL,   -- grain: one day x one ad campaign
    platform          varchar(30)    NULL,
    ad_campaign_id    varchar(60)    NOT NULL,
    ad_campaign_name  varchar(200)   NULL,
    utm_campaign      varchar(100)   NULL,
    series_promoted   varchar(100)   NULL,
    impressions       int            NOT NULL,
    clicks            int            NOT NULL,
    spend             decimal(12,2)  NOT NULL,
    loaded_at         datetime2(6)   NOT NULL
);
GO

-- ---------------------------------------------------------------------------
-- Load
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_marketing @run_id varchar(64)
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

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- Each email campaign: the platform's rates, plus what Gold adds by knowing the patron:
-- how many clickers bought tickets for the promoted series within 7 days, and for how much.
-- Directional (last touch, 7 days), not a full attribution model.
CREATE OR ALTER VIEW rpt.vw_email_campaign_performance AS
WITH clickers AS (
    SELECT DISTINCT c.email_campaign_key, p.patron_id, d.[date] AS click_date
    FROM fact.email_click AS c
    JOIN dim.patron AS p ON p.patron_key = c.patron_key
    JOIN dim.[date] AS d ON d.date_key = c.click_date_key
    WHERE c.patron_key > 0
),
converted AS (
    SELECT k.email_campaign_key, COUNT(DISTINCT k.patron_id) AS buyers_7d, SUM(s.net_amount) AS ticket_revenue_7d
    FROM clickers AS k
    JOIN dim.email_campaign AS ec ON ec.email_campaign_key = k.email_campaign_key
    JOIN dim.patron AS bp ON bp.patron_id = k.patron_id
    JOIN fact.ticket_sales AS s ON s.patron_key = bp.patron_key AND s.is_returned = 0
    JOIN dim.[date] AS od ON od.date_key = s.order_date_key
    JOIN dim.performance AS pf ON pf.performance_key = s.performance_key
    WHERE od.[date] BETWEEN k.click_date AND DATEADD(day, 7, k.click_date)
      AND (ec.series_promoted IS NULL OR pf.series = ec.series_promoted)
    GROUP BY k.email_campaign_key
)
SELECT ec.email_campaign_id, ec.campaign_name, ec.campaign_type, ec.series_promoted, ec.audience_segment,
       CAST(ec.send_datetime AS date) AS send_date, d.fiscal_year,
       r.recipients, r.delivered, r.unique_opens, r.unique_clicks, r.unsubscribes,
       CAST(r.delivered     AS decimal(12,4)) / NULLIF(r.recipients, 0) AS delivery_rate,
       CAST(r.unique_opens  AS decimal(12,4)) / NULLIF(r.delivered, 0)  AS open_rate,
       CAST(r.unique_clicks AS decimal(12,4)) / NULLIF(r.delivered, 0)  AS click_rate,
       CAST(r.unsubscribes  AS decimal(12,4)) / NULLIF(r.delivered, 0)  AS unsubscribe_rate,
       ISNULL(cv.buyers_7d, 0) AS buyers_within_7_days,
       ISNULL(cv.ticket_revenue_7d, 0) AS ticket_revenue_within_7_days
FROM dim.email_campaign AS ec
JOIN fact.email_campaign_results AS r ON r.email_campaign_key = ec.email_campaign_key
JOIN dim.[date] AS d ON d.date_key = r.send_date_key
LEFT JOIN converted AS cv ON cv.email_campaign_key = ec.email_campaign_key
WHERE ec.email_campaign_key > 0;
GO

-- Paid ads by fiscal year, series and platform, next to that series' ticket revenue.
-- Revenue per ad dollar is directional: it isn't all caused by the ads.
CREATE OR ALTER VIEW rpt.vw_ad_spend_by_series AS
WITH ads AS (
    SELECT d.fiscal_year, a.series_promoted, a.platform,
           SUM(a.spend) AS spend, SUM(a.impressions) AS impressions, SUM(a.clicks) AS clicks
    FROM fact.ad_spend_daily AS a JOIN dim.[date] AS d ON d.date_key = a.ad_date_key
    GROUP BY d.fiscal_year, a.series_promoted, a.platform
),
sales AS (
    SELECT p.fiscal_year, p.series, SUM(s.net_amount) AS net_ticket_revenue
    FROM fact.ticket_sales AS s JOIN dim.performance AS p ON p.performance_key = s.performance_key
    WHERE s.is_returned = 0
    GROUP BY p.fiscal_year, p.series
)
SELECT a.fiscal_year, a.series_promoted, a.platform, a.spend, a.impressions, a.clicks,
       CAST(a.clicks AS decimal(14,4)) / NULLIF(a.impressions, 0) AS click_through_rate,
       a.spend / NULLIF(a.clicks, 0)                               AS cost_per_click,
       s.net_ticket_revenue AS series_net_ticket_revenue,
       s.net_ticket_revenue / NULLIF(SUM(a.spend) OVER (PARTITION BY a.fiscal_year, a.series_promoted), 0)
           AS series_revenue_per_ad_dollar
FROM ads AS a
LEFT JOIN sales AS s ON s.fiscal_year = a.fiscal_year AND s.series = a.series_promoted;
GO
-- Access: rpt is already granted to the audience and development groups (60_security.sql);
-- dim and fact to development. The audience group sees marketing through these views.
