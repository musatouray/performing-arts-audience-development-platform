CREATE TABLE [fact].[subscriptions] (
    [subscription_id]   VARCHAR (20)    NOT NULL,
    [patron_key]        INT             NOT NULL,
    [purchase_date_key] INT             NOT NULL,
    [season_id]         VARCHAR (10)    NOT NULL,
    [fiscal_year]       INT             NOT NULL,
    [package_name]      VARCHAR (100)   NULL,
    [seats]             INT             NOT NULL,
    [package_amount]    DECIMAL (14, 2) NOT NULL,
    [is_renewal]        BIT             NOT NULL,
    [loaded_at]         DATETIME2 (6)   NOT NULL
);


GO