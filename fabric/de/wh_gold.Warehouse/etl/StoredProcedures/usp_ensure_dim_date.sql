-- ---------------------------------------------------------------------------
-- dim.date covers exactly the fiscal years the data needs: from the fiscal year of the
-- first sale or ledger entry to the fiscal year of the latest of today, the last
-- scheduled performance and the last budgeted month. So slicers only offer real years,
-- and time intelligence still gets whole, unbroken fiscal years. Rebuilt only when
-- that range changes (a new fiscal year starts, or next year's budget arrives).
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_ensure_dim_date
AS
BEGIN
    DECLARE @first date, @last date, @start date, @end date;
    SELECT @first = MIN(d) FROM (
        SELECT MIN(CAST(order_datetime AS date)) AS d FROM [lh_silver].[tessitura].[order]
        UNION ALL SELECT MIN(effective_date) FROM [lh_silver].[mip].[gl_transaction]) AS x;
    SELECT @last = MAX(d) FROM (
        SELECT CAST(SYSUTCDATETIME() AS date) AS d
        UNION ALL SELECT MAX(CAST(performance_datetime AS date)) FROM [lh_silver].[tessitura].[performance]
        UNION ALL SELECT MAX(effective_date) FROM [lh_silver].[mip].[gl_transaction]
        UNION ALL SELECT EOMONTH(MAX(period_start)) FROM [lh_silver].[mip].[gl_budget]) AS y;
    SET @first = ISNULL(@first, CAST(SYSUTCDATETIME() AS date));
    -- Fiscal year July-June: FY2026 runs from 1 July 2025 to 30 June 2026.
    SET @start = DATEFROMPARTS(YEAR(@first) - CASE WHEN MONTH(@first) >= 7 THEN 0 ELSE 1 END, 7, 1);
    SET @end   = DATEFROMPARTS(YEAR(@last)  + CASE WHEN MONTH(@last)  >= 7 THEN 1 ELSE 0 END, 6, 30);
    IF NOT EXISTS (SELECT 1 FROM dim.[date] WHERE date_key > 0 HAVING MIN([date]) = @start AND MAX([date]) = @end)
        EXEC etl.usp_load_dim_date @start, @end;
END;

GO