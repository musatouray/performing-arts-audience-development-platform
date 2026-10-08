CREATE   VIEW rpt.vw_gold_integrity AS
SELECT 'fact.ticket_sales' AS fact_table, 'unknown patron'     AS check_name, COUNT(*) AS rows_failing FROM fact.ticket_sales WHERE patron_key = -1
UNION ALL SELECT 'fact.ticket_sales', 'unknown performance', COUNT(*) FROM fact.ticket_sales WHERE performance_key = -1
UNION ALL SELECT 'fact.gifts',        'unknown patron',      COUNT(*) FROM fact.gifts WHERE patron_key = -1
UNION ALL SELECT 'fact.gifts',        'unknown campaign',    COUNT(*) FROM fact.gifts WHERE campaign_key = -1
UNION ALL SELECT 'fact.gifts',        'duplicate gift_id',
                 COUNT(*) FROM (SELECT gift_id FROM fact.gifts GROUP BY gift_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'fact.ticket_sales', 'duplicate order_line_id',
                 COUNT(*) FROM (SELECT order_line_id FROM fact.ticket_sales GROUP BY order_line_id HAVING COUNT(*) > 1) AS d
UNION ALL SELECT 'dim.patron',        'multiple current versions',
                 COUNT(*) FROM (SELECT patron_id FROM dim.patron WHERE is_current = 1 GROUP BY patron_id HAVING COUNT(*) > 1) AS x;

GO