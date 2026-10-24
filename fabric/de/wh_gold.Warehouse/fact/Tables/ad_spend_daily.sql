CREATE TABLE [fact].[ad_spend_daily] (
    [ad_date_key]      INT             NOT NULL,
    [platform]         VARCHAR (30)    NULL,
    [ad_campaign_id]   VARCHAR (60)    NOT NULL,
    [ad_campaign_name] VARCHAR (200)   NULL,
    [utm_campaign]     VARCHAR (100)   NULL,
    [series_promoted]  VARCHAR (100)   NULL,
    [impressions]      INT             NOT NULL,
    [clicks]           INT             NOT NULL,
    [spend]            DECIMAL (12, 2) NOT NULL,
    [loaded_at]        DATETIME2 (6)   NOT NULL
);


GO