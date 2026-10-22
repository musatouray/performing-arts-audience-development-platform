CREATE TABLE [fin].[dim_account] (
    [account_key]    INT           NOT NULL,
    [account_code]   VARCHAR (10)  NOT NULL,
    [account_name]   VARCHAR (100) NULL,
    [account_type]   VARCHAR (20)  NULL,
    [account_group]  VARCHAR (50)  NULL,
    [normal_balance] VARCHAR (10)  NULL
);


GO