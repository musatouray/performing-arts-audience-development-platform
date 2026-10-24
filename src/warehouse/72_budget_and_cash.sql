/* =============================================================================
   wh_gold 72: budget and cash, for budget vs actual and the cash flow
   Safe to run again. Run after 70, then rerun 40 so the orchestrator
   (etl.usp_load_gold) calls etl.usp_load_budget_and_cash.

   What it adds:
     fin.fact_budget        the adopted budget (MIP budget module) spread to days, so every
                            date filter (FYTD capped at the ledger's last day, prior year,
                            month) works the same way for budget as for actuals
     fin.dim_source_module  what each ledger posting module is, and where its cash lines
                            land on the cash flow (receipts, payments, or non-cash accruals)
     rpt views              budget vs actual by month and account; monthly cash flow

   Cash is read straight from the ledger: Operating Cash (account 1010) moves when
   Tessitura and Diese money comes in and when payroll and payables are paid.
   ============================================================================= */

IF OBJECT_ID('fin.fact_budget') IS NULL
CREATE TABLE fin.fact_budget (
    budget_line_id   varchar(20)    NOT NULL,   -- the MIP budget line (one month)
    date_key         int            NOT NULL,   -- one row per day of that month
    fiscal_year      int            NOT NULL,
    budget_version   varchar(20)    NOT NULL,   -- Adopted
    account_key      int            NOT NULL,
    fund_key         int            NOT NULL,
    department_key   int            NOT NULL,
    budget_amount    decimal(18,4)  NOT NULL,   -- positive for revenue and expense; dim_account says which
    loaded_at        datetime2(6)   NOT NULL
);
GO

IF OBJECT_ID('fin.dim_source_module') IS NULL
CREATE TABLE fin.dim_source_module (
    source_module    varchar(20)   NOT NULL,
    module_name      varchar(60)   NOT NULL,
    cash_flow_line   varchar(60)   NOT NULL,    -- the line it lands on in the cash flow
    cash_direction   varchar(10)   NOT NULL,    -- In, Out, Opening, Non-cash
    sort_order       int           NOT NULL
);
GO

-- ---------------------------------------------------------------------------
-- Load: rebuilt each run (a few thousand budget lines and eight modules)
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_budget_and_cash @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @ins int = 0, @del int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fin.dim_source_module;
            INSERT INTO fin.dim_source_module VALUES
                ('OPENING',         'Opening balance',             'Opening balance',                     'Opening',  0),
                ('TESSITURA',       'Tessitura postings',          'Tickets, subscriptions and gifts',    'In',       1),
                ('DIESE',           'Diese rental invoices',       'Hall rental fees',                    'In',       2),
                ('PAYROLL_PAYMENT', 'Payroll payments',            'Payroll',                             'Out',      3),
                ('AP_PAYMENT',      'Payables payments',           'Artists, suppliers and operations',   'Out',      4),
                ('PAYROLL',         'Payroll accrual',             'Non-cash accruals',                   'Non-cash', 9),
                ('AP',              'Payables accrual',            'Non-cash accruals',                   'Non-cash', 9),
                ('MANUAL',          'Manual journal',              'Non-cash accruals',                   'Non-cash', 9);

            DELETE FROM fin.fact_budget;
            SET @del = @@ROWCOUNT;
            INSERT INTO fin.fact_budget
            SELECT b.budget_line_id, d.date_key, b.fiscal_year, b.budget_version,
                   ISNULL(a.account_key, -1), ISNULL(f.fund_key, -1), ISNULL(dp.department_key, -1),
                   CAST(b.amount / DAY(EOMONTH(b.period_start)) AS decimal(18,4)),
                   CAST(SYSUTCDATETIME() AS datetime2(6))
            FROM [lh_silver].[mip].[gl_budget] AS b
            JOIN dim.[date] AS d ON d.[date] BETWEEN b.period_start AND EOMONTH(b.period_start)
            LEFT JOIN fin.dim_account    AS a  ON a.account_code = b.account_code
            LEFT JOIN dim.fund           AS f  ON f.mip_fund_code = b.fund_code
            LEFT JOIN fin.dim_department AS dp ON dp.department_code = b.department_code
            WHERE b.budget_version = 'Adopted';
            SET @ins = @@ROWCOUNT;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_budget_and_cash', 'fin.fact_budget', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;
    EXEC etl.usp_log @run_id, 'etl.usp_load_budget_and_cash', 'fin.fact_budget', @ins, 0, @del, 'Succeeded', NULL, @started;
END;
GO

-- ---------------------------------------------------------------------------
-- Views for SQL users and Excel (the semantic model reads the tables)
-- ---------------------------------------------------------------------------
-- Budget vs actual by month and account. Variance is favourable when positive:
-- revenue above budget, or expenses below it.
CREATE OR ALTER VIEW rpt.vw_budget_vs_actual AS
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

-- Monthly cash flow from Operating Cash (account 1010), with the closing balance.
CREATE OR ALTER VIEW rpt.vw_cash_flow_monthly AS
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

-- ---------------------------------------------------------------------------
-- Access: finance analysts read budget and cash like the rest of fin (ADR-006)
-- ---------------------------------------------------------------------------
GRANT SELECT ON OBJECT::rpt.vw_budget_vs_actual  TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_cash_flow_monthly TO [sg-hh-analysts-finance];
GO
