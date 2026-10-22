-- ---------------------------------------------------------------------------
-- Load: the ledger, incrementally (journal lines changed since the last run)
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_fact_gl_entry @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @wm datetime2(6), @new_wm datetime2(6), @ins int, @del int;
    EXEC etl.usp_get_watermark 'fin.fact_gl_entry', @wm OUTPUT;
    SELECT @new_wm = MAX(_silver_updated_at) FROM [lh_silver].[mip].[gl_transaction];

    DROP TABLE IF EXISTS etl.stg_gl_entry;
    CREATE TABLE etl.stg_gl_entry AS
    SELECT g.gl_transaction_id, g.journal_id, g.line_number, g.session_id, g.source_module,
           ISNULL(CONVERT(int, CONVERT(varchar(8), g.effective_date, 112)), -1)            AS effective_date_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(g.posted_at AS date), 112)), -1)   AS posted_date_key,
           ISNULL(a.account_key, -1)      AS account_key,
           ISNULL(f.fund_key, -1)         AS fund_key,
           ISNULL(d.department_key, -1)   AS department_key,
           CAST(ISNULL(g.debit_amount, 0)  AS decimal(14,2)) AS debit_amount,
           CAST(ISNULL(g.credit_amount, 0) AS decimal(14,2)) AS credit_amount,
           CAST(ISNULL(g.credit_amount, 0) - ISNULL(g.debit_amount, 0) AS decimal(14,2)) AS net_amount,
           CAST(g.[description] AS varchar(200)) AS [description],
           CAST(g.reference AS varchar(100))     AS reference,
           CAST(SYSUTCDATETIME() AS datetime2(6)) AS loaded_at
    FROM [lh_silver].[mip].[gl_transaction] AS g
    LEFT JOIN fin.dim_account    AS a ON a.account_code = g.account_code
    LEFT JOIN dim.fund           AS f ON f.mip_fund_code = g.fund_code
    LEFT JOIN fin.dim_department AS d ON d.department_code = g.department_code
    WHERE g._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fin.fact_gl_entry WHERE gl_transaction_id IN (SELECT gl_transaction_id FROM etl.stg_gl_entry);
            SET @del = @@ROWCOUNT;
            INSERT INTO fin.fact_gl_entry SELECT * FROM etl.stg_gl_entry;
            SET @ins = @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fin.fact_gl_entry', @new_wm;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gl_entry', 'fin.fact_gl_entry', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;
    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gl_entry', 'fin.fact_gl_entry', @ins, 0, @del, 'Succeeded', NULL, @started;
END;

GO