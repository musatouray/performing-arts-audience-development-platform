---
name: migration
description: Use when a legacy BI estate (SSAS cubes, SSIS packages, SQL Agent jobs, SSRS or Excel reports on the cubes) has to move to Microsoft Fabric, to inventory it, rate it, and write the migration plan with waves, acceptance numbers, the parallel run, the capacity forecast and the rollback. It plans; it migrates nothing.
argument-hint: "[folder or inventory of the old estate]"
---

# Migration

The job: from the old estate to a Fabric migration plan the data engineer can defend in front of finance and the CTO. Every decision traces to the estate's own files or to an ADR; open decisions are marked, not guessed.

Input: a folder with the old estate as exported files, read-only. Typical contents: cube projects or scripts (`.bim`, `.xmla`, TMSL, `.cube`/`.dim`/`.ds` files), SSIS packages (`.dtsx`), SQL Agent job scripts, stored procedures, an SSRS catalog export (`.rdl` list), usage logs (SSAS query log or DMV exports, report execution logs), and any documentation. If usage logs are missing, say what can't be rated without them and ask for them.

The target is fixed by this repo: read [docs/02-architecture.md](../../../docs/02-architecture.md), the ADRs in [docs/adr/](../../../docs/adr/), [config/tenant.yaml](../../../config/tenant.yaml) for domains, workspace families and stages, and [docs/04-capacity-sizing.md](../../../docs/04-capacity-sizing.md). A choice that departs from an ADR is listed as an open decision with its trade-off.

## Steps

1. **Inventory:** every cube (measure groups, measures, dimensions, partitions, roles), every ETL package and job (schedule, sources, targets), every report and workbook on the cubes, with owner and consumers. One row each, counted by a script that reads the files, never estimated.
2. **Explain each object in three plain lines:** inputs, logic, output. MDX calculations and SCOPE assignments get special attention: list each one with what it computes.
3. **Lineage:** source system › ETL › relational store › cube › report, drawn from the files (Mermaid in the plan).
4. **Rate each object:** business value, size, complexity (MDX scopes, many-to-many, writeback, custom rollups are high), risk, and alive or dead (no use in the usage period, checked against month-end, fiscal year-end (June) and audit jobs).
5. **Cut list:** what not to migrate, with the reason and the owner who must agree.
6. **Requirements:** latency (daily by 7 a.m. ET unless stated), security (roles › Entra `sg-hh-*` groups, RLS and OLS, governance §4), Excel live connection, history depth, audit needs.
7. **Target per object, by the repo's patterns:**
   - ingestion by ADR-003 (Copy job, notebook, Dataflow Gen2 or shortcut, the tool follows the source);
   - Bronze and Silver lakehouses, Gold in `wh_gold` (ADR-002);
   - semantic model in Direct Lake on OneLake with a fixed identity (ADR-004), or Import where Direct Lake can't serve it (say why);
   - MDX logic rewritten as DAX measures, UDFs and calculation groups; time intelligence through the existing calculation group;
   - SSRS to paginated reports, cube-bound Excel to the certified model;
   - each new Silver table gets rules in `config/dq_rules.yaml`.
8. **Migration type per object:** lift and shift, re-platform, re-engineer, or retire.
9. **Old-to-new map:** one row per old output (measure, report, extract) with its new home and the acceptance check that proves it.
10. **Capacity forecast for the F SKU:** for each wave, the expected capacity units of the loads and refreshes and the interactive report load, against the current SKU's headroom; Direct Lake guardrails for that SKU (rows per table, files per table, model memory) against the largest fact tables; whether viewers need Pro licences (below F64). Flag the wave that forces a capacity decision, and point to the reservation-vs-pay-as-you-go trade-off.
11. **Waves:** the smallest proven subject area with a clear owner first (finance is the usual first), then by value and dependency. Avoid change windows in the organization's peak periods (season openings, holiday concerts, fiscal year-end); list the blackout dates as an open point if unknown.
12. **Three scenarios** per wave: best, expected, worst, each with effort in weeks and the main risk.
13. **Acceptance numbers** per output, with the tolerance (default: exact for money at the reported grain, unless finance agrees otherwise). These are what the `reconcile` skill checks.
14. **Parallel run:** old and new side by side, every acceptance number compared daily by the `reconcile` skill, for at least one month-end close, before cutover.
15. **History load, cutover, rollback and decommission:** how history is loaded once, the cutover steps through `dp-hh-*` deployment pipelines, how to roll back (the cube stays read-only until sign-off), and when the old jobs are switched off and by whom.
16. **Write the plan** with the open decisions marked for the data engineer, each with its options and a recommendation.

## Output

One Markdown plan in `.claude/reports/migration/` (ignored by Git), named `<estate>-plan-<yyyy-mm-dd>.md`, with the inventory table, ratings, cut list, lineage diagram, target, old-to-new map, capacity forecast, waves, scenarios, acceptance numbers, parallel run, cutover, rollback, decommission, and the open decisions. Tag every claim [high] checked, [med] likely, or [guess]. Once reviewed, the data engineer decides what moves into `docs/`; the inventory never names servers, people or tenant IDs in a committed file.

## Reads

- the old estate folder (read-only), the architecture doc, the ADRs, `config/tenant.yaml`, `config/sources.yaml`, the capacity sizing doc

## Writes

- the plan and any inventory CSVs, under `.claude/reports/migration/` only

## Never

- Never migrates, deploys or changes anything, in the old estate or in Fabric.
- Never connects to a legacy server: the user exports what is needed.
- Never rates an object as dead without the usage evidence.
