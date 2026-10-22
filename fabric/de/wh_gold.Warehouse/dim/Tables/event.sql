CREATE TABLE [dim].[event] (
    [event_key]       INT           NOT NULL,
    [event_id]        VARCHAR (20)  NOT NULL,
    [event_name]      VARCHAR (300) NULL,
    [event_type]      VARCHAR (20)  NULL,
    [client_name]     VARCHAR (200) NULL,
    [client_type]     VARCHAR (20)  NULL,
    [status]          VARCHAR (20)  NULL,
    [event_date_key]  INT           NOT NULL,
    [performance_key] INT           NOT NULL,
    [is_linked]       BIT           NOT NULL
);


GO