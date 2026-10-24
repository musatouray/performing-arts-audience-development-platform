CREATE TABLE [dim].[email_campaign] (
    [email_campaign_key] INT           NOT NULL,
    [email_campaign_id]  VARCHAR (30)  NOT NULL,
    [campaign_name]      VARCHAR (200) NULL,
    [campaign_type]      VARCHAR (50)  NULL,
    [series_promoted]    VARCHAR (100) NULL,
    [audience_segment]   VARCHAR (100) NULL,
    [send_datetime]      DATETIME2 (6) NULL,
    [send_date_key]      INT           NOT NULL
);


GO