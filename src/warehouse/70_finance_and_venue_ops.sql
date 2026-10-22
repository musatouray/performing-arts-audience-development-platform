/* =============================================================================
   wh_gold 70: finance (MIP general ledger) and venue operations (Diese bookings)
   Safe to run again: existing schemas and tables are kept.
   Gold for two spokes (ADR-009): Finance (CFO office) and Operations (Hall Operations,
   Event Services, Rentals). Run after 00-60, then rerun 40 so the orchestrator
   (etl.usp_load_gold) calls the new procedures.

   What it adds:
     fin.dim_account, fin.dim_department     the ledger's chart of accounts and departments
     dim.fund.mip_fund_code                  one fund dimension for Tessitura AND the ledger
     fin.fact_gl_entry                       one row per journal line
     dim.room, dim.event, fact.venue_booking hall calendar; dim.event links a booking to its
                                             Tessitura performance when there is one
     fin.recon_revenue_to_gl                 box office and Diese revenue vs the ledger, by month,
                                             revenue stream and fund, with a pass/fail status
     fin.recon_note                          where finance explains a variance (who, why, status)
     rpt views                               income statement, reconciliation, hall utilisation,
                                             finance integrity checks

   Why the reconciliation is a table and not a view: it's computed by the load, which
   runs as the ETL identity and so sees every gift, anonymous ones included. People only
   ever see monthly totals by fund, so the totals are complete without exposing anyone.
   ============================================================================= */

IF SCHEMA_ID('fin') IS NULL EXEC('CREATE SCHEMA fin');   -- safe to re-run
GO

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
-- dim.fund gets the ledger's code for each fund (set by etl.usp_load_finance_dims).
-- Fabric Warehouse doesn't support COL_LENGTH, so the check reads sys.columns instead.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dim.fund') AND name = 'mip_fund_code')
    ALTER TABLE dim.fund ADD mip_fund_code varchar(10) NULL;
GO

IF OBJECT_ID('fin.dim_account') IS NULL
CREATE TABLE fin.dim_account (
    account_key     int           NOT NULL,
    account_code    varchar(10)   NOT NULL,
    account_name    varchar(100)  NULL,
    account_type    varchar(20)   NULL,    -- Asset, Liability, Revenue, Expense
    account_group   varchar(50)   NULL,    -- Earned Revenue, Contributed Revenue, Personnel ...
    normal_balance  varchar(10)   NULL     -- Debit or Credit
);
GO

IF OBJECT_ID('fin.dim_department') IS NULL
CREATE TABLE fin.dim_department (
    department_key   int           NOT NULL,
    department_code  varchar(10)   NOT NULL,
    department_name  varchar(100)  NULL
);
GO

-- One row per journal line. net_amount = credit - debit, so revenue is positive and
-- expenses are negative; the income statement view flips expenses for reading.
IF OBJECT_ID('fin.fact_gl_entry') IS NULL
CREATE TABLE fin.fact_gl_entry (
    gl_transaction_id   varchar(20)    NOT NULL,
    journal_id          varchar(20)    NOT NULL,
    line_number         int            NULL,
    session_id          varchar(40)    NULL,   -- the posting batch, e.g. TESS-20250314
    source_module       varchar(20)    NULL,   -- TESSITURA, DIESE, PAYROLL, AP, MANUAL
    effective_date_key  int            NOT NULL,
    posted_date_key     int            NOT NULL,
    account_key         int            NOT NULL,
    fund_key            int            NOT NULL,
    department_key      int            NOT NULL,
    debit_amount        decimal(14,2)  NOT NULL,
    credit_amount       decimal(14,2)  NOT NULL,
    net_amount          decimal(14,2)  NOT NULL,
    [description]       varchar(200)   NULL,
    reference           varchar(100)   NULL,
    loaded_at           datetime2(6)   NOT NULL
);
GO

