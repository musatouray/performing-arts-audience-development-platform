# ADR-006: Security model

**Principles:**

- **Groups, never people.**
- **Least privilege.**
- **Enforce security where each audience actually queries.**
- **PII minimized at the source.** Education data is aggregate only, card data never lands in the lake (PCI scope), and email addresses from marketing clicks are used to find the patron, then dropped before Gold.
- **Analysts read Gold, never Bronze or Silver.** Bronze and Silver are engineering layers, reached only by data engineers through their workspace role. Everything analysts need is modelled in Gold (marketing included), where business definitions and security already live. The one exception is a small, approved data science group with read-only access to cleaned but not-yet-modelled Silver data.

| Layer | Control | Protects |
|---|---|---|
| Tenant | Tenant settings baseline (audited by `scripts/08`): publish-to-web off, external sharing off, item creation scoped | Everyone |
| Identity | Entra security groups `sg-hh-*` (`scripts/00`); service accounts only in their own group `sg-hh-svc-{job}-{nonprod|prod}`, never in a human group; the non-prod account can't reach prod | Joiners and leavers are handled in one place; a service account can't gain team access by accident |
| Workspace | Roles per family and environment (`scripts/02`); Viewer-only in PROD | Builders |
| Item | Item shares, declared in `tenant.yaml › item_shares` and verified by `scripts/09` (sharing is UI-only): `wh_gold` for BI developers (Read, ReadData, ReadAll, for Direct Lake); `wh_gold` **Read only** for SQL analysts, so the per-group GRANTs decide what they see; `lh_silver` Read only for the data science group | Consumers across workspace families |
| Lake | **OneLake security** on `lh_silver` (`scripts/07`): a single role, **DataScienceReaders**, with chosen tables and column permit-lists hiding contact PII. No DefaultReader and no analyst roles: engineers read through their workspace role, which bypasses OneLake security. The ledger and gifts are left out (finance-owned; anonymous donors). `validate_config.py` rejects any Silver role for an analyst group. | The approved data science group |
| Warehouse | GRANT by group, **Dynamic Data Masking** on email/phone/address, **RLS** hiding anonymous gifts (`60_security.sql`) | SQL users, paginated reports, Data Agent |
| Semantic model | **RLS/OLS** roles: Audience, Development, dynamic Venue Manager (`rls_roles.md`) | Report and app consumers |
| Information protection | **Purview sensitivity labels** (Confidential › Donor PII) on `wh_gold` and the models; labels follow exports; DLP policy | Data leaving Fabric |

**Key subtlety:** Direct Lake on OneLake bypasses Warehouse SQL security. The same business rule, anonymous gifts, is therefore implemented **twice, deliberately**: SQL RLS for SQL users and model RLS for report users. Both files are CODEOWNERS-protected, so a change to one gets reviewed alongside the other.

> [!NOTE]
> *"Analysts get curated Gold and nothing below it: report users through model RLS, SQL users through Warehouse grants and masking. Bronze and Silver belong to engineering. The only lake access is a small, reviewed data science group, with contact details hidden. Contributor and above bypass OneLake security, so the people it's meant to restrict never hold those roles. All of it is assigned to groups, so onboarding a new fundraiser is one Entra change."*
