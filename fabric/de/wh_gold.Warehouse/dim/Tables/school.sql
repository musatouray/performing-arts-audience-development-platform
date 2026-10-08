CREATE TABLE [dim].[school] (
    [school_key]  INT           NOT NULL,
    [school_id]   VARCHAR (10)  NOT NULL,
    [school_name] VARCHAR (200) NULL,
    [borough]     VARCHAR (30)  NULL,
    [is_title_i]  BIT           NULL
);


GO