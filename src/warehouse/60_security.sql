/* =============================================================================
   wh_gold 60: security for people who query the warehouse with SQL
   (SSMS, VS Code, Excel, paginated reports, Data Agent).

   These rules don't apply to the Power BI reports. Those read the data files
   directly, so report security is set in the semantic model instead
   (see src/semantic_model/rls_roles.md).

   What this file sets up:
     1. Read access by security group
     2. Masked contact details (email, phone, address) for everyone except fundraising
     3. Anonymous gifts hidden from everyone except a short list of people
   Who is on the privileged list and which venues each manager sees are
   tenant data (real sign-in names), so they're not in this file. After running
   it, copy 61_security_users.example.sql to 61_security_users.local.sql
   (ignored by Git), put in real names, and run that.
   ============================================================================= */

-- ---------------------------------------------------------------------------
-- 1) Read access by group. Each group only gets the schemas it needs.
-- ---------------------------------------------------------------------------
GRANT SELECT ON SCHEMA::rpt  TO [sg-hh-analysts-audience];
GRANT SELECT ON SCHEMA::rpt  TO [sg-hh-analysts-development];
GRANT SELECT ON SCHEMA::dim  TO [sg-hh-analysts-development];
GRANT SELECT ON SCHEMA::fact TO [sg-hh-analysts-development];
GRANT SELECT ON OBJECT::rpt.vw_education_impact TO [sg-hh-education-team];
DENY  SELECT ON SCHEMA::etl  TO [sg-hh-analysts-audience];
DENY  SELECT ON SCHEMA::etl  TO [sg-hh-analysts-development];
GO

-- ---------------------------------------------------------------------------
-- 2) Contact details are masked unless the user has UNMASK permission.
-- ---------------------------------------------------------------------------
ALTER TABLE dim.patron ALTER COLUMN email         ADD MASKED WITH (FUNCTION = 'email()');
ALTER TABLE dim.patron ALTER COLUMN phone         ADD MASKED WITH (FUNCTION = 'partial(0,"XXX-XXX-",4)');
ALTER TABLE dim.patron ALTER COLUMN address_line1 ADD MASKED WITH (FUNCTION = 'default()');
GRANT UNMASK TO [sg-hh-analysts-development];     -- fundraisers need to contact donors
GO

-- ---------------------------------------------------------------------------
-- 3) Anonymous gifts
--    Gifts from donors who asked to stay anonymous are only visible to people
--    listed in sec.privileged_users (for example, the head of fundraising).
-- ---------------------------------------------------------------------------
CREATE TABLE sec.privileged_users (
    user_principal_name varchar(256) NOT NULL,
    reason              varchar(200) NULL
);
GO
-- Rows are added by 61_security_users.local.sql.

CREATE FUNCTION sec.fn_gift_access(@is_anonymous bit)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS allowed
    WHERE @is_anonymous = 0
       OR EXISTS (SELECT 1 FROM sec.privileged_users WHERE user_principal_name = USER_NAME());
GO

CREATE SECURITY POLICY sec.policy_gifts
    ADD FILTER PREDICATE sec.fn_gift_access(is_anonymous) ON fact.gifts
    WITH (STATE = ON);
GO

-- ---------------------------------------------------------------------------
-- 4) Which venues each manager can see. The semantic model's "Venue Manager"
--    role uses this table so each manager only sees their own halls.
-- ---------------------------------------------------------------------------
CREATE TABLE sec.user_venue (
    user_principal_name varchar(256) NOT NULL,
    venue_id            varchar(10)  NOT NULL
);
GO
-- Rows are added by 61_security_users.local.sql.

-- To check it works:
--   SELECT USER_NAME();                                     -- the user name the rules see
--   SELECT COUNT(*), SUM(CAST(is_anonymous AS int)) FROM fact.gifts;
--   Then sign in as a test user in sg-hh-analysts-audience: emails should be masked and anonymous gifts gone.
