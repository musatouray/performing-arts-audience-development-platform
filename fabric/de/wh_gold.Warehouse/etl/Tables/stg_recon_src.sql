CREATE TABLE [etl].[stg_recon_src] (
    [month_start]     DATE            NOT NULL,
    [revenue_stream]  VARCHAR (14)    NOT NULL,
    [fund_code]       VARCHAR (10)    NOT NULL,
    [source_system]   VARCHAR (9)     NOT NULL,
    [gl_account_code] VARCHAR (4)     NOT NULL,
    [amount]          DECIMAL (38, 2) NULL
);


GO