IF OBJECT_ID('dim.room') IS NULL
CREATE TABLE dim.room (
    room_key     int            NOT NULL,
    room_id      varchar(10)    NOT NULL,
    room_name    varchar(100)   NULL,
    room_type    varchar(30)    NULL,    -- Hall, Rehearsal, Event Space
    venue_key    int            NOT NULL,  -- the Tessitura venue for halls, -1 for other rooms
    capacity     int            NULL,
    hourly_rate  decimal(10,2)  NULL
);
GO

-- The bridge between the booking system and ticketing. Many events (rentals,
-- rehearsals) have no performance, so performance_key = -1 is normal for them.
IF OBJECT_ID('dim.event') IS NULL
CREATE TABLE dim.event (
    event_key         int           NOT NULL,
    event_id          varchar(20)   NOT NULL,
    event_name        varchar(300)  NULL,
    event_type        varchar(20)   NULL,   -- Concert, Rental, Rehearsal
    client_name       varchar(200)  NULL,   -- private clients are people: finance-only (see grants below)
    client_type       varchar(20)   NULL,
    [status]          varchar(20)   NULL,
    event_date_key    int           NOT NULL,
    performance_key   int           NOT NULL,
    is_linked         bit           NOT NULL  -- 1 when the Tessitura performance was found
);
GO

-- One row per room booking (a rehearsal, a performance, a rental).
IF OBJECT_ID('fact.venue_booking') IS NULL
CREATE TABLE fact.venue_booking (
    booking_id        varchar(30)    NOT NULL,
    event_key         int            NOT NULL,
    room_key          int            NOT NULL,
    venue_key         int            NOT NULL,
    booking_date_key  int            NOT NULL,
    booking_type      varchar(20)    NULL,   -- Rehearsal, Performance, Event
    start_datetime    datetime2(6)   NULL,
    end_datetime      datetime2(6)   NULL,
    hours_booked      decimal(6,2)   NOT NULL,
    rental_fee        decimal(12,2)  NOT NULL,
    loaded_at         datetime2(6)   NOT NULL
);
GO

IF OBJECT_ID('fin.recon_revenue_to_gl') IS NULL
CREATE TABLE fin.recon_revenue_to_gl (
    month_start       date           NOT NULL,
    fiscal_year       int            NOT NULL,
    revenue_stream    varchar(30)    NOT NULL,   -- Single tickets, Subscriptions, Contributions, Venue rentals
    fund_code         varchar(10)    NOT NULL,
    source_system     varchar(20)    NOT NULL,   -- Tessitura or Diese
    gl_account_code   varchar(10)    NOT NULL,
    source_amount     decimal(16,2)  NOT NULL,
    gl_amount         decimal(16,2)  NOT NULL,
    variance          decimal(16,2)  NOT NULL,   -- ledger minus source
    tolerance_amount  decimal(16,2)  NOT NULL,
    [status]          varchar(20)    NOT NULL,   -- Matched, Within tolerance, Investigate
    loaded_at         datetime2(6)   NOT NULL,
    -- finance's explanation, copied from fin.recon_note at load time so Direct Lake models
    -- (which read tables, not views) can show it; rpt.vw_recon_revenue_to_gl shows it live
    cause             varchar(50)    NULL,
    note              varchar(1000)  NULL,
    resolution        varchar(20)    NULL
);
GO

-- Finance writes here when they've looked at a variance. Kept separate from the
-- computed table, so a reload never wipes their notes.
IF OBJECT_ID('fin.recon_note') IS NULL
CREATE TABLE fin.recon_note (
    month_start     date           NOT NULL,
    revenue_stream  varchar(30)    NOT NULL,
    fund_code       varchar(10)    NOT NULL,
    cause           varchar(50)    NULL,   -- Timing (cut-off), Unposted batch, Reclass, Source error ...
    note            varchar(1000)  NULL,
    resolution      varchar(20)    NULL,   -- Open, Explained, Corrected
    owner_upn       varchar(256)   NULL,
    noted_at        datetime2(6)   NULL
);
GO

