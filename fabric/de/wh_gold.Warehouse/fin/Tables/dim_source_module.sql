CREATE TABLE [fin].[dim_source_module] (
    [source_module]  VARCHAR (20) NOT NULL,
    [module_name]    VARCHAR (60) NOT NULL,
    [cash_flow_line] VARCHAR (60) NOT NULL,
    [cash_direction] VARCHAR (10) NOT NULL,
    [sort_order]     INT          NOT NULL
);


GO