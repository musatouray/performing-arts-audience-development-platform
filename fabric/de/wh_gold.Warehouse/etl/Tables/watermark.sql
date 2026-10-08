CREATE TABLE [etl].[watermark] (
    [object_name] VARCHAR (128) NOT NULL,
    [last_value]  DATETIME2 (6) NOT NULL,
    [updated_at]  DATETIME2 (6) NOT NULL
);


GO