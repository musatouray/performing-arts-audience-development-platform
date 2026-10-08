-- ---------------------------------------------------------------------------
-- The one procedure the pipeline calls. It loads dimensions first, then facts.
-- The pipeline passes its run ID so every log row can be traced back to one run.
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_gold @run_id varchar(64) = NULL
AS
BEGIN
    SET @run_id = ISNULL(@run_id, CONVERT(varchar(64), NEWID()));
    DECLARE @started datetime2(6) = SYSUTCDATETIME();

    -- If any step fails, stop here, record it and fail the pipeline.
    -- Without this, a step that hits a missing table or column is skipped
    -- and the remaining steps carry on as if nothing happened.
    BEGIN TRY
        IF NOT EXISTS (SELECT 1 FROM dim.[date]) EXEC etl.usp_load_dim_date;
        EXEC etl.usp_load_dim_reference @run_id;
        EXEC etl.usp_load_dim_patron @run_id;          -- facts need the dimension keys, so dimensions load first
        EXEC etl.usp_load_fact_ticket_sales @run_id;
        EXEC etl.usp_load_fact_gifts @run_id;
        EXEC etl.usp_load_fact_subscriptions_and_education @run_id;
    END TRY
    BEGIN CATCH
        DECLARE @msg varchar(4000) = CONCAT(ERROR_PROCEDURE(), ': ', ERROR_MESSAGE());
        EXEC etl.usp_log @run_id, 'etl.usp_load_gold', NULL, 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;

    SELECT * FROM etl.load_log WHERE run_id = @run_id ORDER BY started_at;
END;

GO