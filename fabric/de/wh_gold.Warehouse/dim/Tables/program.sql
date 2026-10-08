CREATE TABLE [dim].[program] (
    [program_key]  INT           NOT NULL,
    [program_id]   VARCHAR (10)  NOT NULL,
    [program_name] VARCHAR (200) NULL,
    [program_type] VARCHAR (50)  NULL,
    [audience]     VARCHAR (100) NULL
);


GO