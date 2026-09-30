# Semantic model security: RLS and OLS roles

Report consumers are protected **in the semantic model**. It's the layer they actually query: Direct Lake on OneLake with a fixed identity.
Roles are mapped to **Entra groups**, not to people.

## sm_audience_development

| Role | Members (Entra group) | RLS (DAX table filter) | OLS | Business rule |
|---|---|---|---|---|
| **Development** | `sg-hh-analysts-development` | none | none | Fundraisers see everything, including donor contact details. |
| **Audience** | `sg-hh-analysts-audience` | `fact_gifts`: `FALSE()` | Hide `dim_patron[email]`, `[phone]`, `[address_line1]` | Ticketing/marketing see buyers, not giving history or contact PII. |
| **Venue Manager** (dynamic) | `sg-hh-report-viewers` (a subset) | `dim_performance`: `dim_performance[venue_id] IN CALCULATETABLE ( VALUES ( sec_user_venue[venue_id] ), sec_user_venue[user_principal_name] = USERPRINCIPALNAME () )` | Same OLS as Audience | Each manager sees only their hall(s). The mapping lives in `wh_gold.sec.user_venue`, so no model change is needed to onboard someone. |
| **Anonymous-gift filter** (added to Venue Manager) | n/a | `fact_gifts`: `fact_gifts[is_anonymous] = FALSE()` | n/a | Mirrors the SQL RLS policy in `60_security.sql`. (Audience already sees no gifts.) |

### Testing

Use the **Test as role** option: Model › Security › pick a role, optionally "as user".

Screenshot these for your portfolio:

1. **Audience** role: donor pages show blank or hidden fields.
2. **Venue Manager** as your own user: only Recital Hall (V02) shows up.

## sm_education_impact

| Role | Members | RLS | Notes |
|---|---|---|---|
| **Education Staff** | `sg-hh-education-team` | none | The model holds only aggregate program data. It's access-controlled by the app, and there's no PII to filter. |

## Layered model: who is protected where

| Consumer | Path | Enforced by |
|---|---|---|
| Report/app viewer | Power BI → Direct Lake on OneLake (fixed identity) | **Semantic model RLS/OLS** |
| SQL analyst (SSMS, Excel, paginated reports) | SQL endpoint of `wh_gold` | **T-SQL GRANT, RLS, DDM** (`60_security.sql`) |
| Spark / lake reader | OneLake (`lh_silver`) | **OneLake security roles** (`scripts/07_apply_onelake_security.py`) |
| Engineer / BI developer | Workspace | **Workspace roles** (Contributor in Dev/Test, Viewer in Prod) |
| BI developer authoring on Gold | Direct Lake on OneLake → `wh_gold` in another workspace | **Item share** on `wh_gold` (Read, ReadData, ReadAll), not a workspace role (`scripts/09`) |
| Everyone | Tenant | **Tenant settings**, **Purview sensitivity labels** (Confidential › Donor PII on Gold and the models) |

> **Why not use OLS on `fact_gifts[amount]`?** Any measure that references an OLS-hidden column errors for that role, which breaks visuals. Filtering the rows out (RLS `FALSE()`) makes the fundraising visuals blank instead of broken. Use OLS only for columns that no shared measure depends on, such as contact PII.
