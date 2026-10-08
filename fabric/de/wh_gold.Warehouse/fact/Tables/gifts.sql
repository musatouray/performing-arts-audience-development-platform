CREATE TABLE [fact].[gifts] (
    [gift_id]       VARCHAR (20)    NOT NULL,
    [patron_key]    INT             NOT NULL,
    [gift_date_key] INT             NOT NULL,
    [campaign_key]  INT             NOT NULL,
    [fund_key]      INT             NOT NULL,
    [amount]        DECIMAL (14, 2) NOT NULL,
    [gift_type]     VARCHAR (30)    NULL,
    [is_anonymous]  BIT             NOT NULL,
    [loaded_at]     DATETIME2 (6)   NOT NULL
);


GO