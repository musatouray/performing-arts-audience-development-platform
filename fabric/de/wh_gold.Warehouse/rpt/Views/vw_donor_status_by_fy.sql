-- Each donor's status per fiscal year: New, Retained, Reactivated, LYBUNT or SYBUNT.
--   LYBUNT = gave Last Year But Unfortunately Not This year
--   SYBUNT = gave Some Year (before last) But Unfortunately Not This year
CREATE   VIEW rpt.vw_donor_status_by_fy AS
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