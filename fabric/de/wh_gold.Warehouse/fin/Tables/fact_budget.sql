CREATE TABLE [fin].[fact_budget] (
    [budget_line_id] VARCHAR (20)    NOT NULL,
    [date_key]       INT             NOT NULL,
    [fiscal_year]    INT             NOT NULL,
    [budget_version] VARCHAR (20)    NOT NULL,
    [account_key]    INT             NOT NULL,
    [fund_key]       INT             NOT NULL,
    [department_key] INT             NOT NULL,
    [budget_amount]  DECIMAL (18, 4) NOT NULL,
    [loaded_at]      DATETIME2 (6)   NOT NULL
);


GO