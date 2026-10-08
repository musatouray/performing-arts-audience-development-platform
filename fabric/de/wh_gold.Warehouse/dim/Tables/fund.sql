CREATE TABLE [dim].[fund] (
    [fund_key]      INT           NOT NULL,
    [fund_id]       VARCHAR (10)  NOT NULL,
    [fund_name]     VARCHAR (100) NULL,
    [is_restricted] BIT           NULL
);


GO