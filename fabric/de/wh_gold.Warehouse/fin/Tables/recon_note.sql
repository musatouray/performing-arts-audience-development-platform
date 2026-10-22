CREATE TABLE [fin].[recon_note] (
    [month_start]    DATE           NOT NULL,
    [revenue_stream] VARCHAR (30)   NOT NULL,
    [fund_code]      VARCHAR (10)   NOT NULL,
    [cause]          VARCHAR (50)   NULL,
    [note]           VARCHAR (1000) NULL,
    [resolution]     VARCHAR (20)   NULL,
    [owner_upn]      VARCHAR (256)  NULL,
    [noted_at]       DATETIME2 (6)  NULL
);


GO