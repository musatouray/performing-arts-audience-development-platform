CREATE TABLE [fact].[email_campaign_results] (
    [email_campaign_key] INT           NOT NULL,
    [send_date_key]      INT           NOT NULL,
    [recipients]         INT           NOT NULL,
    [delivered]          INT           NOT NULL,
    [bounces]            INT           NOT NULL,
    [unique_opens]       INT           NOT NULL,
    [unique_clicks]      INT           NOT NULL,
    [unsubscribes]       INT           NOT NULL,
    [stats_as_of]        DATETIME2 (6) NULL,
    [loaded_at]          DATETIME2 (6) NOT NULL
);


GO