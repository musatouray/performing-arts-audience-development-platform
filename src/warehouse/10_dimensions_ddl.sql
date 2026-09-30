/* =============================================================================
   wh_gold · 10 — dimension tables (DDL)
   Surrogate keys are int; -1 = "Unknown" member so facts never drop rows on a
   missing lookup (orphans are visible, not silently lost).
   PRIMARY KEY ... NOT ENFORCED documents the grain for the optimizer and for
   the semantic model; Fabric Warehouse does not enforce it.
   ============================================================================= */

CREATE TABLE dim.[date] (
    date_key           int          NOT NULL,   -- yyyymmdd
    [date]             date         NOT NULL,
    day_of_week        int          NOT NULL,
    day_name           varchar(10)  NOT NULL,
    is_weekend         bit          NOT NULL,
    month_num          int          NOT NULL,
    month_name         varchar(10)  NOT NULL,
    calendar_quarter   int          NOT NULL,
    calendar_year      int          NOT NULL,
    fiscal_year        int          NOT NULL,   -- FY runs Jul -> Jun; FY2027 = Jul-2026..Jun-2027
    fiscal_year_label  varchar(10)  NOT NULL,   -- 'FY2027'
    fiscal_month_num   int          NOT NULL,   -- Jul = 1 ... Jun = 12 (sort key for fiscal visuals)
    fiscal_quarter     int          NOT NULL,
    season_label       varchar(12)  NOT NULL    -- '2026-27'
);
ALTER TABLE dim.[date] ADD CONSTRAINT pk_dim_date PRIMARY KEY NONCLUSTERED (date_key) NOT ENFORCED;
GO

-- SCD Type 2: address/geography/type changes create a new version, so a patron's
-- purchases and gifts are reported against where they lived AT THE TIME.
CREATE TABLE dim.patron (
    patron_key       int           NOT NULL,
    patron_id        varchar(20)   NOT NULL,   -- golden ID from Silver identity resolution
    first_name       varchar(100)  NULL,
    last_name        varchar(100)  NULL,
    full_name        varchar(210)  NULL,
    email            varchar(256)  NULL,       -- masked (DDM) for non-privileged SQL users
    phone            varchar(40)   NULL,       -- masked (DDM)
    address_line1    varchar(200)  NULL,
    city             varchar(100)  NULL,
    [state]          varchar(10)   NULL,
    postal_code      varchar(10)   NULL,
    country          varchar(50)   NULL,
    region           varchar(30)   NULL,       -- 'NYC', 'NY Metro', 'Domestic', 'Unknown'
    patron_type      varchar(20)   NULL,
    email_opt_in     bit           NULL,
    source_systems   varchar(50)   NULL,       -- 'fundraising,ticketing' = known to both systems
    first_seen_date  date          NULL,
    scd_hash         varchar(64)   NULL,
    valid_from       datetime2(6)  NOT NULL,
    valid_to         datetime2(6)  NOT NULL,   -- 9999-12-31 for the current version
    is_current       bit           NOT NULL
);
ALTER TABLE dim.patron ADD CONSTRAINT pk_dim_patron PRIMARY KEY NONCLUSTERED (patron_key) NOT ENFORCED;
GO

CREATE TABLE dim.venue (
    venue_key   int          NOT NULL,
    venue_id    varchar(10)  NOT NULL,
    venue_name  varchar(100) NOT NULL,
    capacity    int          NULL
);
GO

CREATE TABLE dim.performance (
    performance_key       int           NOT NULL,
    performance_id        varchar(20)   NOT NULL,
    title                 varchar(300)  NULL,
    series                varchar(100)  NULL,
    genre                 varchar(100)  NULL,
    season_id             varchar(10)   NULL,
    season_name           varchar(30)   NULL,
    fiscal_year           int           NULL,
    venue_id              varchar(10)   NULL,
    venue_name            varchar(100)  NULL,
    performance_datetime  datetime2(6)  NULL,
    performance_date_key  int           NULL,
    day_part              varchar(10)   NULL,   -- Matinee / Evening
    capacity              int           NULL,
    [status]              varchar(20)   NULL
);
GO

CREATE TABLE dim.channel (
    channel_key   int          NOT NULL,
    channel_name  varchar(50)  NOT NULL
);
GO

CREATE TABLE dim.campaign (
    campaign_key   int            NOT NULL,
    campaign_id    varchar(20)    NOT NULL,
    campaign_name  varchar(200)   NULL,
    campaign_type  varchar(50)    NULL,
    fiscal_year    int            NULL,
    goal_amount    decimal(14,2)  NULL
);
GO

CREATE TABLE dim.fund (
    fund_key       int           NOT NULL,
    fund_id        varchar(10)   NOT NULL,
    fund_name      varchar(100)  NULL,
    is_restricted  bit           NULL
);
GO

CREATE TABLE dim.program (
    program_key   int           NOT NULL,
    program_id    varchar(10)   NOT NULL,
    program_name  varchar(200)  NULL,
    program_type  varchar(50)   NULL,
    audience      varchar(100)  NULL
);
GO

CREATE TABLE dim.school (
    school_key   int           NOT NULL,
    school_id    varchar(10)   NOT NULL,
    school_name  varchar(200)  NULL,
    borough      varchar(30)   NULL,
    is_title_i   bit           NULL
);
GO
