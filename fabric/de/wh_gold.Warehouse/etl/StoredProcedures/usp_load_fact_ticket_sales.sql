/* =============================================================================
   wh_gold 40: procedures that load the fact tables
   * ticket_sales and gifts load only rows changed since the last run. Changed rows
     are deleted and inserted again in one transaction, which also handles late
     changes such as an order returned three days after it was bought.
   * subscriptions and education_sessions are small, so they're reloaded in full.
   * Each sale or gift links to the patron's details as they were on that date.
   * Anything that can't be matched points to the -1 "Unknown" row instead of being dropped.
   ============================================================================= */

CREATE   PROCEDURE etl.usp_load_fact_ticket_sales @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @wm datetime2(6), @new_wm datetime2(6), @del int, @ins int;
    EXEC etl.usp_get_watermark 'fact.ticket_sales', @wm OUTPUT;

    SELECT @new_wm = MAX(x) FROM (
        SELECT MAX(_silver_updated_at) AS x FROM [lh_silver].[ticketing].[order_lines]
        UNION ALL SELECT MAX(_silver_updated_at) FROM [lh_silver].[ticketing].[orders]) AS t;

    -- Pick up lines that changed, and lines whose order changed (for example, was returned).
    DROP TABLE IF EXISTS etl.stg_ticket_sales;
    CREATE TABLE etl.stg_ticket_sales AS
    SELECT ol.order_line_id, ol.order_id,
           ISNULL(p.patron_key, -1)                         AS patron_key,
           ISNULL(dp.performance_key, -1)                   AS performance_key,
           ISNULL(v.venue_key, -1)                          AS venue_key,
           ISNULL(c.channel_key, -1)                        AS channel_key,
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(o.order_datetime AS date), 112)), -1) AS order_date_key,
           ISNULL(dp.performance_date_key, -1)              AS performance_date_key,
           DATEDIFF(day, o.order_datetime, dp.performance_datetime) AS days_before_show,
           ol.price_zone,
           ISNULL(ol.quantity, 0)                                                         AS quantity,
           ISNULL(ol.unit_price, 0)                                                       AS unit_price,
           CAST(ISNULL(ol.quantity, 0) * ISNULL(ol.unit_price, 0) AS decimal(14,2))       AS gross_amount,
           CAST(ISNULL(ol.discount_amount, 0) AS decimal(14,2))                           AS discount_amount,
           CAST(ISNULL(ol.quantity, 0) * ISNULL(ol.unit_price, 0) - ISNULL(ol.discount_amount, 0) AS decimal(14,2)) AS net_amount,
           CAST(ISNULL(ol.is_comp, 0) AS bit)                                             AS is_comp,
           CAST(CASE WHEN o.[status] = 'Returned' THEN 1 ELSE 0 END AS bit)               AS is_returned,
           CAST(SYSUTCDATETIME() AS datetime2(6))                                         AS loaded_at   -- Warehouse only stores up to 6 decimal places
    FROM [lh_silver].[ticketing].[order_lines] AS ol
    LEFT JOIN [lh_silver].[ticketing].[orders]      AS o  ON o.order_id = ol.order_id
    LEFT JOIN [lh_silver].[core].[patron_xref]      AS x  ON x.source_system = 'ticketing' AND x.source_id = o.customer_id
    LEFT JOIN dim.patron                            AS p  ON p.patron_id = x.patron_id
                                                         AND o.order_datetime >= p.valid_from AND o.order_datetime < p.valid_to
    LEFT JOIN dim.performance                       AS dp ON dp.performance_id = ol.performance_id
    LEFT JOIN dim.venue                             AS v  ON v.venue_id = dp.venue_id
    LEFT JOIN dim.channel                           AS c  ON c.channel_name = o.channel
    WHERE ol._silver_updated_at > @wm OR o._silver_updated_at > @wm;

    BEGIN TRY
        BEGIN TRANSACTION;
            DELETE FROM fact.ticket_sales
            WHERE order_line_id IN (SELECT order_line_id FROM etl.stg_ticket_sales);
            SET @del = @@ROWCOUNT;
            INSERT INTO fact.ticket_sales SELECT * FROM etl.stg_ticket_sales;
            SET @ins = @@ROWCOUNT;
            IF @new_wm IS NOT NULL EXEC etl.usp_set_watermark 'fact.ticket_sales', @new_wm;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DECLARE @msg varchar(4000) = ERROR_MESSAGE();
        EXEC etl.usp_log @run_id, 'etl.usp_load_fact_ticket_sales', 'fact.ticket_sales', 0, 0, 0, 'Failed', @msg, @started;
        THROW;
    END CATCH;

    DECLARE @note varchar(4000) = CONCAT('watermark ', CONVERT(varchar(30), @wm, 126), ' -> ', CONVERT(varchar(30), @new_wm, 126));
    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_ticket_sales', 'fact.ticket_sales', @ins, 0, @del, 'Succeeded', @note, @started;
END;

GO