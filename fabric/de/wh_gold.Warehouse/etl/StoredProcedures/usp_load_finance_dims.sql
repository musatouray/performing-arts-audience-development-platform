-- ---------------------------------------------------------------------------
-- Load: ledger reference data (accounts, departments, fund codes)
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_finance_dims @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @max int, @ins int = 0, @upd int = 0;

    UPDATE t SET account_name = s.account_name, account_type = s.account_type,
                 account_group = s.account_group, normal_balance = s.normal_balance
    FROM fin.dim_account AS t JOIN [lh_silver].[mip].[gl_account] AS s ON t.account_code = s.account_code
    WHERE ISNULL(t.account_name, '') <> ISNULL(s.account_name, '') OR ISNULL(t.account_group, '') <> ISNULL(s.account_group, '');
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(account_key), 0) FROM fin.dim_account WHERE account_key > 0;
    INSERT INTO fin.dim_account
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.account_code), s.account_code, s.account_name, s.account_type,
           s.account_group, s.normal_balance
    FROM [lh_silver].[mip].[gl_account] AS s
    WHERE NOT EXISTS (SELECT 1 FROM fin.dim_account AS t WHERE t.account_code = s.account_code);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM fin.dim_account WHERE account_key = -1)
        INSERT INTO fin.dim_account VALUES (-1, 'N/A', 'Unknown account', 'Unknown', 'Unknown', NULL);

    UPDATE t SET department_name = s.department_name
    FROM fin.dim_department AS t JOIN [lh_silver].[mip].[department] AS s ON t.department_code = s.department_code
    WHERE ISNULL(t.department_name, '') <> ISNULL(s.department_name, '');
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(department_key), 0) FROM fin.dim_department WHERE department_key > 0;
    INSERT INTO fin.dim_department
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.department_code), s.department_code, s.department_name
    FROM [lh_silver].[mip].[department] AS s
    WHERE NOT EXISTS (SELECT 1 FROM fin.dim_department AS t WHERE t.department_code = s.department_code);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM fin.dim_department WHERE department_key = -1)
        INSERT INTO fin.dim_department VALUES (-1, 'N/A', 'Unknown department');

    -- One fund dimension for both systems: finance's crosswalk (mip.fund.tessitura_fund_id)
    -- stamps the ledger code onto the Tessitura fund.
    UPDATE t SET mip_fund_code = s.fund_code
    FROM dim.fund AS t JOIN [lh_silver].[mip].[fund] AS s ON t.fund_id = s.tessitura_fund_id
    WHERE ISNULL(t.mip_fund_code, '') <> s.fund_code;
    SET @upd += @@ROWCOUNT;

    EXEC etl.usp_log @run_id, 'etl.usp_load_finance_dims', 'fin.dim_*', @ins, @upd, 0, 'Succeeded', NULL, @started;
END;

GO