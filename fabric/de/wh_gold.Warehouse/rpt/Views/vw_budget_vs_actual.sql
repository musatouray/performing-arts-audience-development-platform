-- ---------------------------------------------------------------------------
-- Views for SQL users and Excel (the semantic model reads the tables)
-- ---------------------------------------------------------------------------
-- Budget vs actual by month and account. Variance is favourable when positive:
-- revenue above budget, or expenses below it.
CREATE   VIEW rpt.vw_budget_vs_actual AS
WITH act AS (
    SELECT dd.fiscal_year, DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1) AS month_start, g.account_key,
           SUM(CASE WHEN a.account_type = 'Revenue' THEN g.net_amount ELSE -g.net_amount END) AS actual
    FROM fin.fact_gl_entry AS g
    JOIN fin.dim_account AS a ON a.account_key = g.account_key
    JOIN dim.[date] AS dd ON dd.date_key = g.effective_date_key
    WHERE a.account_type IN ('Revenue', 'Expense')
    GROUP BY dd.fiscal_year, DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1), g.account_key
), bud AS (
    SELECT b.fiscal_year, DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1) AS month_start, b.account_key,
           SUM(b.budget_amount) AS budget
    FROM fin.fact_budget AS b
    JOIN dim.[date] AS dd ON dd.date_key = b.date_key
    GROUP BY b.fiscal_year, DATEFROMPARTS(YEAR(dd.[date]), MONTH(dd.[date]), 1), b.account_key
)
SELECT COALESCE(act.fiscal_year, bud.fiscal_year) AS fiscal_year,
       COALESCE(act.month_start, bud.month_start) AS month_start,
       a.account_type, a.account_group, a.account_name,
       CAST(ISNULL(act.actual, 0) AS decimal(18,2)) AS actual,
       CAST(ISNULL(bud.budget, 0) AS decimal(18,2)) AS budget,
       CAST(CASE WHEN a.account_type = 'Revenue' THEN ISNULL(act.actual, 0) - ISNULL(bud.budget, 0)
                 ELSE ISNULL(bud.budget, 0) - ISNULL(act.actual, 0) END AS decimal(18,2)) AS favourable_variance
FROM act
FULL JOIN bud ON bud.fiscal_year = act.fiscal_year AND bud.month_start = act.month_start AND bud.account_key = act.account_key
JOIN fin.dim_account AS a ON a.account_key = COALESCE(act.account_key, bud.account_key);

GO