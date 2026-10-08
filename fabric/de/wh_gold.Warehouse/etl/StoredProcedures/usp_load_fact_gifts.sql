CREATE   PROCEDURE etl.usp_load_fact_gifts @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @wm datetime2(6), @new_wm datetime2(6), @del int, @ins int;
    EXEC etl.usp_get_watermark 'fact.gifts', @wm OUTPUT;
    SELECT @new_wm = MAX(_silver_updated_at) FROM [lh_silver].[fundraising].[gifts];

    DROP TABLE IF EXISTS etl.stg_gifts;
    CREATE TABLE etl.stg_gifts AS
    SELECT g.gift_id,
           ISNULL(p.patron_key, -1)   AS patron_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), g.gift_date, 112)), -1) AS gift_date_key,
           ISNULL(ca.campaign_key, -1) AS campaign_key,
           ISNULL(f.fund_key, -1)      AS fund_key,
           CAST(ISNULL(g.amount, 0) AS decimal(14,2)) AS amount,
           g.gift_type,
           CAST(ISNULL(g.is_anonymous, 0) AS bit) AS is_anonymous,
           CAST(SYSUTCDATETIME() AS datetime2(6)) AS loaded_at   -- Warehouse only stores up to 6 decimal places
    FROM [lh_silver].[fundraising].[gifts]      AS g
    LEFT JOIN [lh_silver].[core].[patron_xref]  AS x  ON x.source_system = 'fundraising' AND x.source_id = g.donor_id
    LEFT JOIN dim.patron                        AS p  ON p.patron_id = x.patron_id
                                                     AND CAST(g.gift_date AS datetime2(6)) >= p.valid_from
                                                     AND CAST(g.gift_date AS datetime2(6)) <  p.valid_to
    LEFT JOIN dim.campaign                      AS ca ON ca.campaign_id = g.campaign_id
    LEFT JOIN dim.fund                          AS f  ON f.fund_id = g.fund_id
    WHERE g._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.gifts WHERE gift_id IN (SELECT gift_id FROM etl.stg_gifts);
            SET @del = @@ROWCOUNT;
            INSERT INTO fact.gifts SELECT * FROM etl.stg_gifts;
            SET @ins = @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fact.gifts', @new_wm;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gifts', 'fact.gifts', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;

    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_gifts', 'fact.gifts', @ins, 0, @del, 'Succeeded', NULL, @started;
END;

GO