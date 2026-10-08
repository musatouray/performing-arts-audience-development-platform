CREATE   PROCEDURE etl.usp_log
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