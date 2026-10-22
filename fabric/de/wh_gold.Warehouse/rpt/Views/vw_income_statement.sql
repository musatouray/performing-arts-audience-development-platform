-- ---------------------------------------------------------------------------
-- Views for people who query with SQL (and the finance model's Data Trust page)
-- ---------------------------------------------------------------------------

-- Income statement lines: revenue positive, expenses positive (as people read them).
CREATE   VIEW rpt.vw_income_statement AS
SELECT d.fiscal_year, d.fiscal_year_label, d.fiscal_month_num, d.month_name,
       a.account_type, a.account_group, a.account_code, a.account_name,
       dp.department_name, f.mip_fund_code AS fund_code, f.fund_name,
       SUM(CASE WHEN a.account_type = 'Expense' THEN -g.net_amount ELSE g.net_amount END) AS amount
FROM fin.fact_gl_entry AS g
JOIN fin.dim_account    AS a  ON a.account_key = g.account_key
JOIN fin.dim_department AS dp ON dp.department_key = g.department_key
JOIN dim.fund           AS f  ON f.fund_key = g.fund_key
JOIN dim.[date]         AS d  ON d.date_key = g.effective_date_key
WHERE a.account_type IN ('Revenue', 'Expense')
GROUP BY d.fiscal_year, d.fiscal_year_label, d.fiscal_month_num, d.month_name, a.account_type, a.account_group,
         a.account_code, a.account_name, dp.department_name, f.mip_fund_code, f.fund_name;

GO