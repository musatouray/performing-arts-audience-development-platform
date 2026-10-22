CREATE TABLE [fin].[recon_revenue_to_gl] (
    [month_start]      DATE            NOT NULL,
    [fiscal_year]      INT             NOT NULL,
    [revenue_stream]   VARCHAR (30)    NOT NULL,
    [fund_code]        VARCHAR (10)    NOT NULL,
    [source_system]    VARCHAR (20)    NOT NULL,
    [gl_account_code]  VARCHAR (10)    NOT NULL,
    [source_amount]    DECIMAL (16, 2) NOT NULL,
    [gl_amount]        DECIMAL (16, 2) NOT NULL,
    [variance]         DECIMAL (16, 2) NOT NULL,
    [tolerance_amount] DECIMAL (16, 2) NOT NULL,
    [status]           VARCHAR (20)    NOT NULL,
    [loaded_at]        DATETIME2 (6)   NOT NULL,
    [cause]            VARCHAR (50)    NULL,
    [note]             VARCHAR (1000)  NULL,
    [resolution]       VARCHAR (20)    NULL
);


GO