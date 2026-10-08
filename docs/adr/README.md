# Architecture Decision Records

Each ADR records one platform decision: the context, the options, the choice, and what it costs us.
They're written the way you'd defend them to a CIO. Every one ends with a **Note** (the decision in a few sentences, as you'd say it out loud) and a **"revisit when"** trigger.

| # | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-workspace-domain-topology.md) | Workspace families × environments, grouped by domain; Finance & Operations planned next | Accepted |
| [ADR-002](ADR-002-medallion-storage.md) | Lakehouse for Bronze/Silver, Warehouse for Gold | Accepted |
| [ADR-003](ADR-003-ingestion-tools.md) | Ingestion tool per source: Copy job, API notebook, Dataflow Gen2, shortcut | Accepted |
| [ADR-004](ADR-004-semantic-model-mode.md) | Direct Lake on OneLake + fixed identity for enterprise models | Accepted |
| [ADR-005](ADR-005-cicd.md) | Git on DEV + deployment pipelines; fabric-cicd as the scale-up path | Accepted |
| [ADR-006](ADR-006-security-model.md) | Layered security, groups only, enforced where each audience queries | Accepted |
| [ADR-007](ADR-007-data-quality.md) | Declarative DQ gate in Silver with quarantine | Accepted |
| [ADR-008](ADR-008-capacity-cost.md) | Capacity sizing, isolation and cost controls | Accepted |
