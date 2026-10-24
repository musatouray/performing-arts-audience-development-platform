-- ---------------------------------------------------------------------------
-- Load: rebuilt each run (a few thousand budget lines and eight modules)
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_budget_and_cash @run_id varchar(64)
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