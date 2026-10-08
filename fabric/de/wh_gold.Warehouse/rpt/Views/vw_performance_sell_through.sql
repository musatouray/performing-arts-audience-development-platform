/* =============================================================================
   wh_gold 50: reporting views for people who use SQL or paginated reports
   Most people use the Power BI reports. These views use the same definitions
   (sell-through, lapsed donors, renewals) so the numbers match.
   People are counted by patron_id. patron_key can't be used because one person
   can have several rows when their address changes.
   ============================================================================= */

-- Sell-through per performance (tickets sold vs capacity), excluding returns.
CREATE   VIEW rpt.vw_performance_sell_through AS
SELECT p.performance_id, p.title, p.series, p.genre, p.season_name, p.fiscal_year, p.venue_name,
       p.performance_datetime, p.day_part, p.capacity, p.[status],
       SUM(CASE WHEN s.is_returned = 0 THEN s.quantity ELSE 0 END)                        AS tickets_sold,
       SUM(CASE WHEN s.is_returned = 0 AND s.is_comp = 1 THEN s.quantity ELSE 0 END)      AS comps,
       SUM(CASE WHEN s.is_returned = 0 THEN s.net_amount ELSE 0 END)                      AS net_revenue,
       CAST(SUM(CASE WHEN s.is_returned = 0 THEN s.quantity ELSE 0 END) AS decimal(12,4))
           / NULLIF(p.capacity, 0)                                                        AS sell_through_pct,
       CAST(SUM(CASE WHEN s.is_returned = 0 THEN s.net_amount ELSE 0 END) AS decimal(14,2))
           / NULLIF(p.capacity, 0)                                                        AS revenue_per_available_seat
FROM dim.performance AS p
LEFT JOIN fact.ticket_sales AS s ON s.performance_key = p.performance_key
WHERE p.performance_key > 0
GROUP BY p.performance_id, p.title, p.series, p.genre, p.season_name, p.fiscal_year, p.venue_name,
         p.performance_datetime, p.day_part, p.capacity, p.[status];

GO