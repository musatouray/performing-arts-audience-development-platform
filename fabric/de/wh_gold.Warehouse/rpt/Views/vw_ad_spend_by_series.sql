-- Paid ads by fiscal year, series and platform, next to that series' ticket revenue.
-- Revenue per ad dollar is directional: it isn't all caused by the ads.
CREATE   VIEW rpt.vw_ad_spend_by_series AS
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