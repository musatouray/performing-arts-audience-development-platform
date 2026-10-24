-- Monthly cash flow from Operating Cash (account 1010), with the closing balance.
CREATE   VIEW rpt.vw_cash_flow_monthly AS
WITH m AS (
    SELECT DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1) AS month_start, sm.cash_flow_line, sm.cash_direction,
           SUM(g.debit_amount - g.credit_amount) AS cash_movement
    FROM fin.fact_gl_entry AS g
    JOIN fin.dim_account AS a ON a.account_key = g.account_key AND a.account_code = '1010'
    JOIN dim.[date] AS dd ON dd.date_key = g.effective_date_key
    LEFT JOIN fin.dim_source_module AS sm ON sm.source_module = g.source_module
    GROUP BY DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1), sm.cash_flow_line, sm.cash_direction
)
SELECT m.month_start, m.cash_flow_line, m.cash_direction, CAST(m.cash_movement AS decimal(18,2)) AS cash_movement,
       CAST(SUM(m.cash_movement) OVER (PARTITION BY 1) AS decimal(18,2)) * 0
         + (SELECT CAST(SUM(x.cash_movement) AS decimal(18,2)) FROM m AS x WHERE x.month_start <= m.month_start)
           AS closing_cash_balance             -- cash at the end of the month (same on every line of the month)
FROM m;

GO