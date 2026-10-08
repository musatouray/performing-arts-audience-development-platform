CREATE TABLE [dim].[patron] (
    [patron_key]      INT                                                               NOT NULL,
    [patron_id]       VARCHAR (20)                                                      NOT NULL,
    [first_name]      VARCHAR (100)                                                     NULL,
    [last_name]       VARCHAR (100)                                                     NULL,
    [full_name]       VARCHAR (210)                                                     NULL,
    [email]           VARCHAR (256) MASKED WITH (FUNCTION = 'email()')                  NULL,
    [phone]           VARCHAR (40) MASKED WITH (FUNCTION = 'partial(0, "XXX-XXX-", 4)') NULL,
    [address_line1]   VARCHAR (200) MASKED WITH (FUNCTION = 'default()')                NULL,
    [city]            VARCHAR (100)                                                     NULL,
    [state]           VARCHAR (10)                                                      NULL,
    [postal_code]     VARCHAR (10)                                                      NULL,
    [country]         VARCHAR (50)                                                      NULL,
    [region]          VARCHAR (30)                                                      NULL,
    [patron_type]     VARCHAR (20)                                                      NULL,
    [email_opt_in]    BIT                                                               NULL,
    [source_systems]  VARCHAR (50)                                                      NULL,
    [first_seen_date] DATE                                                              NULL,
    [scd_hash]        VARCHAR (64)                                                      NULL,
    [valid_from]      DATETIME2 (6)                                                     NOT NULL,
    [valid_to]        DATETIME2 (6)                                                     NOT NULL,
    [is_current]      BIT                                                               NOT NULL
);


GO

ALTER TABLE [dim].[patron]
    ADD CONSTRAINT [pk_dim_patron] PRIMARY KEY NONCLUSTERED ([patron_key] ASC) NOT ENFORCED;


GO