# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # nb_00_common: shared helpers
# 
# The other notebooks load this one with `%run nb_00_common`.
# It finds the lakehouses, reads the config, logs each run and runs the data quality checks.
# 
# Lakehouses are looked up by name. The names are the same in dev, test and prod,
# so this code works in every environment without changes.

# CELL ********************

import json
import re
import uuid
from datetime import datetime, timezone

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

try:                                    # built into Fabric notebooks
    import notebookutils as nbu
except ImportError:                     # older Fabric runtimes
    from notebookutils import mssparkutils as nbu  # type: ignore

WORKSPACE_ID = nbu.runtime.context["currentWorkspaceId"]
ONELAKE = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com"
BRONZE, SILVER = "lh_bronze", "lh_silver"
RUN_ID = str(uuid.uuid4())


def lakehouse_path(lakehouse: str) -> str:
    """Storage path of a lakehouse in this workspace, found by name."""
    return f"{ONELAKE}/{nbu.lakehouse.get(lakehouse)['id']}"


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tbl(lakehouse: str, schema: str, table: str) -> str:
    """Full table name: lakehouse.schema.table.
    Table names can't be passed to SQL as parameters, so every name used in a SQL
    statement comes through here and must be a plain identifier (letters, digits, _)."""
    for part in (lakehouse, schema, table):
        if not _SAFE_NAME.match(part):
            raise ValueError(f"unsafe table name part: {part!r}")
    return f"`{lakehouse}`.`{schema}`.`{table}`"


