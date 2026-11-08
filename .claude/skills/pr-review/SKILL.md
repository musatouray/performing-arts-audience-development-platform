---
name: pr-review
description: Use before a change is merged from dev into main (a file, the current diff or a branch), to review it pass by pass against this project's Fabric standards, with pushback. Read-only; it never edits, commits or pushes.
argument-hint: "[branch, diff or file]"
---

# Pull request review

The job: review one change in fixed passes, in this order, against this repo's own standards, and report every finding with its fix. It never edits.

Input: a file, the current diff (`git diff`), or a branch before its merge (`git diff main...dev` by default).

The standards are the files, not memory: [docs/03-governance-standards.md](../../../docs/03-governance-standards.md), the ADRs in [docs/adr/](../../../docs/adr/), and `pyproject.toml` for code style. Quote the rule a finding breaks.

## Steps

1. **Scope.** The files, the lines and the purpose of the change. Group the files by area: `scripts/`, `config/`, `src/warehouse/`, `fabric/` (Fabric Git items), `src/semantic_model/`, `docs/`, `.github/`.
2. **Secrets and tenant values** (governance §4, "Secrets and tenant-specific values"):
   - No GUIDs, server names, storage accounts, SharePoint URLs, emails or sign-in names in a committed file. They belong in `.env` (with the name added to `.env.example`), `config/.generated/` or a `*.local.*` file.
   - No passwords, keys or tokens anywhere. Inside Fabric: connections or Key Vault via `notebookutils.credentials.getSecret`.
   - Notebooks and pipelines take stage values from the variable libraries (`vl_platform`, `vl_finance`), never a hard-coded workspace or item ID. IDs that Fabric Git integration writes under `fabric/` are expected and not a finding.
   - Screenshots added under `docs/screenshots/` show no tenant names, emails, URLs or IDs.
3. **Access and personal data** (governance §4):
   - Access only through `sg-hh-*` groups; never a person granted directly. SQL grants and RLS roles name groups or `sec.*` tables.
   - A new column with personal data is tagged `pii` or `restricted` in `config/sources.yaml`; restricted columns stay out of OneLake security roles, are masked in SQL (DDM) and hidden in models (OLS).
   - No payment card fields; education data stays aggregate.
4. **Correctness:**
   - Money is `decimal`, never `float`. Keys keep their type (IDs as strings keep leading zeros).
   - Same result on a rerun and on a backfill: SQL files stay safe to re-run (`CREATE OR ALTER`, `IF OBJECT_ID(...) IS NULL`), loads are incremental or idempotent (watermark, hash MERGE), and every write is tied to the pipeline `run_id` in `etl.load_log`.
   - Grain: a join that can double or drop rows is called out with the key it joins on.
5. **Deployment order.** A new file in `src/warehouse/` is added to `ORDER` in `scripts/13_deploy_gold_sql.py`. A new object that reads a lakehouse table is noted for the first-load bootstrap. A Fabric item change still deploys through `dp-hh-*` (DEV › TEST › PROD); nothing is edited in TEST or PROD by hand.
6. **Data quality.** A new Silver table or column has its rules in `config/dq_rules.yaml` (severity error or warn). A new Gold output that finance reads has a reconciliation or a reason why not.
7. **Semantic model.** New measures have a description and a format string, reuse the UDFs and the calculation group instead of copying logic, and respect the RLS roles in `src/semantic_model/rls_roles.md`. Direct Lake stays Direct Lake: no change that forces DirectQuery fallback.
8. **Capacity (F SKU).** What the change costs on a small capacity: full scans where an incremental read would do, Spark where a Python notebook or T-SQL would do, a schedule inside business hours, a new refresh that collides with `pl_daily_load`.
9. **Tests and CI.** Run the CI checks locally, read-only: `uv run ruff check .`, `uv run python scripts/validate_config.py`, `uv run pytest -q`. Report what passed. Never run a script that calls a Fabric write API or deploys SQL.
10. **Duplication.** Logic that already exists in `scripts/lib/`, `etl.*` procedures or the UDFs.
11. **Documentation.** The runbook (`docs/01-runbook.md`), `TODO.md`, and an ADR when the change is a decision with a trade-off. Every ADR ends with "revisit when".
12. **Style.** `pyproject.toml` ruff rules (line length 140); keep the file's existing line endings (most files are CRLF).
13. **Every finding:** the risk (high, medium, low), the file and line, the rule it breaks with its source file, and the suggested change. Tag each claim [high] checked, [med] likely, or [guess].
14. **Verdict:** approve, or changes requested.

## Pushback

A finding the author declines stays in the report as declined, with the reason given. It is never dropped and never quietly downgraded.

## Output

One self-contained HTML file in `.claude/reports/pr-review/` (ignored by Git), named `<branch>-<yyyy-mm-dd>.html`: the change and the verdict on top, the CI results, then every finding with the code, the rule and the suggested change, high risk first. No fonts, scripts or images from the network. Say where the file is; give a short summary in the chat.

## Reads

- the change, the standards and ADRs, `config/*.yaml`, the tests

## Writes

- the report only

## Never

- Never edits the change, never commits, pushes or merges, never runs a deploy or a Fabric write API.
