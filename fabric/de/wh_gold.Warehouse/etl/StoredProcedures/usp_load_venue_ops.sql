-- ---------------------------------------------------------------------------
-- Load: the hall calendar. Small (a few thousand rows a year), so the bookings
-- fact is rebuilt each run; events keep their keys so reports stay stable.
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_venue_ops @run_id varchar(64)
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