CREATE TABLE [rpt].[source_freshness] (
    [source_system]   VARCHAR (20)  NOT NULL,
    [source_name]     VARCHAR (100) NULL,
    [last_loaded_utc] DATETIME2 (6) NULL,
    [data_through]    DATE          NULL,
    [measured_by]     VARCHAR (50)  NULL,
    [snapshot_at]     DATETIME2 (6) NOT NULL
);


GO