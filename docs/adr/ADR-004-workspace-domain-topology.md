# ADR-004: Workspace and domain topology

## Options

| Option | Pros | Cons |
|---|---|---|
| One workspace per environment | Simple | Analysts see raw data; no separation of duties; one giant Git folder |
| Workspace per medallion layer × env (9+) | Clean layer isolation | Cross-workspace Warehouse reads aren't possible; too much overhead for four people |
| **Workspace per family × env: Data Platform + one BI workspace per business domain** | Engineers own the data plane; BI access per business area; one Org App per domain; domains map 1:1 to BI workspaces | Nine workspaces; cross-workspace model binding at promotion (ADR-003) |

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

**Say it in 30 seconds:** "Engineers own the data plane; each business area gets its own BI workspace, domain and app. That gives us separation of duties without drowning a four-person team in workspaces."

**Revisit when:** a new business area (for example, Marketing) needs its own certified model. Add a family in `tenant.yaml`, re-run scripts 02–05, and the design scales by configuration.
