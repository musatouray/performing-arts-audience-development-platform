CREATE TABLE [fact].[ticket_sales] (
    [order_line_id]        VARCHAR (20)    NOT NULL,
    [order_id]             VARCHAR (20)    NOT NULL,
    [patron_key]           INT             NOT NULL,
    [performance_key]      INT             NOT NULL,
    [venue_key]            INT             NOT NULL,
    [channel_key]          INT             NOT NULL,
    [order_date_key]       INT             NOT NULL,
    [performance_date_key] INT             NOT NULL,
    [days_before_show]     INT             NULL,
    [price_zone]           VARCHAR (50)    NULL,
    [quantity]             INT             NOT NULL,
    [unit_price]           DECIMAL (12, 2) NOT NULL,
    [gross_amount]         DECIMAL (14, 2) NOT NULL,
    [discount_amount]      DECIMAL (14, 2) NOT NULL,
    [net_amount]           DECIMAL (14, 2) NOT NULL,
    [is_comp]              BIT             NOT NULL,
    [is_returned]          BIT             NOT NULL,
    [loaded_at]            DATETIME2 (6)   NOT NULL
);


GO