"""Step 13: deploy the Gold warehouse schema (src/warehouse/*.sql) to one environment's wh_gold.

Deployment pipelines copy item definitions, not warehouse objects, and the SQL files cross-reference
lh_silver, which warehouse deployment doesn't handle well. So the schema is deployed from the repo, the
same files in the same order in every environment: the repo is the single source of truth for Gold.

Every file can be run again safely (CREATE ... IF NOT EXISTS, CREATE OR ALTER), so this is also how a
schema change reaches TEST and PROD: merge it, then run this script for that environment.

  * Signs in with your Entra account (az login, or a browser window) or, in CI, a service principal
    from the environment (AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET). No SQL passwords.
  * Finds the warehouse's SQL endpoint through the Fabric API, so no server names live in the repo.
  * Runs 61_security_users.local.sql (real sign-in names, ignored by Git) when it exists.
  * Stops at the first failing batch and says which file and batch failed.
  * First deployment to an empty stage: a few views read lakehouse tables (dq.dq_results, audit.run_log) that
    only exist after the first pipeline run. Those batches are set aside and listed, and the script exits with
    code 2 and the bootstrap steps: run the pipeline once, run this script again, rerun the failed activity.

Run: uv run python scripts/13_deploy_gold_sql.py --env test [--dry-run] [--start-at 70]
"""

import re
import struct
import sys
import time
from pathlib import Path

from lib.fabric import ROOT, Client, banner, credential, find_item, require_workspace, std_args, ws_name

SQL_DIR = Path(ROOT) / "src" / "warehouse"
# 40 runs again at the end: its orchestrator (etl.usp_load_gold) calls procedures from 70 to 80.
ORDER = ["00_schemas_and_etl_framework.sql", "10_dimensions_ddl.sql", "20_facts_ddl.sql", "30_load_dimensions.sql",
         "40_load_facts.sql", "50_reporting_views.sql", "60_security.sql", "61_security_users.local.sql",
         "70_finance_and_venue_ops.sql", "72_budget_and_cash.sql", "75_marketing.sql", "80_source_freshness.sql",
         "40_load_facts.sql"]
GO = re.compile(r"^\s*GO\s*(--.*)?$", re.IGNORECASE | re.MULTILINE)


def batches(path: Path) -> list[str]:
    return [b.strip() for b in GO.split(path.read_text(encoding="utf-8")) if b and b.strip() and not GO.fullmatch(b)]


def connect(server: str):
    import pyodbc

    drivers = sorted(d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d)
    if not drivers:
        sys.exit("No SQL Server ODBC driver found. Install ODBC Driver 18 for SQL Server.")
    tok = credential().get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    conn_str = f"Driver={{{drivers[-1]}}};Server={server},1433;Database=wh_gold;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60"
    return pyodbc.connect(conn_str, attrs_before={1256: struct.pack(f"<I{len(tok)}s", len(tok), tok)}, autocommit=True)


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", required=True, choices=["dev", "test", "prod"])
    ap.add_argument("--start-at", help="skip files before this prefix (for example 70), to resume after a fix")
    a = ap.parse_args()

    missing = [f for f in ORDER if not (SQL_DIR / f).exists()]
    if any(not f.endswith(".local.sql") for f in missing):
        sys.exit(f"missing SQL files: {missing}")
    if missing:
        print("note: 61_security_users.local.sql not found; skipping it (copy the .example.sql and fill it in)")
    files = [f for f in ORDER if f not in missing]
    if a.start_at:
        first = next((i for i, f in enumerate(files) if f.startswith(a.start_at)), None)
        if first is None:
            sys.exit(f"--start-at {a.start_at}: no file with that prefix")
        files = files[first:]

    c = Client(dry_run=a.dry_run)
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    wh = find_item(c, ws["id"], "wh_gold", "Warehouse")
    if not wh:
        sys.exit(f"wh_gold not found in {ws['displayName']}: run 03_create_items.py first")
    server = c.call("GET", f"/workspaces/{ws['id']}/warehouses/{wh['id']}", write=False)["properties"]["connectionString"]
    banner(f"Gold schema -> {ws['displayName']}/wh_gold")

    plan = [(f, batches(SQL_DIR / f)) for f in files]
    for f, bs in plan:
        print(f"   {f:<36} {len(bs):>3} batches")
    if a.dry_run:
        print("\n(dry run: nothing executed)")
        return

    conn = connect(server)
    cur = conn.cursor()
    deferred, deferred_names = [], set()
    for f, bs in plan:
        t0 = time.time()
        for i, b in enumerate(bs, 1):
            try:
                cur.execute(b)
                while cur.nextset():   # drain result sets and messages so errors in later statements surface
                    pass
            except Exception as e:
                first_line = next((ln for ln in b.splitlines() if ln.strip() and not ln.strip().startswith("--")), "")[:100]
                if waits_for_lakehouse(str(e), deferred_names):
                    deferred.append(f"{f} batch {i}: {first_line}")
                    deferred_names.update(created_objects(b))
                    continue
                sys.exit(f"\nFAILED in {f}, batch {i} of {len(bs)} ({first_line} ...):\n{e}\n"
                         f"Fix it, then resume with --start-at {f[:2]}")
        print(f"   ok {f} ({time.time() - t0:.0f}s)")

    if deferred:
        print(f"\n{len(deferred)} batch(es) set aside: they read lakehouse tables that don't exist in this stage yet.")
        for d in deferred:
            print(f"   - {d}")
        print(f"\nFirst deployment to {ws['displayName']}:\n"
              "  1. Run pl_daily_load once. Bronze and Silver create their tables; sp_load_gold fails at the\n"
              "     source-freshness snapshot, because its view isn't there yet. That's expected, once.\n"
              f"  2. Run this script again: uv run python scripts/13_deploy_gold_sql.py --env {a.env}\n"
              "  3. In the Monitoring hub, rerun the pipeline from the failed activity.")
        sys.exit(2)
    print(f"\nDone. Next: run pl_daily_load in {ws['displayName']} with load_date blank.")


def waits_for_lakehouse(message: str, deferred_names: set[str]) -> bool:
    """True when a batch failed only because something it reads doesn't exist yet: a lakehouse table the first
    pipeline run creates (error 208 on lh_bronze / lh_silver), or an object set aside earlier in this run
    (a GRANT on a deferred view, error 208 or 15151)."""
    msg = message.lower()
    if "(208)" not in msg and "(15151)" not in msg:
        return False
    return "lh_silver." in msg or "lh_bronze." in msg or any(n in msg for n in deferred_names)


def created_objects(batch: str) -> set[str]:
    """Names of the views and procedures a batch creates, e.g. {'rpt.vw_source_freshness', 'vw_source_freshness'}."""
    out = set()
    for m in re.finditer(r"CREATE\s+(?:OR\s+ALTER\s+)?(?:VIEW|PROCEDURE|FUNCTION)\s+([\w\.\[\]]+)", batch, re.IGNORECASE):
        name = m.group(1).replace("[", "").replace("]", "").lower()
        out.update({name, name.split(".")[-1]})
    return out


if __name__ == "__main__":
    main()
