CREATE TABLE [etl].[stg_recon] (
    [month_start]      DATE            NULL,
    [fiscal_year]      INT             NULL,
    [revenue_stream]   VARCHAR (30)    NULL,
    [fund_code]        VARCHAR (10)    NULL,
    [source_system]    VARCHAR (20)    NULL,
    [gl_account_code]  VARCHAR (10)    NULL,
    [source_amount]    DECIMAL (16, 2) NULL,
    [gl_amount]        DECIMAL (16, 2) NULL,
    [variance]         DECIMAL (16, 2) NULL,
    [tolerance_amount] DECIMAL (16, 2) NULL,
    [status]           VARCHAR (20)    NULL,
    [loaded_at]        DATETIME2 (6)   NULL,
    [cause]            VARCHAR (50)    NULL,
    [note]             VARCHAR (1000)  NULL,
    [resolution]       VARCHAR (20)    NULL
);


GO