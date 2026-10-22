CREATE   VIEW rpt.vw_finance_integrity AS
SELECT 'fin.fact_gl_entry' AS fact_table, 'unbalanced journals' AS check_name,
       COUNT(*) AS rows_failing FROM (SELECT journal_id FROM fin.fact_gl_entry GROUP BY journal_id
                                       HAVING SUM(debit_amount) <> SUM(credit_amount)) AS j
UNION ALL SELECT 'fin.fact_gl_entry', 'unknown account',  COUNT(*) FROM fin.fact_gl_entry WHERE account_key = -1
UNION ALL SELECT 'fin.fact_gl_entry', 'unknown fund',     COUNT(*) FROM fin.fact_gl_entry WHERE fund_key = -1
UNION ALL SELECT 'dim.fund', 'Tessitura fund with no ledger code', COUNT(*) FROM dim.fund WHERE fund_key > 0 AND mip_fund_code IS NULL
UNION ALL SELECT 'dim.event', 'concert not linked to a performance',
                 COUNT(*) FROM dim.event WHERE event_type = 'Concert' AND is_linked = 0
UNION ALL SELECT 'fact.venue_booking', 'unknown event or room',
                 COUNT(*) FROM fact.venue_booking WHERE event_key = -1 OR room_key = -1
UNION ALL SELECT 'fin.recon_revenue_to_gl', 'variances to investigate, no note yet',
                 COUNT(*) FROM rpt.vw_recon_revenue_to_gl WHERE [status] = 'Investigate' AND cause IS NULL;

GO