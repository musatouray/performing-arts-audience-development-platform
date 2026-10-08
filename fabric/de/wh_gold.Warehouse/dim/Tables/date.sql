CREATE TABLE [dim].[date] (
    [date_key]          INT          NOT NULL,
    [date]              DATE         NOT NULL,
    [day_of_week]       INT          NOT NULL,
    [day_name]          VARCHAR (10) NOT NULL,
    [is_weekend]        BIT          NOT NULL,
    [month_num]         INT          NOT NULL,
    [month_name]        VARCHAR (10) NOT NULL,
    [calendar_quarter]  INT          NOT NULL,
    [calendar_year]     INT          NOT NULL,
    [fiscal_year]       INT          NOT NULL,
    [fiscal_year_label] VARCHAR (10) NOT NULL,
    [fiscal_month_num]  INT          NOT NULL,
    [fiscal_quarter]    INT          NOT NULL,
    [season_label]      VARCHAR (12) NOT NULL
);


GO

ALTER TABLE [dim].[date]
    ADD CONSTRAINT [pk_dim_date] PRIMARY KEY NONCLUSTERED ([date_key] ASC) NOT ENFORCED;


GO