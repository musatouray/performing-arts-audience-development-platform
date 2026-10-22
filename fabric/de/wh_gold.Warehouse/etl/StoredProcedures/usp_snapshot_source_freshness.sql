CREATE   PROCEDURE etl.usp_snapshot_source_freshness @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @ins int;
    DELETE FROM rpt.source_freshness;
    INSERT INTO rpt.source_freshness
    SELECT source_system, source_name, CAST(last_loaded_utc AS datetime2(6)), data_through, measured_by,
           CAST(SYSUTCDATETIME() AS datetime2(6))
    FROM rpt.vw_source_freshness;
    SET @ins = @@ROWCOUNT;
    EXEC etl.usp_log @run_id, 'etl.usp_snapshot_source_freshness', 'rpt.source_freshness', @ins, 0, 0, 'Succeeded', NULL, @started;
END;

GO