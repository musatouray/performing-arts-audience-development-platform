CREATE TABLE [dim].[room] (
    [room_key]    INT             NOT NULL,
    [room_id]     VARCHAR (10)    NOT NULL,
    [room_name]   VARCHAR (100)   NULL,
    [room_type]   VARCHAR (30)    NULL,
    [venue_key]   INT             NOT NULL,
    [capacity]    INT             NULL,
    [hourly_rate] DECIMAL (10, 2) NULL
);


GO