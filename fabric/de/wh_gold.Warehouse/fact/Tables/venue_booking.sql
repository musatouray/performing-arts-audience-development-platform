CREATE TABLE [fact].[venue_booking] (
    [booking_id]       VARCHAR (30)    NOT NULL,
    [event_key]        INT             NOT NULL,
    [room_key]         INT             NOT NULL,
    [venue_key]        INT             NOT NULL,
    [booking_date_key] INT             NOT NULL,
    [booking_type]     VARCHAR (20)    NULL,
    [start_datetime]   DATETIME2 (6)   NULL,
    [end_datetime]     DATETIME2 (6)   NULL,
    [hours_booked]     DECIMAL (6, 2)  NOT NULL,
    [rental_fee]       DECIMAL (12, 2) NOT NULL,
    [loaded_at]        DATETIME2 (6)   NOT NULL
);


GO