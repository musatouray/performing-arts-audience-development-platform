-- The reconciliation with finance's notes beside each line.
CREATE   VIEW rpt.vw_recon_revenue_to_gl AS
SELECT r.month_start, r.fiscal_year, r.revenue_stream, r.fund_code, r.source_system, r.gl_account_code,
       r.source_amount, r.gl_amount, r.variance, r.tolerance_amount, r.[status],
       n.cause, n.note, ISNULL(n.resolution, CASE WHEN r.[status] = 'Investigate' THEN 'Open' END) AS resolution,
       n.owner_upn, r.loaded_at
FROM fin.recon_revenue_to_gl AS r
LEFT JOIN fin.recon_note AS n ON n.month_start = r.month_start AND n.revenue_stream = r.revenue_stream
                             AND n.fund_code = r.fund_code;

GO