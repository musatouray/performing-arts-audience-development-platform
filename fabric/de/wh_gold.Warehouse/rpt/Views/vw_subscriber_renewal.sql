-- Subscriber renewal by season: subscribers who renewed / last season's subscribers.
CREATE   VIEW rpt.vw_subscriber_renewal AS
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