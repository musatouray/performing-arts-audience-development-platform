CREATE TABLE [etl].[load_log] (
    [run_id]         VARCHAR (64)   NOT NULL,
    [procedure_name] VARCHAR (128)  NOT NULL,
    [target_table]   VARCHAR (128)  NULL,
    [rows_inserted]  INT            NULL,
    [rows_updated]   INT            NULL,
    [rows_deleted]   INT            NULL,
    [status]         VARCHAR (20)   NOT NULL,
    [message]        VARCHAR (4000) NULL,
    [started_at]     DATETIME2 (6)  NOT NULL,
    [ended_at]       DATETIME2 (6)  NULL,
    [run_by]         VARCHAR (256)  NULL
);


GO