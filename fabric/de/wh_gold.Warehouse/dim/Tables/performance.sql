CREATE TABLE [dim].[performance] (
    [performance_key]      INT           NOT NULL,
    [performance_id]       VARCHAR (20)  NOT NULL,
    [title]                VARCHAR (300) NULL,
    [series]               VARCHAR (100) NULL,
    [genre]                VARCHAR (100) NULL,
    [season_id]            VARCHAR (10)  NULL,
    [season_name]          VARCHAR (30)  NULL,
    [fiscal_year]          INT           NULL,
    [venue_id]             VARCHAR (10)  NULL,
    [venue_name]           VARCHAR (100) NULL,
    [performance_datetime] DATETIME2 (6) NULL,
    [performance_date_key] INT           NULL,
    [day_part]             VARCHAR (10)  NULL,
    [capacity]             INT           NULL,
    [status]               VARCHAR (20)  NULL
);


GO