"""Step 11: load the generated ticketing data into the ticketing database (the mock Tessitura).

This plays the part of the ticketing system itself. Each run applies one or more
days of sales, returns and address changes to the tix tables, the way the real
system would during the day. The Fabric Copy job then copies the changes to Bronze.

  * The first run creates schema tix and its tables, based on config/sources.yaml.
  * Each data/ticketing_db/<table>/load_date=D folder is applied once, oldest first.
    tix._load_history remembers which days are done.
  * New rows are inserted. Changed rows are updated and get a new updated_at.
    Unchanged rows are left alone, so the Copy job doesn't copy them again.

Works with SQL Server on your own computer (the lab setup) or Azure SQL Database.
How it signs in is set by TICKETING_SQL_AUTH in .env:
  windows  your Windows account (on-premises SQL Server)
  sql      a SQL login from SQL_USER and SQL_PASSWORD
  entra    your az login account (Azure SQL Database; the default)
On SQL Server the database is created if it doesn't exist yet.
Needs the Microsoft ODBC Driver 18 for SQL Server on this computer.

Run: uv run python scripts/11_load_ticketing_db.py [--load-date 2026-09-28] [--dry-run]
"""

import csv
import os
import struct
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from lib.config import sources_config, unfilled
from lib.fabric import ROOT, banner, credential, std_args

SQL_TYPES = {"string": "nvarchar(400)", "int": "int", "boolean": "bit", "date": "date", "timestamp": "datetime2(0)"}
BATCH = 5000


def sql_type(t: str) -> str:
    return t if t.startswith("decimal") else SQL_TYPES[t]


def to_python(v: str, t: str):
    """CSV text to the Python value the driver expects. Empty text stays empty for text columns."""
    if v == "" or v is None:
        return "" if t == "string" and v == "" else None
    if t == "int":
        return int(v)
    if t == "boolean":
        return v in ("True", "true", "1")
    if t == "date":
        return date.fromisoformat(v)
    if t == "timestamp":
        return datetime.fromisoformat(v)
    if t.startswith("decimal"):
        return Decimal(v)
    return v


def ensure_database(pyodbc, conn_str: str, database: str, auth: str):
    """On SQL Server, create the database the first time. (Azure SQL databases are created in the portal.)"""
    master = conn_str.replace(f"Database={database};", "Database=master;")
    login = ";Trusted_Connection=yes" if auth == "windows" else f";UID={os.environ['SQL_USER']};PWD={os.environ['SQL_PASSWORD']}"
    with pyodbc.connect(master + login, autocommit=True) as conn:
        if conn.execute("SELECT DB_ID(?)", database).fetchone()[0] is None:
            print(f"   creating database {database}")
            conn.execute(f"CREATE DATABASE [{database}]")


def connect(db: dict):
    import pyodbc

    drivers = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
    if not drivers:
        sys.exit("No SQL Server ODBC driver found. Install ODBC Driver 18 for SQL Server:\n"
                 "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server")
    auth = os.getenv("TICKETING_SQL_AUTH", "entra").lower()
    # A local SQL Server usually has a self-signed certificate. Trusting it is fine on your own
    # computer; never turn this on for a server you reach over a network.
    trust = "yes" if os.getenv("TICKETING_SQL_TRUST_SERVER_CERT", "no").lower() in ("yes", "true", "1") else "no"
    conn_str = (f"Driver={{{sorted(drivers)[-1]}}};Server={db['server']};Database={db['database']};"
                f"Encrypt=yes;TrustServerCertificate={trust};Connection Timeout=60")
    if auth in ("windows", "sql"):
        ensure_database(pyodbc, conn_str, db["database"], auth)
    for attempt in range(6):
        try:
            if auth == "windows":
                return pyodbc.connect(f"{conn_str};Trusted_Connection=yes")
            if auth == "sql":
                return pyodbc.connect(f"{conn_str};UID={os.environ['SQL_USER']};PWD={os.environ['SQL_PASSWORD']}")
            tok = credential().get_token("https://database.windows.net/.default").token.encode("utf-16-le")
            return pyodbc.connect(conn_str, attrs_before={1256: struct.pack(f"<I{len(tok)}s", len(tok), tok)})
        except pyodbc.Error as e:
            # A free-tier database pauses when nobody uses it and takes about a minute to wake up.
            if "40613" not in str(e) or attempt == 5:
                raise
            print("   the database is waking up, trying again in 20s ...")
            time.sleep(20)


def create_table_sql(schema: str, ent: dict) -> str:
    cols = [f"[{c}] {sql_type(t)} {'NOT NULL' if c in ent['primary_key'] else 'NULL'}" for c, t in ent["columns"].items()]
    if "updated_at" not in ent["columns"]:
        cols.append("[updated_at] datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()")
    pk = ", ".join(f"[{k}]" for k in ent["primary_key"])
    name = ent["name"]
    return (f"IF OBJECT_ID('{schema}.{name}') IS NULL BEGIN\n"
            f"  CREATE TABLE [{schema}].[{name}] (\n    " + ",\n    ".join(cols) + f",\n"
            f"    CONSTRAINT [PK_{schema}_{name}] PRIMARY KEY ({pk}));\n"
            f"  CREATE INDEX [IX_{schema}_{name}_updated_at] ON [{schema}].[{name}] ([updated_at]);  -- the Copy job filters on this\n"
            "END;")


