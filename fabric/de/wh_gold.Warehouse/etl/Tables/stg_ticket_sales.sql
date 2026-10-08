CREATE TABLE [etl].[stg_ticket_sales] (
    [order_line_id]        VARCHAR (8000)  NULL,
    [order_id]             VARCHAR (8000)  NULL,
    [patron_key]           INT             NOT NULL,
    [performance_key]      INT             NOT NULL,
    [venue_key]            INT             NOT NULL,
    [channel_key]          INT             NOT NULL,
    [order_date_key]       INT             NOT NULL,
    [performance_date_key] INT             NOT NULL,
    [days_before_show]     INT             NULL,
    [price_zone]           VARCHAR (8000)  NULL,
    [quantity]             INT             NOT NULL,
    [unit_price]           DECIMAL (12, 2) NOT NULL,
    [gross_amount]         DECIMAL (14, 2) NULL,
    [discount_amount]      DECIMAL (14, 2) NULL,
    [net_amount]           DECIMAL (14, 2) NULL,
    [is_comp]              BIT             NULL,
    [is_returned]          BIT             NULL,
    [loaded_at]            DATETIME2 (6)   NULL
);


GO