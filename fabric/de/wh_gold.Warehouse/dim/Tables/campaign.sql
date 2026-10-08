CREATE TABLE [dim].[campaign] (
    [campaign_key]  INT             NOT NULL,
    [campaign_id]   VARCHAR (20)    NOT NULL,
    [campaign_name] VARCHAR (200)   NULL,
    [campaign_type] VARCHAR (50)    NULL,
    [fiscal_year]   INT             NULL,
    [goal_amount]   DECIMAL (14, 2) NULL
);


GO