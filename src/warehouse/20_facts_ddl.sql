/* =============================================================================
   wh_gold · 20 — fact tables (DDL)
   Every fact states its GRAIN. Degenerate business keys (order_line_id, gift_id)
   are kept for drill-through and for idempotent incremental loads.
   ============================================================================= */

-- Grain: one row per ticket ORDER LINE (performance x price zone within an order).
CREATE TABLE fact.ticket_sales (
    order_line_id         varchar(20)    NOT NULL,
    order_id              varchar(20)    NOT NULL,
    patron_key            int            NOT NULL,
    performance_key       int            NOT NULL,
    venue_key             int            NOT NULL,
    channel_key           int            NOT NULL,
    order_date_key        int            NOT NULL,   -- role-playing date #1: when it was bought
    performance_date_key  int            NOT NULL,   -- role-playing date #2: when the show is
    days_before_show      int            NULL,       -- purchase lead time (pacing analysis)
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

-- Grain: one row per GIFT (payment/transaction) in the fundraising system.
CREATE TABLE fact.gifts (
    gift_id        varchar(20)    NOT NULL,
    patron_key     int            NOT NULL,
    gift_date_key  int            NOT NULL,
    campaign_key   int            NOT NULL,
    fund_key       int            NOT NULL,
    amount         decimal(14,2)  NOT NULL,
    gift_type      varchar(30)    NULL,
    is_anonymous   bit            NOT NULL,   -- RLS: only privileged users see anonymous gifts
    loaded_at      datetime2(6)   NOT NULL
);
GO

-- Grain: one row per SUBSCRIPTION package purchased for a season.
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

-- Grain: one row per EDUCATION SESSION delivered (aggregate participants - no student PII).
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
