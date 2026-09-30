# Interview demo script (10 minutes) and defence bank

## The story in one breath

> "I rebuilt your use case as a working Fabric tenant. It has three business domains and nine workspaces across dev, test and prod, all created from one config file by idempotent REST API scripts. There's a medallion flow from three simulated source systems, with DQ gates and identity resolution, and a T-SQL star schema with SCD2. Security is layered and enforced where each audience queries. Everything is promoted through Git and deployment pipelines."

## 10-minute walkthrough

| Min | Show | Say |
|---|---|---|
| 0–1 | `docs/diagrams/01-platform-architecture.png` | Sources → Bronze/Silver lakehouses → Gold warehouse → Direct Lake models → apps. "Spark where data is messy, T-SQL where the business logic lives." |
| 1–2 | `config/tenant.yaml` + Admin portal › Domains | "The whole topology is config. Groups, domains, nine workspaces, roles and pipelines. I can rebuild it in 10 minutes, and CI validates it on every PR." |
| 2–3 | Workspace list + Manage access | "Groups only. Builders are Contributors in DEV/TEST and Viewers in PROD. Consumers get apps." |
| 3–5 | `nb_20` run log + `dq.dq_results` + quarantine | "Quality rules are YAML the business can read. Error rows are quarantined, not dropped. Identity resolution merged ticket buyers and donors into one patron. That's the foundation for 'how many buyers also give'." |
| 5–6 | `wh_gold`: SCD2 query + `rpt.vw_donor_retention` | "Point-in-time patron history, and LYBUNT defined once in SQL and mirrored in DAX, so numbers match everywhere." |
| 6–7 | Semantic model: diagram + "Test as role" | "Direct Lake on OneLake means no refresh and no DirectQuery fallback. Because it bypasses SQL security, RLS lives in the model. The same rule is enforced at each layer." |
| 7–8 | Report pages | Executive overview, sell-through, the LYBUNT call list. |
| 8–9 | Deployment pipeline + GitHub PR + CI | "Git is the source of truth for dev. Deployment pipelines are the only way into prod. fabric-cicd is the scale-up path." |
| 9–10 | ADR list | "Every decision has an ADR with the trade-offs and a 'revisit when' trigger. That's how the team keeps making the right call without me." |

## Defence bank: likely questions and answers

**"Which Fabric deployment pattern is this?"**
Pattern 2: multiple workspaces on one capacity. It uses the hub-and-spoke, per-workload and domains sub-variants. I didn't split workspaces per medallion layer, so the warehouse can read Silver directly. The next step is Pattern 3 with a dedicated PROD capacity, once reports need a performance guarantee.

**"Why not put everything in a Lakehouse?"**
A four-person team fluent in T-SQL should own the business logic. The Warehouse also gives multi-table transactions, stored procedures and SQL security for SQL consumers. See ADR-001.

**"Why Direct Lake and not Import?"**
There's no scheduled refresh and no data copy, and reports are current as soon as Gold commits. With Direct Lake *on OneLake* there's no DirectQuery fallback. The trade-off is that security must live in the model (ADR-003). For a small model with heavy Power Query, I'd still use Import.

**"Your warehouse has RLS. Why also model RLS?"**
Direct Lake on OneLake reads Delta files directly, so SQL RLS/DDM don't apply. Each audience is protected at the layer it queries (ADR-006).

**"How do you handle a late change, like a ticket return three days later?"**
The Silver MERGE updates the order, because its hash changed. The Gold fact load picks up any line whose line *or parent order* changed after the watermark, then deletes and re-inserts inside a transaction. That's idempotent and safe to retry.

**"How do you know today's numbers are complete?"**
Bronze reconciles row counts against the source manifest and fails the pipeline on a mismatch. DQ pass rates, quarantine counts and unknown-member counts all feed a Data Trust page.

**"How would you take over the partner's two pilots?"**
I wouldn't rip them up. I'd do knowledge transfer before the engagement ends, then audit them against these standards: naming, layer contracts, security, capacity usage. I'd harden one domain end to end, publish the standards, and then migrate the rest domain by domain.

**"What would you do differently at 10× scale?"**

- Separate PROD capacity.
- fabric-cicd with PR-gated deploys.
- Workspace identity and trusted access for sources.
- Mirroring for the ticketing database.
- Materialized lake views for Silver.
- Purview DLP policies.
- A data contract per source with its owner.

**"How does this help ML and GenAI?"**
Trusted, labeled, documented Gold is the prerequisite. Next steps would be a **Fabric Data Agent** over `rpt.*` views with RLS applied, and a donor propensity model trained on Silver or Gold features.

**"Capacity is expensive for a nonprofit. How do you control cost?"**
Size from Capacity Metrics evidence. Run heavy jobs off-hours. Use incremental loads, V-Order and Direct Lake instead of Import refreshes. Keep Dataflow Gen2 only where the business owns the logic. See ADR-008.

## First 90 days (if asked)

1. **Days 1–30, learn:**
   - Audit the pilots.
   - Get knowledge transfer from the partner.
   - Inventory sources and reports (including SSRS).
   - Meet the CIO, the Director of BI and the business owners.
2. **Days 31–60, standardize:**
   - Publish the architecture and governance standards (this repo's docs).
   - Set up Git and deployment pipelines, the DQ framework and capacity monitoring.
3. **Days 61–90, deliver:**
   - Ship one Certified model and a flagship app.
   - Start a self-service training program.
   - Present a 12-month roadmap to the CIO.
