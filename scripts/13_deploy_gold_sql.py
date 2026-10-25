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
    for f, bs in plan:
        t0 = time.time()
        for i, b in enumerate(bs, 1):
            try:
                cur.execute(b)
                while cur.nextset():   # drain result sets and messages so errors in later statements surface
                    pass
            except Exception as e:
                first_line = next((ln for ln in b.splitlines() if ln.strip() and not ln.strip().startswith("--")), "")[:100]
                sys.exit(f"\nFAILED in {f}, batch {i} of {len(bs)} ({first_line} ...):\n{e}\n"
                         f"Fix it, then resume with --start-at {f[:2]}")
        print(f"   ok {f} ({time.time() - t0:.0f}s)")
    print(f"\nDone. Next: run pl_daily_load in {ws['displayName']} with load_date blank.")


if __name__ == "__main__":
    main()
