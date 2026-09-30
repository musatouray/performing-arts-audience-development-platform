/* =============================================================================
   wh_gold · 00 — schemas + ETL framework
   Workload : Fabric Warehouse (T-SQL). Run once per environment, in order 00 -> 60.
   Run with : Fabric SQL editor, SSMS or VS Code (mssql). "GO" separates batches.

   Layer contract (Gold):
     dim.*   conformed dimensions, surrogate keys, unknown member = -1
     fact.*  facts at a declared grain, FK = dimension surrogate keys
     rpt.*   business-friendly views (for SQL users / paginated reports)
     sec.*   security predicates + mapping tables (RLS)
     etl.*   procedures, watermarks, load log
   Silver is read via cross-database queries: [lh_silver].[schema].[table]
   (same workspace -> no data copy, no linked service).
   Fabric Warehouse T-SQL notes: varchar (UTF-8) not nvarchar, datetime2 not datetime,
   no IDENTITY -> surrogate keys = MAX(key) + ROW_NUMBER().
   ============================================================================= */

CREATE SCHEMA dim;
GO
CREATE SCHEMA fact;
GO
CREATE SCHEMA rpt;
GO
CREATE SCHEMA sec;
GO
CREATE SCHEMA etl;
GO

-- One row per procedure run: the pipeline-health report and the "did last night's load work?" answer.
CREATE TABLE etl.load_log (
    run_id          varchar(64)   NOT NULL,
    procedure_name  varchar(128)  NOT NULL,
    target_table    varchar(128)  NULL,
    rows_inserted   int           NULL,
    rows_updated    int           NULL,
    rows_deleted    int           NULL,
    status          varchar(20)   NOT NULL,
    message         varchar(4000) NULL,
    started_at      datetime2(6)  NOT NULL,
    ended_at        datetime2(6)  NULL
);
GO

-- High-water marks for incremental fact loads (based on Silver _silver_updated_at).
CREATE TABLE etl.watermark (
    object_name  varchar(128) NOT NULL,
    last_value   datetime2(6) NOT NULL,
    updated_at   datetime2(6) NOT NULL
);
GO

CREATE OR ALTER PROCEDURE etl.usp_log
    @run_id varchar(64), @procedure_name varchar(128), @target_table varchar(128),
    @rows_inserted int, @rows_updated int, @rows_deleted int,
    @status varchar(20), @message varchar(4000), @started_at datetime2(6)
AS
BEGIN
    INSERT INTO etl.load_log
    VALUES (@run_id, @procedure_name, @target_table, @rows_inserted, @rows_updated, @rows_deleted,
            @status, @message, @started_at, SYSUTCDATETIME());
END;
GO

CREATE OR ALTER PROCEDURE etl.usp_get_watermark @object_name varchar(128), @value datetime2(6) OUTPUT
AS
BEGIN
    SELECT @value = MAX(last_value) FROM etl.watermark WHERE object_name = @object_name;
    SET @value = COALESCE(@value, CAST('1900-01-01' AS datetime2(6)));
END;
GO

CREATE OR ALTER PROCEDURE etl.usp_set_watermark @object_name varchar(128), @value datetime2(6)
AS
BEGIN
    DELETE FROM etl.watermark WHERE object_name = @object_name;
    INSERT INTO etl.watermark VALUES (@object_name, @value, SYSUTCDATETIME());
END;
GO
