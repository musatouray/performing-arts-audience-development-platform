# ADR-007: Data quality

## Options

| Option | Pros | Cons |
|---|---|---|
| **Declarative rules (YAML) + a Silver DQ engine in PySpark with quarantine** | Rules are reviewable in PRs and owned with the business; error rows never reach Gold; full audit (`dq.dq_results`, `dq.quarantine`) | Some framework code to own |
| Materialized lake views with constraints | Declarative and native; drop or fail on violation | Less control over quarantine and reporting; newer feature |
| Great Expectations / Soda | Rich rule library | Extra dependency and learning curve for a small team |

## Decision

Declarative rules in `config/dq_rules.yaml`, enforced in `nb_20_silver_transform`:

- **error** rules quarantine the row.
- **warn** rules log the violation and load the row.

Around that:

- **Load-completeness reconciliation** against source manifests runs in Bronze and fails the pipeline on a mismatch.
- **Gold integrity** checks (`rpt.vw_gold_integrity`) count unknown-member (-1) facts.
- **Activator** alerts the data owner when an error rule fires.

**Say it in 30 seconds:** "Quality rules live in config that the business can read, bad rows are quarantined rather than silently dropped, and every run leaves a pass rate that feeds a Data Trust page. That's how dashboards become dashboards people trust."