-- ---------------------------------------------------------------------------
-- Load: ledger reference data (accounts, departments, fund codes)
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_finance_dims @run_id varchar(64)
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

-- ---------------------------------------------------------------------------
-- Load: the ledger, incrementally (journal lines changed since the last run)
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_fact_gl_entry @run_id varchar(64)
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

-- ---------------------------------------------------------------------------
-- Load: the hall calendar. Small (a few thousand rows a year), so the bookings
-- fact is rebuilt each run; events keep their keys so reports stay stable.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_load_venue_ops @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @max int, @ins int = 0, @upd int = 0, @del int = 0;

    /* ---- room (halls point at the Tessitura venue) ---- */
    UPDATE t SET room_name = s.room_name, room_type = s.room_type, venue_key = ISNULL(v.venue_key, -1),
                 capacity = s.capacity, hourly_rate = s.hourly_rate
    FROM dim.room AS t JOIN [lh_silver].[diese].[room] AS s ON t.room_id = s.room_id
    LEFT JOIN dim.venue AS v ON v.venue_id = s.venue_id
    WHERE ISNULL(t.room_name, '') <> ISNULL(s.room_name, '') OR ISNULL(t.hourly_rate, -1) <> ISNULL(s.hourly_rate, -1)
       OR ISNULL(t.capacity, -1) <> ISNULL(s.capacity, -1);
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(room_key), 0) FROM dim.room WHERE room_key > 0;
    INSERT INTO dim.room
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.room_id), s.room_id, s.room_name, s.room_type,
           ISNULL(v.venue_key, -1), s.capacity, s.hourly_rate
    FROM [lh_silver].[diese].[room] AS s
    LEFT JOIN dim.venue AS v ON v.venue_id = s.venue_id
    WHERE NOT EXISTS (SELECT 1 FROM dim.room AS t WHERE t.room_id = s.room_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.room WHERE room_key = -1)
        INSERT INTO dim.room VALUES (-1, 'N/A', 'Unknown room', 'Unknown', -1, NULL, NULL);

    /* ---- event (the bridge to ticketing) ---- */
    WITH src AS (
        SELECT e.event_id, e.event_name, e.event_type, e.client_name, e.client_type, e.[status],
               ISNULL(CONVERT(int, CONVERT(varchar(8), e.event_date, 112)), -1) AS event_date_key,
               ISNULL(p.performance_key, -1) AS performance_key,
               CAST(CASE WHEN p.performance_key IS NOT NULL THEN 1 ELSE 0 END AS bit) AS is_linked
        FROM [lh_silver].[diese].[event] AS e
        LEFT JOIN dim.performance AS p ON p.performance_id = e.tessitura_performance_id
    )
    UPDATE t SET event_name = s.event_name, event_type = s.event_type, client_name = s.client_name,
                 client_type = s.client_type, [status] = s.[status], event_date_key = s.event_date_key,
                 performance_key = s.performance_key, is_linked = s.is_linked
    FROM dim.event AS t JOIN src AS s ON t.event_id = s.event_id
    WHERE ISNULL(t.[status], '') <> ISNULL(s.[status], '') OR t.event_date_key <> s.event_date_key
       OR t.performance_key <> s.performance_key OR ISNULL(t.event_name, '') <> ISNULL(s.event_name, '');
    SET @upd += @@ROWCOUNT;
    SELECT @max = ISNULL(MAX(event_key), 0) FROM dim.event WHERE event_key > 0;
    INSERT INTO dim.event
    SELECT @max + ROW_NUMBER() OVER (ORDER BY e.event_id), e.event_id, e.event_name, e.event_type, e.client_name,
           e.client_type, e.[status], ISNULL(CONVERT(int, CONVERT(varchar(8), e.event_date, 112)), -1),
           ISNULL(p.performance_key, -1), CAST(CASE WHEN p.performance_key IS NOT NULL THEN 1 ELSE 0 END AS bit)
    FROM [lh_silver].[diese].[event] AS e
    LEFT JOIN dim.performance AS p ON p.performance_id = e.tessitura_performance_id
    WHERE NOT EXISTS (SELECT 1 FROM dim.event AS t WHERE t.event_id = e.event_id);
    SET @ins += @@ROWCOUNT;
    IF NOT EXISTS (SELECT 1 FROM dim.event WHERE event_key = -1)
        INSERT INTO dim.event VALUES (-1, 'N/A', 'Unknown event', 'Unknown', NULL, NULL, NULL, -1, -1, 0);

    /* ---- venue_booking (rebuilt) ---- */
    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.venue_booking;
            SET @del = @@ROWCOUNT;
            INSERT INTO fact.venue_booking
            SELECT b.booking_id, ISNULL(e.event_key, -1), ISNULL(r.room_key, -1), ISNULL(r.venue_key, -1),
                   ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(b.start_datetime AS date), 112)), -1),
                   b.booking_type, CAST(b.start_datetime AS datetime2(6)), CAST(b.end_datetime AS datetime2(6)),
                   CAST(DATEDIFF(minute, b.start_datetime, b.end_datetime) / 60.0 AS decimal(6,2)),
                   CAST(ISNULL(b.rental_fee, 0) AS decimal(12,2)),
                   CAST(SYSUTCDATETIME() AS datetime2(6))
            FROM [lh_silver].[diese].[booking] AS b
            LEFT JOIN dim.event AS e ON e.event_id = b.event_id
            LEFT JOIN dim.room  AS r ON r.room_id = b.room_id;
            SET @ins += @@ROWCOUNT;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_venue_ops', 'fact.venue_booking', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;
    EXEC etl.usp_log @run_id, 'etl.usp_load_venue_ops', 'dim.room+dim.event+fact.venue_booking', @ins, @upd, @del, 'Succeeded', NULL, @started;