def merge_sql(schema: str, ent: dict) -> str:
    cols = list(ent["columns"])
    keys = ent["primary_key"]
    compare = [c for c in cols if c not in keys and c != "updated_at"]
    on = " AND ".join(f"t.[{k}] = s.[{k}]" for k in keys)
    new_ts = "COALESCE(s.[updated_at], SYSUTCDATETIME())" if "updated_at" in cols else "SYSUTCDATETIME()"
    insert_cols = cols + ([] if "updated_at" in cols else ["updated_at"])
    insert_vals = [f"s.[{c}]" for c in cols] + ([] if "updated_at" in cols else ["SYSUTCDATETIME()"])
    # EXCEPT compares the columns and treats two NULLs as equal, so only real changes count.
    return f"""
SET NOCOUNT ON;
DECLARE @actions TABLE (act nvarchar(10));
MERGE [{schema}].[{ent['name']}] AS t
USING [{schema}].[_stage_{ent['name']}] AS s ON {on}
WHEN MATCHED AND EXISTS (SELECT {', '.join(f's.[{c}]' for c in compare)} EXCEPT SELECT {', '.join(f't.[{c}]' for c in compare)})
    THEN UPDATE SET {', '.join(f'[{c}] = s.[{c}]' for c in compare)}, [updated_at] = {new_ts}
WHEN NOT MATCHED
    THEN INSERT ({', '.join(f'[{c}]' for c in insert_cols)}) VALUES ({', '.join(insert_vals)})
OUTPUT $action INTO @actions;
SELECT COALESCE(SUM(CASE WHEN act = 'INSERT' THEN 1 END), 0), COALESCE(SUM(CASE WHEN act = 'UPDATE' THEN 1 END), 0) FROM @actions;
"""


def load_table_day(cur, schema: str, ent: dict, path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0, 0, 0
    cols, types = list(ent["columns"]), ent["columns"]
    latest = {tuple(r[k] for k in ent["primary_key"]): r for r in rows}       # one row per key, the last one wins
    data = [[to_python(r.get(c), types[c]) for c in cols] for r in latest.values()]
    col_list = ", ".join(f"[{c}]" for c in cols)
    stage = f"[{schema}].[_stage_{ent['name']}]"           # a work table for this load, rebuilt each time
    cur.execute(f"DROP TABLE IF EXISTS {stage}; SELECT TOP 0 {col_list} INTO {stage} FROM [{schema}].[{ent['name']}];")
    cur.fast_executemany = True
    insert = f"INSERT INTO {stage} ({col_list}) VALUES ({', '.join('?' * len(cols))})"
    for i in range(0, len(data), BATCH):
        cur.executemany(insert, data[i:i + BATCH])
    cur.execute(merge_sql(schema, ent))
    inserted, updated = cur.fetchone()
    cur.execute(f"DROP TABLE {stage};")
    return len(rows), inserted, updated


def main():
    ap = std_args(__doc__)
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "ticketing_db")
    ap.add_argument("--load-date", help="only apply this day (default: every day not applied yet)")
    a = ap.parse_args()

    src = next(s for s in sources_config()["sources"] if s["source"] == "ticketing")
    db = src["ingestion"]["source_db"]
    schema = db["schema"]
    if unfilled(db):
        sys.exit("Add TICKETING_SQL_SERVER and TICKETING_SQL_DATABASE to .env first.")

    days = sorted({p.name.split("=")[1] for p in a.data.glob("*/load_date=*")})
    if a.load_date:
        days = [d for d in days if d == a.load_date]
    if not days:
        sys.exit(f"No data in {a.data}. Run: uv run python -m data_generator.generate full")
    banner(f"Ticketing database {db['server']}/{db['database']} (schema {schema})")

    if a.dry_run:
        for ent in src["entities"]:
            print(create_table_sql(schema, ent), "\n")
        print(f"   [dry-run] would apply {len(days)} day(s): {days[0]} .. {days[-1]}")
        return

    conn = connect(db)
    cur = conn.cursor()
    cur.execute(f"IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA [{schema}]');")
    for ent in src["entities"]:
        cur.execute(create_table_sql(schema, ent))
    cur.execute(f"IF OBJECT_ID('{schema}._load_history') IS NULL CREATE TABLE [{schema}].[_load_history] "
                "(load_date date NOT NULL, table_name nvarchar(100) NOT NULL, rows_in int, inserted int, updated int, "
                "loaded_at datetime2(0) DEFAULT SYSUTCDATETIME(), PRIMARY KEY (load_date, table_name));")
    conn.commit()
    done = {(str(r[0]), r[1]) for r in cur.execute(f"SELECT load_date, table_name FROM [{schema}].[_load_history]").fetchall()}

    for d in days:
        print(f"\n  load_date={d}")
        for ent in src["entities"]:                       # lookup tables first, in the order of sources.yaml
            if (d, ent["name"]) in done:
                continue
            path = a.data / ent["name"] / f"load_date={d}" / f"{ent['name']}.csv"
            if not path.exists():
                continue
            rows_in, ins, upd = load_table_day(cur, schema, ent, path)
            cur.execute(f"INSERT INTO [{schema}].[_load_history] (load_date, table_name, rows_in, inserted, updated) "
                        "VALUES (?, ?, ?, ?, ?)", d, ent["name"], rows_in, ins, upd)
            conn.commit()
            print(f"   {ent['name']:<15} {rows_in:>9,} in   {ins:>9,} new   {upd:>7,} changed")
    print("\n  Done. The next Copy job run picks up the new and changed rows.")


if __name__ == "__main__":
    main()
