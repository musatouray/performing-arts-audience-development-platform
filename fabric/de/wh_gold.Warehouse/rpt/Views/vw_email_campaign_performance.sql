-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- Each email campaign: the platform's rates, plus what Gold adds by knowing the patron:
-- how many clickers bought tickets for the promoted series within 7 days, and for how much.
-- Directional (last touch, 7 days), not a full attribution model.
CREATE   VIEW rpt.vw_email_campaign_performance AS
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