CREATE TABLE [etl].[stg_gifts] (
    [gift_id]       VARCHAR (8000)  NULL,
    [patron_key]    INT             NOT NULL,
    [gift_date_key] INT             NOT NULL,
    [campaign_key]  INT             NOT NULL,
    [fund_key]      INT             NOT NULL,
    [amount]        DECIMAL (14, 2) NULL,
    [gift_type]     VARCHAR (8000)  NULL,
    [is_anonymous]  BIT             NULL,
    [loaded_at]     DATETIME2 (6)   NULL
);


GO