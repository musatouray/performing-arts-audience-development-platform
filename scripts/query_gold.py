"""Read-only query against one environment's wh_gold, for the reconcile skill and ad-hoc checks.

  * Signs in like 13_deploy_gold_sql.py: your Entra account (az login, or a browser window), or a service
    principal from the environment. No SQL passwords.
  * Finds the warehouse's SQL endpoint through the Fabric API, so no server names live in the repo.
  * Runs ONE statement that must be a SELECT (or WITH ... SELECT), inside a transaction that is always rolled
    back, so it can't change anything even by mistake. You see only what your account is granted: dynamic data
    masking and row-level security still apply.
  * Prints up to --max-rows rows, or writes every row to a CSV under .claude/reports/ (ignored by Git), so query
    results never end up in a committed file.

Run: uv run python scripts/query_gold.py --env dev --sql "SELECT TOP 20 * FROM rpt.vw_recon_revenue_to_gl"
     uv run python scripts/query_gold.py --env dev --file q.sql --csv .claude/reports/reconcile/recon.csv
"""

import argparse
import csv
import re
import struct
import sys
from pathlib import Path

from lib.fabric import ROOT, Client, credential, find_item, require_workspace, ws_name

REPORTS = (Path(ROOT) / ".claude" / "reports").resolve()
WRITES = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|deny|into|"
    r"backup|restore|dbcc|openrowset|opendatasource|sp_\w+|xp_\w+)\b",
    re.IGNORECASE,
)


def code_only(sql: str) -> str:
    """The statement without comments and string literals, so keywords inside text don't count."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def check_read_only(sql: str) -> None:
    code = code_only(sql).strip().rstrip(";").strip()
    if not code:
        sys.exit("empty query")
    if ";" in code:
        sys.exit("one statement only")
    if not re.match(r"(select|with)\b", code, re.IGNORECASE):
        sys.exit("only SELECT (or WITH ... SELECT) queries are allowed")
    if m := WRITES.search(code):
        sys.exit(f"refused: '{m.group(0)}' is not allowed in a read-only query")


def csv_path(arg: str) -> Path:
    p = Path(arg)
    p = (p if p.is_absolute() else Path(ROOT) / p).resolve()
    if REPORTS not in p.parents:
        sys.exit(f"--csv must be under {REPORTS} (ignored by Git), so query results are never committed")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def connect(server: str):
    import pyodbc

    drivers = sorted(d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d)
    if not drivers:
        sys.exit("No SQL Server ODBC driver found. Install ODBC Driver 18 for SQL Server.")
    tok = credential().get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    conn_str = f"Driver={{{drivers[-1]}}};Server={server},1433;Database=wh_gold;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60"
    return pyodbc.connect(conn_str, attrs_before={1256: struct.pack(f"<I{len(tok)}s", len(tok), tok)}, autocommit=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sql", help="the query text")
    src.add_argument("--file", help="a .sql file holding the query")
    ap.add_argument("--csv", help="write every row to this CSV (must be under .claude/reports/)")
    ap.add_argument("--max-rows", type=int, default=200, help="rows to print when not writing a CSV")
    a = ap.parse_args()

    sql = a.sql if a.sql is not None else Path(a.file).read_text(encoding="utf-8")
    check_read_only(sql)
    out = csv_path(a.csv) if a.csv else None

    c = Client(dry_run=False)
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    wh = find_item(c, ws["id"], "wh_gold", "Warehouse")
    if not wh:
        sys.exit(f"wh_gold not found in {ws['displayName']}")
    server = c.call("GET", f"/workspaces/{ws['id']}/warehouses/{wh['id']}", write=False)["properties"]["connectionString"]

    conn = connect(server)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        if out:
            n = 0
            with out.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                while rows := cur.fetchmany(5000):
                    w.writerows(rows)
                    n += len(rows)
            print(f"{n} rows -> {out}")
        else:
            rows = cur.fetchmany(a.max_rows + 1)
            print("\t".join(cols))
            for r in rows[: a.max_rows]:
                print("\t".join("" if v is None else str(v) for v in r))
            if len(rows) > a.max_rows:
                print(f"... more than {a.max_rows} rows; use --csv for all of them")
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
