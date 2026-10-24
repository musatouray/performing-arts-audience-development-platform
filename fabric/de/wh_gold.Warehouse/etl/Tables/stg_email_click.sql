CREATE TABLE [etl].[stg_email_click] (
    [click_id]           VARCHAR (8000) NULL,
    [email_campaign_key] INT            NOT NULL,
    [patron_key]         INT            NOT NULL,
    [click_date_key]     INT            NOT NULL,
    [clicked_at]         DATETIME2 (6)  NULL,
    [loaded_at]          DATETIME2 (6)  NULL
);


GO