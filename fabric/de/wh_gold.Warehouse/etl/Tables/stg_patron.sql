CREATE TABLE [etl].[stg_patron] (
    [patron_id]       VARCHAR (8000) NULL,
    [first_name]      VARCHAR (8000) NULL,
    [last_name]       VARCHAR (8000) NULL,
    [full_name]       VARCHAR (210)  NULL,
    [email]           VARCHAR (8000) NULL,
    [phone]           VARCHAR (8000) NULL,
    [address_line1]   VARCHAR (8000) NULL,
    [city]            VARCHAR (8000) NULL,
    [state]           VARCHAR (8000) NULL,
    [postal_code]     VARCHAR (8000) NULL,
    [country]         VARCHAR (8000) NULL,
    [region]          VARCHAR (30)   NULL,
    [patron_type]     VARCHAR (8000) NULL,
    [email_opt_in]    BIT            NULL,
    [source_systems]  VARCHAR (8000) NULL,
    [first_seen_date] DATE           NULL,
    [scd_hash]        VARCHAR (64)   NULL
);


GO