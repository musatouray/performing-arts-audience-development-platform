# ADR-006: Security model

**Principles:**

- **Groups, never people.**
- **Least privilege.**
- **Enforce security where each audience actually queries.**
- **PII minimized at the source.** Education data is aggregate only, and card data never lands in the lake (PCI scope).

| Layer | Control | Protects |
|---|---|---|
| Tenant | Tenant settings baseline (audited by `scripts/08`): publish-to-web off, external sharing off, item creation scoped | Everyone |
| Identity | Entra security groups `sg-hh-*` (`scripts/00`) | Joiners and leavers are handled in one place |
| Workspace | Roles per family and environment (`scripts/02`); Viewer-only in PROD | Builders |
| Item | **Item share on `wh_gold` only** for BI developers (Read, ReadData, ReadAll), declared in `tenant.yaml › item_shares` and verified by `scripts/09` (warehouse sharing is UI-only) | Consumers across workspace families |
| Lake | **OneLake security** roles on `lh_silver`: table access plus column permit-lists hiding contact PII (`scripts/07`) | Spark and lake readers |
| Warehouse | GRANT by group, **Dynamic Data Masking** on email/phone/address, **RLS** hiding anonymous gifts (`60_security.sql`) | SQL users, paginated reports, Data Agent |
| Semantic model | **RLS/OLS** roles: Audience, Development, dynamic Venue Manager (`rls_roles.md`) | Report and app consumers |
| Information protection | **Purview sensitivity labels** (Confidential › Donor PII) on `wh_gold` and the models; labels follow exports; DLP policy | Data leaving Fabric |

**Key subtlety:** Direct Lake on OneLake bypasses Warehouse SQL security. The same business rule, anonymous gifts, is therefore implemented **twice, deliberately**: SQL RLS for SQL users and model RLS for report users. Both files are CODEOWNERS-protected, so a change to one gets reviewed alongside the other.

**Say it in 30 seconds:** "Every audience is protected at the layer it actually queries. Report users through model RLS, SQL users through Warehouse security, lake users through OneLake security. All of it is assigned to groups, so onboarding a new fundraiser is one Entra change."
