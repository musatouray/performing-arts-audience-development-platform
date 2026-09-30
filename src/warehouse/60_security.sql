/* =============================================================================
   wh_gold · 60 — SQL-layer security (for people who query the Warehouse with SQL:
   SSMS/VS Code, Excel, paginated reports on the SQL endpoint, Data Agent).

   IMPORTANT (defend this in the interview):
   Direct Lake **on OneLake** reads the Delta files directly, so T-SQL RLS/DDM below do
   NOT apply to Power BI reports built on it. Report users are protected by
   semantic-model RLS/OLS (src/semantic_model/rls_roles.md) + a fixed-identity connection.
   One policy, enforced at the layer each audience actually uses.

   Controls here:
     1. GRANT by Entra GROUP on schemas (never on individuals)
     2. Dynamic Data Masking on patron contact PII + UNMASK only for Development
     3. Row-Level Security: anonymous gifts visible only to privileged users
   Replace @yourdomain with your tenant's domain before running.
   ============================================================================= */

-- ---------------------------------------------------------------------------
-- 1) Least-privilege grants (groups from config/tenant.yaml)
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
-- 2) Dynamic Data Masking: contact PII masked unless the caller has UNMASK.
-- ---------------------------------------------------------------------------
ALTER TABLE dim.patron ALTER COLUMN email         ADD MASKED WITH (FUNCTION = 'email()');
ALTER TABLE dim.patron ALTER COLUMN phone         ADD MASKED WITH (FUNCTION = 'partial(0,"XXX-XXX-",4)');
ALTER TABLE dim.patron ALTER COLUMN address_line1 ADD MASKED WITH (FUNCTION = 'default()');
GRANT UNMASK TO [sg-hh-analysts-development];     -- fundraisers need to contact donors
GO

-- ---------------------------------------------------------------------------
-- 3) Row-Level Security on fact.gifts
--    Donors who asked for anonymity are hidden from everyone except users listed
--    in sec.privileged_users (e.g. Chief Development Officer, gift processing).
-- ---------------------------------------------------------------------------
CREATE TABLE sec.privileged_users (
    user_principal_name varchar(256) NOT NULL,
    reason              varchar(200) NULL
);
GO
INSERT INTO sec.privileged_users VALUES ('you@yourdomain.com', 'Platform owner (demo)');
GO

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
-- 4) Mapping table for DYNAMIC RLS in the semantic model ("Venue Manager" role):
--    a manager sees only the venues assigned to them. Loaded into the model as a
--    hidden table; DAX filter: sec_user_venue[user_principal_name] = USERPRINCIPALNAME()
-- ---------------------------------------------------------------------------
CREATE TABLE sec.user_venue (
    user_principal_name varchar(256) NOT NULL,
    venue_id            varchar(10)  NOT NULL
);
GO
INSERT INTO sec.user_venue VALUES ('you@yourdomain.com', 'V02');   -- demo: you manage the Recital Hall
GO

-- Verify as yourself:
--   SELECT USER_NAME();                                     -- the UPN RLS sees
--   SELECT COUNT(*), SUM(CAST(is_anonymous AS int)) FROM fact.gifts;
--   Then sign in as a test user in sg-hh-analysts-audience: emails are masked, anonymous gifts are gone.
