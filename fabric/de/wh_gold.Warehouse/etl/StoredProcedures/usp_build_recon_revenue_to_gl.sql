-- ---------------------------------------------------------------------------
-- Revenue-to-ledger reconciliation, rebuilt every run from Gold.
--   Single tickets  Tessitura net sales, not returned, by order month  vs GL 4100
--   Subscriptions   Tessitura packages by purchase month              vs GL 4110
--   Contributions   Tessitura gifts by gift month and fund            vs GL 4200 by fund
--   Venue rentals   Diese rental fees, not cancelled, by event month   vs GL 4300
-- Tolerance: $1,000 or 1% of the source amount, whichever is larger. The controller sets
-- materiality; change both numbers in the SELECT below if theirs differs.
-- Only months the ledger covers are compared (the current month is still being posted).
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_build_recon_revenue_to_gl @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @first date, @last date, @last_day date, @ins int;
    SELECT @first = MIN(d.[date]), @last = MAX(d.[date])
    FROM fin.fact_gl_entry AS g JOIN dim.[date] AS d ON d.date_key = g.effective_date_key
    WHERE g.source_module = 'TESSITURA';
    SET @last_day = @last;                       -- the ledger's latest posting; later bookings aren't invoiced yet
    SET @first = DATEFROMPARTS(YEAR(@first), MONTH(@first), 1);
    SET @last  = DATEFROMPARTS(YEAR(@last), MONTH(@last), 1);

    -- Source and ledger totals at the same grain: month x revenue stream x fund.
    DROP TABLE IF EXISTS etl.stg_recon_src;
    CREATE TABLE etl.stg_recon_src AS

        SELECT DATEFROMPARTS(d.calendar_year, d.month_num, 1) AS month_start, 'Single tickets' AS revenue_stream,
               'GEN' AS fund_code, 'Tessitura' AS source_system, '4100' AS gl_account_code, SUM(t.net_amount) AS amount
        FROM fact.ticket_sales AS t JOIN dim.[date] AS d ON d.date_key = t.order_date_key
        WHERE t.is_returned = 0
        GROUP BY d.calendar_year, d.month_num
        UNION ALL
        SELECT DATEFROMPARTS(d.calendar_year, d.month_num, 1), 'Subscriptions', 'GEN', 'Tessitura', '4110', SUM(s.package_amount)
        FROM fact.subscriptions AS s JOIN dim.[date] AS d ON d.date_key = s.purchase_date_key
        GROUP BY d.calendar_year, d.month_num
        UNION ALL
        SELECT DATEFROMPARTS(d.calendar_year, d.month_num, 1), 'Contributions', ISNULL(f.mip_fund_code, 'N/A'), 'Tessitura', '4200', SUM(g.amount)
        FROM fact.gifts AS g JOIN dim.[date] AS d ON d.date_key = g.gift_date_key
        JOIN dim.fund AS f ON f.fund_key = g.fund_key
        GROUP BY d.calendar_year, d.month_num, f.mip_fund_code
        UNION ALL
        SELECT DATEFROMPARTS(d.calendar_year, d.month_num, 1), 'Venue rentals', 'GEN', 'Diese', '4300', SUM(b.rental_fee)
        FROM fact.venue_booking AS b JOIN dim.event AS e ON e.event_key = b.event_key
        JOIN dim.[date] AS d ON d.date_key = b.booking_date_key
        WHERE e.event_type = 'Rental' AND e.[status] <> 'Cancelled' AND d.[date] <= @last_day
        GROUP BY d.calendar_year, d.month_num;

    DROP TABLE IF EXISTS etl.stg_recon_gl;
    CREATE TABLE etl.stg_recon_gl AS

        SELECT DATEFROMPARTS(d.calendar_year, d.month_num, 1) AS month_start,
               CASE a.account_code WHEN '4100' THEN 'Single tickets' WHEN '4110' THEN 'Subscriptions'
                                   WHEN '4200' THEN 'Contributions' ELSE 'Venue rentals' END AS revenue_stream,
               CASE WHEN a.account_code = '4200' THEN ISNULL(f.mip_fund_code, 'N/A') ELSE 'GEN' END AS fund_code,
               CASE WHEN a.account_code = '4300' THEN 'Diese' ELSE 'Tessitura' END AS source_system,
               a.account_code AS gl_account_code, SUM(g.net_amount) AS amount
        FROM fin.fact_gl_entry AS g
        JOIN fin.dim_account AS a ON a.account_key = g.account_key
        JOIN dim.[date] AS d ON d.date_key = g.effective_date_key
        LEFT JOIN dim.fund AS f ON f.fund_key = g.fund_key
        WHERE a.account_code IN ('4100', '4110', '4200', '4300')
        GROUP BY d.calendar_year, d.month_num, a.account_code, CASE WHEN a.account_code = '4200' THEN ISNULL(f.mip_fund_code, 'N/A') ELSE 'GEN' END;

    DROP TABLE IF EXISTS etl.stg_recon;
    CREATE TABLE etl.stg_recon AS
    SELECT j.month_start,
           YEAR(j.month_start) + CASE WHEN MONTH(j.month_start) >= 7 THEN 1 ELSE 0 END AS fiscal_year,
           CAST(j.revenue_stream AS varchar(30)) AS revenue_stream, CAST(j.fund_code AS varchar(10)) AS fund_code,
           CAST(j.source_system AS varchar(20)) AS source_system, CAST(j.gl_account_code AS varchar(10)) AS gl_account_code,
           j.source_amount, j.gl_amount,
           CAST(j.gl_amount - j.source_amount AS decimal(16,2)) AS variance,
           CAST(CASE WHEN ABS(j.source_amount) * 0.01 > 1000 THEN ABS(j.source_amount) * 0.01 ELSE 1000 END AS decimal(16,2)) AS tolerance_amount,
           CAST(CASE WHEN ABS(j.gl_amount - j.source_amount) < 0.01 THEN 'Matched'
                     WHEN ABS(j.gl_amount - j.source_amount) <= CASE WHEN ABS(j.source_amount) * 0.01 > 1000
                                                                   THEN ABS(j.source_amount) * 0.01 ELSE 1000 END
                          THEN 'Within tolerance'
                     ELSE 'Investigate' END AS varchar(20)) AS [status],
           CAST(SYSUTCDATETIME() AS datetime2(6)) AS loaded_at,
           n.cause, n.note,
           CAST(ISNULL(n.resolution, CASE WHEN ABS(j.gl_amount - j.source_amount) >
                    CASE WHEN ABS(j.source_amount) * 0.01 > 1000 THEN ABS(j.source_amount) * 0.01 ELSE 1000 END
                    THEN 'Open' END) AS varchar(20)) AS resolution
    FROM (

        SELECT COALESCE(s.month_start, g.month_start) AS month_start,
               COALESCE(s.revenue_stream, g.revenue_stream) AS revenue_stream,
               COALESCE(s.fund_code, g.fund_code) AS fund_code,
               COALESCE(s.source_system, g.source_system) AS source_system,
               COALESCE(s.gl_account_code, g.gl_account_code) AS gl_account_code,
               CAST(ISNULL(s.amount, 0) AS decimal(16,2)) AS source_amount,
               CAST(ISNULL(g.amount, 0) AS decimal(16,2)) AS gl_amount
        FROM etl.stg_recon_src AS s
        FULL OUTER JOIN etl.stg_recon_gl AS g ON g.month_start = s.month_start AND g.revenue_stream = s.revenue_stream
                               AND g.fund_code = s.fund_code
    ) AS j
    LEFT JOIN fin.recon_note AS n ON n.month_start = j.month_start AND n.revenue_stream = j.revenue_stream
                                 AND n.fund_code = j.fund_code
    WHERE j.month_start BETWEEN @first AND @last;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fin.recon_revenue_to_gl;
            INSERT INTO fin.recon_revenue_to_gl SELECT * FROM etl.stg_recon;
            SET @ins = @@ROWCOUNT;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_build_recon_revenue_to_gl', 'fin.recon_revenue_to_gl', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;
    DECLARE @open int = (SELECT COUNT(*) FROM fin.recon_revenue_to_gl WHERE [status] = 'Investigate');
    DECLARE @note varchar(200) = CONCAT(@open, ' month/stream/fund row(s) to investigate');
    EXEC etl.usp_log @run_id, 'etl.usp_build_recon_revenue_to_gl', 'fin.recon_revenue_to_gl', @ins, 0, 0, 'Succeeded', @note, @started;
END;

GO