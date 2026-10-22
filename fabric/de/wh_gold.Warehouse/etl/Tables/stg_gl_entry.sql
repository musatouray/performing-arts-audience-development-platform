CREATE TABLE [etl].[stg_gl_entry] (
    [gl_transaction_id]  VARCHAR (8000)  NULL,
    [journal_id]         VARCHAR (8000)  NULL,
    [line_number]        INT             NULL,
    [session_id]         VARCHAR (8000)  NULL,
    [source_module]      VARCHAR (8000)  NULL,
    [effective_date_key] INT             NOT NULL,
    [posted_date_key]    INT             NOT NULL,
    [account_key]        INT             NOT NULL,
    [fund_key]           INT             NOT NULL,
    [department_key]     INT             NOT NULL,
    [debit_amount]       DECIMAL (14, 2) NULL,
    [credit_amount]      DECIMAL (14, 2) NULL,
    [net_amount]         DECIMAL (14, 2) NULL,
    [description]        VARCHAR (200)   NULL,
    [reference]          VARCHAR (100)   NULL,
    [loaded_at]          DATETIME2 (6)   NULL
);


GO