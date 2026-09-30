# ADR-001: Lakehouse for Bronze/Silver, Warehouse for Gold

**Context.** Two partner-led pilots proved the medallion approach. Now a four-person BI team, strong in T-SQL, has to own it. Sources arrive as CSV extracts, API JSON and spreadsheets. Business users only ever touch Gold, through semantic models.

## Options

| Option | Pros | Cons |
|---|---|---|
| A. All Lakehouse (Spark end to end) | One engine; cheap; flexible schemas | Gold logic in PySpark is hard for a T-SQL team to maintain; the SQL endpoint is read-only |
| B. All Warehouse | Pure T-SQL | Poor fit for raw files, schema drift, API payloads |
| **C. Lakehouse Bronze/Silver + Warehouse Gold** | Spark where data is messy; T-SQL where the business logic lives; multi-table transactions, stored procedures and SQL security (RLS, DDM, GRANT) in Gold | Two engines to know; cross-database reads need the SQL endpoint metadata sync |

## Decision

Option **C**.

- `lh_bronze` and `lh_silver` are schema-enabled lakehouses.
- `wh_gold` is a Warehouse that reads Silver through cross-database queries in the same workspace, so there's no copy.

## Consequences

- After Spark writes Silver, the notebook calls `refreshMetadata` on the SQL endpoint before Gold procedures run. This avoids the classic "the proc didn't see today's rows" failure.
- Every layer has the **same item names in every environment**. Code resolves items by name, so promotion needs no ID rewiring.

**Say it in 30 seconds:** "Spark where the data is messy, T-SQL where the business logic lives. Your team knows T-SQL, so the layer the business depends on is the layer your team can maintain without me."

**Revisit when:** Gold transforms need ML or complex Python. At that point, consider Lakehouse Gold with materialized lake views.