END;
GO

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
CREATE OR ALTER PROCEDURE etl.usp_build_recon_revenue_to_gl @run_id varchar(64)
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

-- ---------------------------------------------------------------------------
-- Views for people who query with SQL (and the finance model's Data Trust page)
-- ---------------------------------------------------------------------------

-- Income statement lines: revenue positive, expenses positive (as people read them).
CREATE OR ALTER VIEW rpt.vw_income_statement AS
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

-- The reconciliation with finance's notes beside each line.
CREATE OR ALTER VIEW rpt.vw_recon_revenue_to_gl AS
SELECT r.month_start, r.fiscal_year, r.revenue_stream, r.fund_code, r.source_system, r.gl_account_code,
       r.source_amount, r.gl_amount, r.variance, r.tolerance_amount, r.[status],
       n.cause, n.note, ISNULL(n.resolution, CASE WHEN r.[status] = 'Investigate' THEN 'Open' END) AS resolution,
       n.owner_upn, r.loaded_at
FROM fin.recon_revenue_to_gl AS r
LEFT JOIN fin.recon_note AS n ON n.month_start = r.month_start AND n.revenue_stream = r.revenue_stream
                             AND n.fund_code = r.fund_code;
GO

-- Hall and room use by month: hours booked by type, and share of the available hours
-- (14 bookable hours a day, 9am to 11pm).
CREATE OR ALTER VIEW rpt.vw_room_utilisation AS
SELECT r.room_name, r.room_type, d.fiscal_year, d.calendar_year, d.month_num, d.month_name,
       SUM(CASE WHEN e.event_type = 'Concert'   THEN b.hours_booked ELSE 0 END) AS concert_hours,
       SUM(CASE WHEN e.event_type = 'Rental'    THEN b.hours_booked ELSE 0 END) AS rental_hours,
       SUM(CASE WHEN e.event_type = 'Rehearsal' THEN b.hours_booked ELSE 0 END) AS rehearsal_hours,
       SUM(b.hours_booked) AS hours_booked,
       14.0 * DAY(EOMONTH(MIN(d.[date]))) AS hours_available,
       CAST(SUM(b.hours_booked) / (14.0 * DAY(EOMONTH(MIN(d.[date])))) AS decimal(6,3)) AS utilisation,
       SUM(CASE WHEN e.event_type = 'Rental' THEN b.rental_fee ELSE 0 END) AS rental_revenue
FROM fact.venue_booking AS b
JOIN dim.event AS e ON e.event_key = b.event_key
JOIN dim.room  AS r ON r.room_key = b.room_key
JOIN dim.[date] AS d ON d.date_key = b.booking_date_key
WHERE e.[status] <> 'Cancelled' AND b.hours_booked > 0
GROUP BY r.room_name, r.room_type, d.fiscal_year, d.calendar_year, d.month_num, d.month_name;
GO

CREATE OR ALTER VIEW rpt.vw_finance_integrity AS
SELECT 'fin.fact_gl_entry' AS fact_table, 'unbalanced journals' AS check_name,
       COUNT(*) AS rows_failing FROM (SELECT journal_id FROM fin.fact_gl_entry GROUP BY journal_id
                                       HAVING SUM(debit_amount) <> SUM(credit_amount)) AS j
UNION ALL SELECT 'fin.fact_gl_entry', 'unknown account',  COUNT(*) FROM fin.fact_gl_entry WHERE account_key = -1
UNION ALL SELECT 'fin.fact_gl_entry', 'unknown fund',     COUNT(*) FROM fin.fact_gl_entry WHERE fund_key = -1
UNION ALL SELECT 'dim.fund', 'Tessitura fund with no ledger code', COUNT(*) FROM dim.fund WHERE fund_key > 0 AND mip_fund_code IS NULL
UNION ALL SELECT 'dim.event', 'concert not linked to a performance',
                 COUNT(*) FROM dim.event WHERE event_type = 'Concert' AND is_linked = 0
UNION ALL SELECT 'fact.venue_booking', 'unknown event or room',
                 COUNT(*) FROM fact.venue_booking WHERE event_key = -1 OR room_key = -1
UNION ALL SELECT 'fin.recon_revenue_to_gl', 'variances to investigate, no note yet',
                 COUNT(*) FROM rpt.vw_recon_revenue_to_gl WHERE [status] = 'Investigate' AND cause IS NULL;
GO

-- ---------------------------------------------------------------------------
-- Access. Create the Entra groups sg-hh-analysts-finance and sg-hh-analysts-operations
-- first (scripts/00).
--   Finance     the ledger, the reconciliation and its notes, plus read access to the
--               hall calendar, to trace a rental variance back to the event behind it.
--   Operations  the hall calendar, room use and rental fees. Nothing from the ledger.
-- Client names in dim.event can name private people, so only these two groups get it.
-- ---------------------------------------------------------------------------
GRANT SELECT ON SCHEMA::fin TO [sg-hh-analysts-finance];
GRANT INSERT, UPDATE ON OBJECT::fin.recon_note TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::dim.event          TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::dim.room           TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::fact.venue_booking TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::dim.[date]         TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::dim.fund           TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::dim.venue          TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_income_statement     TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_recon_revenue_to_gl  TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_room_utilisation     TO [sg-hh-analysts-finance];
GRANT SELECT ON OBJECT::rpt.vw_finance_integrity    TO [sg-hh-analysts-finance];
DENY  SELECT ON SCHEMA::etl TO [sg-hh-analysts-finance];

GRANT SELECT ON OBJECT::dim.event          TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::dim.room           TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::fact.venue_booking TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::dim.[date]         TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::dim.venue          TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::dim.performance    TO [sg-hh-analysts-operations];
GRANT SELECT ON OBJECT::rpt.vw_room_utilisation     TO [sg-hh-analysts-operations];
DENY  SELECT ON SCHEMA::fin TO [sg-hh-analysts-operations];
DENY  SELECT ON SCHEMA::etl TO [sg-hh-analysts-operations];

DENY  SELECT ON SCHEMA::fin TO [sg-hh-analysts-audience];
DENY  SELECT ON SCHEMA::fin TO [sg-hh-analysts-development];
GO
