# ADR-001: Workspace and domain topology

## Options

| Option | Pros | Cons |
|---|---|---|
| One workspace per environment | Simple | Analysts see raw data; no separation of duties; one giant Git folder |
| Workspace per medallion layer × env (9+) | Clean layer isolation | Cross-workspace Warehouse reads aren't possible; too much overhead for four people |
| **Workspace per family × env: Data Platform + one BI workspace per business domain** | Engineers own the data plane; BI access per business area; one Org App per domain; domains map 1:1 to BI workspaces | Nine workspaces; cross-workspace model binding at promotion (ADR-004) |

## Decision

Three families × three environments = **nine workspaces**, named `{org}-{family}-{env}`, with one deployment pipeline per family:

- `hh-dataplatform-*` holds `lh_bronze`, `lh_silver`, `wh_gold`, notebooks and pipelines. Engineers only.
- `hh-audience-*` holds the Audience & Development model, reports and app.
- `hh-education-*` holds the Education Impact model, reports and app.

Domains (governance and discoverability, **not** security; admins are set on the parent and inherited by subdomains) are organized like this:

- Parent domain **Harmonia Hall**
  - Subdomain **Data Platform**
  - Subdomain **Audience & Development**
  - Subdomain **Education & Community**

Roles:

- Every environment has `sg-hh-fabric-admins` as Admin.
- Builders are Contributors in DEV and TEST, Viewers in PROD, so PROD is changed only by deployment.
- Consumers get **Org Apps**, never workspace roles.

**Microsoft deployment pattern:** this is **Pattern 2, multiple workspaces on a single capacity**, combining the hub-and-spoke, per-workload and data-mesh-via-domains sub-variants. The planned evolution is **Pattern 3, per-environment capacities** (dedicated PROD capacity, ADR-008). Full mapping: [architecture §9](../02-architecture.md#9-microsoft-fabric-deployment-pattern).

## Domain roles vs. workspace roles

They're two separate systems, and **domain roles never carry over to workspaces**. Microsoft Learn: "Domain assignment doesn't affect item visibility or accessibility… access depends on workspace role and item permissions."

| Role | Where it's set | What it allows | Here |
|---|---|---|---|
| **Domain admin** | Parent domain only; **subdomains inherit it** | Edit description and image, delegate settings, assign workspaces | `sg-hh-fabric-admins` on *Harmonia Hall* |
| **Domain contributor** | Domain | A **workspace admin** may assign *their own* workspaces to the domain | Not used; `scripts/02` assigns centrally |
| **Workspace role** (Admin, Member, Contributor, Viewer) | Each workspace | Actual access to items and data | Matrix below (`tenant.yaml › workspace_families.roles`) |

### Workspace role matrix

| Workspace | Admin | Contributor | Viewer |
|---|---|---|---|
| hh-dataplatform-dev | fabric-admins | data-engineers | none |
| hh-dataplatform-test | fabric-admins | data-engineers | none |
| hh-dataplatform-prod | fabric-admins | none | data-engineers |
| hh-audience-dev | fabric-admins | bi-developers | none |
| hh-audience-test | fabric-admins | bi-developers | analysts-audience, analysts-development (UAT sign-off) |
| hh-audience-prod | fabric-admins | none | bi-developers |
| hh-education-dev | fabric-admins | bi-developers | none |
| hh-education-test | fabric-admins | bi-developers | education-team (UAT sign-off) |
| hh-education-prod | fabric-admins | none | bi-developers |

**Cross-family access (item share, not a workspace role).** `sg-hh-bi-developers` gets an *item share* on `wh_gold` in every environment (Read + ReadData + ReadAll). That's enough to build Direct Lake models on Gold, while Bronze, Silver, notebooks and pipelines stay invisible to them. Warehouse sharing is UI-only, so it's declared in `tenant.yaml › item_shares` and verified by `scripts/09_verify_item_shares.py`.

Business consumers have **no role in PROD workspaces**. They get the **Org App**, whose audience is `sg-hh-report-viewers` plus the analyst or education groups, and semantic-model RLS controls what each person sees.

> [!NOTE]
> *"Engineers own the data plane; each business area gets its own BI workspace, domain and app. That gives us separation of duties without drowning a four-person team in workspaces."*

## Planned next domain: Finance & Operations

Not built yet, on purpose. It's the first domain to add once the audience, fundraising and education domains are running and trusted.

**Why Finance gets its own domain instead of joining an existing one:**

- **A different source of truth.** Ticketing and fundraising report sales and pledges. The finance system (the ERP and its general ledger) reports recognized revenue and cash. They rarely match mid-month, and both are correct:
  - Subscriptions sold in spring for a fall season are *deferred revenue* until the performances happen.
  - A pledge is counted when it's made, but cash arrives over months or years.
  - Refunds and exchanges land in different periods in each system.
- **A different audience and sensitivity.** General ledger detail belongs to the finance team and the auditors, not to marketing or fundraising analysts. Mixing it into those workspaces would complicate the access model (ADR-006).
- **Audit needs.** A nonprofit has an annual financial audit under nonprofit accounting standards (FASB ASC 958), plus a federal Single Audit if its federal grants pass the threshold. Auditors need reconciled numbers they can trace back to the source.

**How it would fit the current design:**

- **Workspaces:** a new family, `hh-finance-{dev,test,prod}`, in a new subdomain **Finance & Operations**, with its own deployment pipeline and a `sg-hh-finance-analysts` group. One family added to `tenant.yaml`, then re-run scripts 02–05.
- **Data:** engineers still own the data plane. The general ledger is ingested into `lh_bronze` and `lh_silver` like any other source. Gold gains a small finance star schema: `fact_gl_entry`, `dim_account`, `dim_fund` (restricted vs unrestricted, matching the existing fundraising funds) and `dim_department`.
- **First deliverable: reconciliations, not dashboards.**
  - Box-office daily settlement vs bank deposits.
  - Ticket revenue vs recognized and deferred revenue by season.
  - Gifts and pledges in the fundraising system vs contributions in the general ledger, by fund.
  - Each one shows its variance on the Data Trust page, so finance and the business can see where numbers differ and why.

**Why it waits:** there's no ERP source in this platform yet, and a four-person team gets more value from making the existing domains trusted first. Adding it costs three workspaces, one deployment pipeline and a new source connection.

> [!NOTE]
> *"Finance gets its own domain because it has its own source of truth. Ticketing says what we sold; the ledger says what we've earned and banked. My first finance deliverable would be the reconciliation between the two, so month-end and the audit stop depending on spreadsheets."*

**Revisit when:**

- Finance is reconciling box-office, fundraising and ledger numbers by hand at month-end.
- The board, the audit committee or the auditors ask for revenue reports reconciled to the ledger.
- Any other business area needs its own certified model. Add a family in `tenant.yaml`, re-run scripts 02–05, and the design scales through configuration.
