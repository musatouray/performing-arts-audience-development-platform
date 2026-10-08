/* =============================================================================
   wh_gold 00: schemas and load logging
   Run the files in order (00 to 60), once per environment, in the Fabric SQL
   editor, SSMS or VS Code.

   Schemas:
     dim    descriptive tables (patrons, performances, dates...)
     fact   measurable events (ticket sales, gifts, subscriptions, sessions)
     rpt    ready-made views for people who query with SQL
     sec    security rules and lookup tables
     etl    load procedures, load log and progress markers
   Silver tables are read directly as [lh_silver].[schema].[table]; nothing is copied.
   Fabric Warehouse has no IDENTITY columns, so keys are numbered as MAX(key) + ROW_NUMBER().
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

-- One row per procedure run. Use it to check whether last night's load worked.
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
    ended_at        datetime2(6)  NULL,
    run_by          varchar(256)  NULL   -- who ran it (a person, or the pipeline's identity)
);
GO

-- How far each incremental load got, so the next run only picks up newer rows.
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
    INSERT INTO etl.load_log (run_id, procedure_name, target_table, rows_inserted, rows_updated, rows_deleted,
                              [status], [message], started_at, ended_at, run_by)
    VALUES (@run_id, @procedure_name, @target_table, @rows_inserted, @rows_updated, @rows_deleted,
            @status, @message, @started_at, SYSUTCDATETIME(), USER_NAME());
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
