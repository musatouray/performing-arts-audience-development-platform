CREATE TABLE [fin].[fact_gl_entry] (
    [gl_transaction_id]  VARCHAR (20)    NOT NULL,
    [journal_id]         VARCHAR (20)    NOT NULL,
    [line_number]        INT             NULL,
    [session_id]         VARCHAR (40)    NULL,
    [source_module]      VARCHAR (20)    NULL,
    [effective_date_key] INT             NOT NULL,
    [posted_date_key]    INT             NOT NULL,
    [account_key]        INT             NOT NULL,
    [fund_key]           INT             NOT NULL,
    [department_key]     INT             NOT NULL,
    [debit_amount]       DECIMAL (14, 2) NOT NULL,
    [credit_amount]      DECIMAL (14, 2) NOT NULL,
    [net_amount]         DECIMAL (14, 2) NOT NULL,
    [description]        VARCHAR (200)   NULL,
    [reference]          VARCHAR (100)   NULL,
    [loaded_at]          DATETIME2 (6)   NOT NULL
);


GO