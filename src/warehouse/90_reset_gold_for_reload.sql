/* =============================================================================
   90_reset_gold_for_reload.sql  -  empty Gold so it can be reloaded from Silver.

   When to use: only after a breaking change upstream, such as the switch to
   Tessitura table names (ticketing.* / fundraising.* -> tessitura.*). Patron IDs,
   source keys and watermarks from the old tables no longer line up, so a clean
   reload is safer than trying to patch rows in place.

   What it keeps: the table definitions, dim.[date] (a calendar, not source data),
   security tables (sec.*) and the load history in etl.load_log, which stays as
   the audit trail of what happened before the reset.

   NOT for production: there you would rebuild into new tables and swap them in,
   so reports never see an empty Gold. Run in dev only, then rerun pl_daily_load.
   The "Unknown" (-1) rows are added back by the load procedures on the next run.
   ============================================================================= */

-- Facts first, then dimensions.
TRUNCATE TABLE fact.ticket_sales;
TRUNCATE TABLE fact.gifts;            -- TRUNCATE is not filtered by the anonymous-gift security policy
TRUNCATE TABLE fact.subscriptions;
TRUNCATE TABLE fact.education_sessions;
TRUNCATE TABLE fact.venue_booking;
TRUNCATE TABLE fact.email_campaign_results;
TRUNCATE TABLE fact.email_click;
TRUNCATE TABLE fact.ad_spend_daily;
TRUNCATE TABLE fin.fact_gl_entry;
TRUNCATE TABLE rpt.source_freshness;
TRUNCATE TABLE fin.recon_revenue_to_gl;   -- rebuilt each run; fin.recon_note (finance's notes) is kept

TRUNCATE TABLE dim.patron;
TRUNCATE TABLE dim.performance;
TRUNCATE TABLE dim.venue;
TRUNCATE TABLE dim.channel;
TRUNCATE TABLE dim.campaign;
TRUNCATE TABLE dim.fund;
TRUNCATE TABLE dim.program;
TRUNCATE TABLE dim.school;
TRUNCATE TABLE dim.event;
TRUNCATE TABLE dim.email_campaign;
TRUNCATE TABLE dim.room;
TRUNCATE TABLE fin.dim_account;
TRUNCATE TABLE fin.dim_department;

-- Forget the "loaded up to" points, so the next run reads all of Silver.
TRUNCATE TABLE etl.watermark;

-- Check: every count should be 0 except dim_date.
SELECT 'fact.ticket_sales' AS tbl, COUNT(*) AS n FROM fact.ticket_sales
UNION ALL SELECT 'fact.gifts',          COUNT(*) FROM fact.gifts
UNION ALL SELECT 'fact.subscriptions',  COUNT(*) FROM fact.subscriptions
UNION ALL SELECT 'dim.patron',          COUNT(*) FROM dim.patron
UNION ALL SELECT 'etl.watermark',       COUNT(*) FROM etl.watermark
UNION ALL SELECT 'dim_date (kept)',     COUNT(*) FROM dim.[date];