def table_exists(name: str) -> bool:
    try:
        spark.table(name).limit(0).collect()
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_schemas(lakehouse: str, schemas: list[str]):
    for s in schemas:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{lakehouse}`.`{s}`")


def load_json_config(name: str) -> dict:
    """Read a config file (sources or dq_rules) uploaded by scripts/06."""
    path = f"{lakehouse_path(BRONZE)}/Files/config/{name}.json"
    return json.loads("".join(r.value for r in spark.read.text(path, wholetext=True).collect()))


def bronze_schema(src: dict) -> str:
    """Bronze schema for a source. Usually the source name; education lands in dbo."""
    return (src.get("ingestion") or {}).get("bronze_schema") or src["source"]


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# MARKDOWN ********************

# ## Run log
# One row per table per step, used by the pipeline health report.
# Each layer logs to its own lakehouse (`<lakehouse>.audit.run_log`), so a Bronze
# notebook never needs write access to Silver.

# CELL ********************

def log_run(notebook: str, entity: str, stage: str, rows_in: int, rows_out: int,
            rows_quarantined: int = 0, status: str = "Succeeded", message: str = "", started=None,
            lakehouse: str = SILVER):
    ensure_schemas(lakehouse, ["audit"])
    row = [(RUN_ID, notebook, entity, stage, rows_in, rows_out, rows_quarantined, status, message[:4000],
            started or now_utc(), now_utc())]
    cols = "run_id string, notebook string, entity string, stage string, rows_in long, rows_out long, " \
           "rows_quarantined long, status string, message string, started_at timestamp, ended_at timestamp"
    spark.createDataFrame(row, cols).write.mode("append").saveAsTable(tbl(lakehouse, "audit", "run_log"))
    print(f"[{stage}] {entity}: in={rows_in:,} out={rows_out:,} quarantined={rows_quarantined:,} {status}")

# MARKDOWN ********************

# ## Data quality checks
# Rules come from `config/dq_rules.yaml`.
# * error: the row is moved to `dq.quarantine` and not loaded
# * warn: the row is loaded and the problem is counted in `dq.dq_results`

# CELL ********************

def _violation(df: DataFrame, rule: dict):
    c, r = F.col(rule.get("column", "")), rule["rule"]
    if r == "not_null":
        return c.isNull()
    if r == "regex":
        bad = ~c.rlike(rule["pattern"])
        return (c.isNotNull() & bad) if rule.get("allow_null") else (c.isNull() | bad)
    if r == "accepted_values":
        return c.isNotNull() & ~c.isin(rule["values"])
    if r == "range":
        return c.isNotNull() & ((c < F.lit(rule["min"])) | (c > F.lit(rule["max"])))
    if r == "not_future":
        return c.isNotNull() & (c.cast("timestamp") > F.current_timestamp())
    raise ValueError(f"unknown rule {r}")


def apply_dq(df: DataFrame, entity: str, rules_cfg: dict, restricted: list[str] | None = None):
    """Run the checks for one table. Returns the good rows, how many were set aside, and the
    cached working DataFrame, which the caller unpersists once it has used the good rows.
    Restricted columns (contact details) are hashed in the quarantine copy: you can still
    tell two bad rows apart, but nobody can read the email or phone number there."""
    rules = rules_cfg.get("rules", {}).get(entity, [])
    if not rules:
        return df, 0, None
    ensure_schemas(SILVER, ["dq"])
    flagged = df
    names = []
    for i, rule in enumerate(rules):
        flag = f"_dq_{i}"
        if rule["rule"] == "foreign_key":
            src, ent = rule["ref_entity"].split(".")
            ref_name = tbl(SILVER, src, ent)
            if not table_exists(ref_name):
                continue
            ref = spark.table(ref_name).select(F.col(rule["ref_column"]).alias("_fk")).distinct().withColumn(flag + "_ok", F.lit(True))
            flagged = (flagged.join(ref, flagged[rule["column"]] == ref["_fk"], "left")
                       .withColumn(flag, F.col(rule["column"]).isNotNull() & F.col(flag + "_ok").isNull())
                       .drop("_fk", flag + "_ok"))
        else:
            flagged = flagged.withColumn(flag, _violation(flagged, rule))
        names.append((flag, rule))
    flagged = flagged.cache()
    total = flagged.count()

    # Count the failures for every rule in one pass.
    agg = flagged.agg(*[F.sum(F.col(f).cast("int")).alias(f) for f, _ in names]).collect()[0].asDict()
    results = [(RUN_ID, entity, r["rule"], r.get("column"), r["severity"], int(agg[f] or 0), total,
                float(1 - (agg[f] or 0) / total) if total else 1.0, now_utc()) for f, r in names]
    spark.createDataFrame(results, "run_id string, entity string, rule string, column_name string, severity string, "
                                   "failed_rows long, total_rows long, pass_rate double, checked_at timestamp") \
        .write.mode("append").saveAsTable(tbl(SILVER, "dq", "dq_results"))

    error_flags = [f for f, r in names if r["severity"] == "error"]
    is_bad = F.lit(False)
    for f in error_flags:
        is_bad = is_bad | F.coalesce(F.col(f), F.lit(False))
    failures = F.concat_ws(",", *[F.when(F.col(f), F.lit(f"{r['rule']}:{r.get('column')}")) for f, r in names if r["severity"] == "error"])
    flag_cols = [f for f, _ in names]
    bad = flagged.where(is_bad)
    n_bad = bad.count()
    if n_bad:
        (bad.select(F.lit(RUN_ID).alias("run_id"), F.lit(entity).alias("entity"), failures.alias("failed_rules"),
                    F.to_json(F.struct(*[F.sha2(F.col(c).cast("string"), 256).alias(c) if c in (restricted or []) else F.col(c)
                                         for c in df.columns])).alias("record"),
                    F.current_timestamp().alias("quarantined_at"))
            .write.mode("append").saveAsTable(tbl(SILVER, "dq", "quarantine")))
    valid = flagged.where(~is_bad).drop(*flag_cols)
    return valid, n_bad, flagged

# MARKDOWN ********************

# ## Helpers for Silver: set types, remove duplicates, merge changes

# CELL ********************

def conform(df: DataFrame, columns: dict) -> DataFrame:
    """Give each column the type listed in config/sources.yaml.
    Also trims text, turns empty text into nulls and lower-cases emails.
    A value that can't be converted becomes null instead of failing the job;
    the data quality checks then catch it. Columns starting with "_" are left as they are."""
    meta = [c for c in df.columns if c.startswith("_")]
    typed = []
    for name, dtype in columns.items():
        if name not in df.columns:                       # the file is missing this column
            typed.append(F.lit(None).cast(dtype).alias(name))
            continue
        v = F.nullif(F.trim(F.col(name).cast("string")), F.lit(""))
        if name == "email":
            v = F.lower(v)
        typed.append(v.alias(name))
    staged = df.select(*typed, *meta)
    return staged.select(*[F.expr(f"try_cast(`{n}` as {t})").alias(n) for n, t in columns.items()], *meta)


def latest_per_key(df: DataFrame, keys: list[str], order_by: str) -> DataFrame:
    """Keep only the latest version of each row (by primary key)."""
    w = Window.partitionBy(*keys).orderBy(F.col(order_by).desc_nulls_last(), F.col("_ingested_at").desc())
    return df.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def with_row_hash(df: DataFrame, business_cols: list[str]) -> DataFrame:
    return df.withColumn("_row_hash", F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("~")) for c in business_cols]), 256))


def merge_into(target: str, src: DataFrame, keys: list[str]):
    """Insert new rows and update changed ones. Unchanged rows are left alone."""
    if not table_exists(target):
        src.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(target)
        return
    view = f"src_{uuid.uuid4().hex[:8]}"
    src.createOrReplaceTempView(view)
    on = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    spark.sql(f"""
        MERGE INTO {target} t USING {view} s ON {on}
        WHEN MATCHED AND t._row_hash <> s._row_hash THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
