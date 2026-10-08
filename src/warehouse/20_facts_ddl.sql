/* =============================================================================
   wh_gold 20: fact tables
   Each table notes what one row represents. Source IDs such as order_line_id and
   gift_id are kept so you can trace a row back and so reloads don't duplicate data.
   ============================================================================= */

-- One row per order line (one show and price zone within an order).
CREATE TABLE fact.ticket_sales (
    order_line_id         varchar(20)    NOT NULL,
    order_id              varchar(20)    NOT NULL,
    patron_key            int            NOT NULL,
    performance_key       int            NOT NULL,
    venue_key             int            NOT NULL,
    channel_key           int            NOT NULL,
    order_date_key        int            NOT NULL,   -- date the tickets were bought
    performance_date_key  int            NOT NULL,   -- date of the show
    days_before_show      int            NULL,       -- how far ahead the tickets were bought
    price_zone            varchar(50)    NULL,
    quantity              int            NOT NULL,
    unit_price            decimal(12,2)  NOT NULL,
    gross_amount          decimal(14,2)  NOT NULL,
    discount_amount       decimal(14,2)  NOT NULL,
    net_amount            decimal(14,2)  NOT NULL,
    is_comp               bit            NOT NULL,
    is_returned           bit            NOT NULL,
    loaded_at             datetime2(6)   NOT NULL
);
GO

-- One row per gift (payment) in the fundraising system.
CREATE TABLE fact.gifts (
    gift_id        varchar(20)    NOT NULL,
    patron_key     int            NOT NULL,
    gift_date_key  int            NOT NULL,
    campaign_key   int            NOT NULL,
    fund_key       int            NOT NULL,
    amount         decimal(14,2)  NOT NULL,
    gift_type      varchar(30)    NULL,
    is_anonymous   bit            NOT NULL,   -- anonymous gifts are hidden from most users (see 60_security.sql)
    loaded_at      datetime2(6)   NOT NULL
);
GO

-- One row per subscription package bought for a season.
CREATE TABLE fact.subscriptions (
    subscription_id    varchar(20)    NOT NULL,
    patron_key         int            NOT NULL,
    purchase_date_key  int            NOT NULL,
    season_id          varchar(10)    NOT NULL,
    fiscal_year        int            NOT NULL,
    package_name       varchar(100)   NULL,
    seats              int            NOT NULL,
    package_amount     decimal(14,2)  NOT NULL,
    is_renewal         bit            NOT NULL,
    loaded_at          datetime2(6)   NOT NULL
);
GO

-- One row per education session. Only a participant count is kept, no student details.
CREATE TABLE fact.education_sessions (
    enrollment_id          varchar(20)   NOT NULL,
    program_key            int           NOT NULL,
    school_key             int           NOT NULL,
    session_date_key       int           NOT NULL,
    participants           int           NOT NULL,
    teaching_artist_hours  decimal(6,1)  NULL,
    loaded_at              datetime2(6)  NOT NULL
);
GO
