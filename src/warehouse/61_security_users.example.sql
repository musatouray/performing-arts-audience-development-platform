/* =============================================================================
   wh_gold 61: the people behind the security rules in 60_security.sql

   This is a template. Real sign-in names are tenant data and must not go to
   GitHub, so:
     1. Copy this file to 61_security_users.local.sql (ignored by Git).
     2. Replace the example names with real ones.
     3. Run the .local.sql copy in wh_gold, after 60_security.sql.
   Re-running is safe: each list is cleared and filled again.
   ============================================================================= */

-- Who can see anonymous gifts (for example, the head of fundraising)
-- The identity that runs etl.usp_load_gold must be on this list too. The load
-- deletes changed gifts before inserting them again, and the security rule hides
-- anonymous gifts from anyone not listed, so they would never be deleted and
-- would end up duplicated. To find the name: run the pipeline once and check
-- etl.load_log.run_by (or run SELECT USER_NAME() as that identity).
DELETE FROM sec.privileged_users;
INSERT INTO sec.privileged_users VALUES ('someone@yourdomain.com', 'Platform owner (demo)');
INSERT INTO sec.privileged_users VALUES ('<identity that runs the pipeline>', 'Gold load (ETL)');
GO

-- Which venues each manager sees in reports ("Venue Manager" role)
DELETE FROM sec.user_venue;
INSERT INTO sec.user_venue VALUES ('someone@yourdomain.com', 'V02');   -- for testing: you manage the Recital Hall
GO
