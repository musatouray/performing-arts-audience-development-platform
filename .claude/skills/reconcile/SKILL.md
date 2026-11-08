---
name: reconcile
description: Use when two numbers that should agree don't — source vs ledger, Gold vs sm_finance, one stage vs another, or a legacy cube vs its Fabric replacement during a parallel run — to find the slices and rows where they diverge and the cause of each. Read-only.
argument-hint: "[the two numbers, measures or queries]"
---

# Reconcile

The job: two numbers that should match, the places where they stop matching, and the reasons, until what is left is zero or inside the agreed tolerance. It reads; it changes no number.

Input: the two sides (a query, a table, a view or a measure for each), the filter, and the number each one gives. If only one number is given, ask for the other side before starting.

## The usual pairs in this project

| Pair | Side A | Side B | Already built |
|---|---|---|---|
| Revenue to ledger | Tessitura and Diese revenue (Gold facts) | MIP ledger, `fin.fact_gl_entry` | `fin.recon_revenue_to_gl` by month, revenue stream and fund, with `tolerance_amount` and `[status]`; finance's causes in `fin.recon_note`; read through `rpt.vw_recon_revenue_to_gl` |
| Model to warehouse | an `sm_finance` measure (DAX) | the same figure in SQL on `wh_gold` | none: reconcile it when a measure changes |
| Stage to stage | DEV `wh_gold` | TEST or PROD `wh_gold` | none: after a deployment or a reload |
| Legacy to Fabric | the old cube or report (MDX/DAX over XMLA, or an export) | the Fabric model or Gold | the parallel run of a migration (see the `migration` skill) |

Start from what is already built. For revenue to ledger, read `rpt.vw_recon_revenue_to_gl` first: the lines with `[status] = 'Investigate'` and no note are the open work.

## How to read each side

- **SQL on `wh_gold`:** `uv run python scripts/query_gold.py --env dev --sql "SELECT ..."` (or `--file`). One SELECT per call, rolled back, signed in as the user, so masking and RLS apply. Large results go to CSV with `--csv .claude/reports/reconcile/<name>.csv`.
- **DAX on a semantic model:** the Power BI MCP server against a local model, or ask the user to run the query in DAX query view or a Fabric notebook (`sempy.fabric.evaluate_dax`) and save the result as CSV under `.claude/reports/reconcile/`.
- **Legacy side:** an export or a query the user runs and saves the same way. Never ask for credentials; the user runs anything that needs their sign-in on a system this repo doesn't reach.
- Default to DEV. Use TEST or PROD only when the user names it.

## Steps

1. **Name the two sides:** the query, table or measure, the filter, and the number each one gives. Write both queries into the report.
2. **Make them comparable:** the same grain, period and filters; the fiscal calendar (July to June); the same unit and sign convention (the recon table's `variance` is ledger minus source); the same time zone (America/New_York); the same treatment of blanks, unknown members and reversals. List every adjustment made.
3. **Compare the totals,** then split by one dimension at a time (month, revenue stream, fund, source system, GL account, status, load date) until a difference sits in one slice.
4. **In that slice, compare row by row:** the rows only on one side, and the rows on both sides with different values. Show the keys.
5. **Name the cause.** The usual ones here: timing at the month cut-off, an unposted batch, a reclass between funds or accounts, a late or partial delivery (check `rpt.source_freshness` and `etl.load_log`), a quarantined row (`dq.quarantine`), a join that drops or doubles rows, an SCD2 date mismatch, a type or rounding conversion, a filter that differs between the sides.
6. **After each cause,** show what is left of the difference, and continue until it is zero or inside the tolerance.
7. **Say which side is right,** with the proof from the source, or say it can't be proven from what was read. Tag every claim [high] checked, [med] likely, or [guess].
8. **For revenue to ledger:** draft one `fin.recon_note` row per explained line (month, stream, fund, cause, note, resolution `Explained` or `Corrected`) for finance to review. Finance enters it; this skill never writes it.
9. Give the result as one web page.

## Output

One self-contained HTML file in `.claude/reports/reconcile/` (ignored by Git), named `<topic>-<yyyy-mm-dd>.html`: the two numbers on top with the difference; the adjustments that made them comparable; the drill-down from the total to the slices; the rows behind each cause; what is left after each cause; the verdict; the queries used; the drafted notes. No fonts, scripts or images from the network. Personal data (names, emails, phones, addresses) masked on the page.

## Reads

- `wh_gold` through `scripts/query_gold.py`, results the user exported, `src/warehouse/*.sql` (how each side is built), `config/sources.yaml`, `config/dq_rules.yaml`, `src/semantic_model/`

## Writes

- the report and its CSVs, under `.claude/reports/reconcile/` only

## Never

- Never changes a number on either side, never inserts a `fin.recon_note`, never reruns a load.
- Never calls a difference "rounding" or "timing" without showing the rows.
- Never puts query results or personal data in a committed file.
