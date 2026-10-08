# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e4b5b873-13f4-4335-827c-bf8d757c7554",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "9f9f5fa0-6a89-4f39-987e-240311772371",
# META       "known_lakehouses": [
# META         {
# META           "id": "e4b5b873-13f4-4335-827c-bf8d757c7554"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_10_bronze_ingest: load the landed files into Bronze tables
# 
# Default lakehouse: lh_bronze. That's the only one it needs: it reads and writes Bronze only.
# Run by the `pl_daily_load` pipeline, or by hand.
# 
# This covers the sources that arrive as files under `Files/landing`:
# * fundraising, saved there by `nb_05_fundraising_api`
# * marketing, which `Files/landing/marketing` shows through a shortcut to ADLS Gen2
# 
# Ticketing (Copy job) and education (Dataflow Gen2) write their Bronze tables directly,
# so they're not handled here.
# 
# For each file-based table listed in `sources.json`:
# 1. Find the daily folders (`load_date=YYYY-MM-DD`) not loaded yet. Folders already loaded are skipped.
# 2. Read every column as text. Data types are set later, in Silver.
# 3. Add columns that record where each row came from and when it was loaded.
# 4. Append to `lh_bronze.<source>.<table>`. Bronze keeps everything; nothing is overwritten.
# 5. Compare row counts with the source's manifest file and save the result in `audit.reconciliation`.


# PARAMETERS CELL ********************

load_date = ""          # empty = every folder not loaded yet; "2026-09-28" = just that day
entities = ""           # empty = all tables; or a list like "ticketing.orders,fundraising.gifts"
reprocess = False       # True = load days again even if already loaded (this creates duplicates in Bronze)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Setup
# Load the shared helpers, pick the sources that arrive as files, and look up which days
# are already in Bronze.

# CELL ********************

%run nb_00_common

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Only fundraising and marketing land as files. Ticketing (Copy job) and education
# (Dataflow) write their Bronze tables themselves, so they're left out here.
sources = [s for s in load_json_config("sources")["sources"] if s["ingestion"]["lands_in"] == "files"]
landing_root = f"{lakehouse_path(BRONZE)}/Files/landing"
wanted = {e.strip() for e in entities.split(",") if e.strip()}
ensure_schemas(BRONZE, ["audit"] + [bronze_schema(s) for s in sources])

# Every loaded day is recorded in audit.ingest_log. Days found there are skipped,
# so running the notebook twice never loads the same file twice.
ingest_log = tbl(BRONZE, "audit", "ingest_log")
already = set()
if table_exists(ingest_log) and not reprocess:
    already = {(r.entity, r.load_date) for r in spark.table(ingest_log).select("entity", "load_date").distinct().collect()}


def partitions(source: str, entity: str) -> list[str]:
    """List load_date=... folders for an entity in OneLake."""
    try:
        return sorted(f.name.rstrip("/").split("=")[1] for f in nbu.fs.ls(f"{landing_root}/{source}/{entity}")
                      if f.name.startswith("load_date="))
    except Exception:  # noqa: BLE001 - no files for this table yet
        return []

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Load each new day into Bronze
# For every table, each `load_date=` folder that isn't in the ingest log yet is read,
# stamped with where and when it came from, and appended to `lh_bronze.<source>.<table>`.

# CELL ********************

batch_id = RUN_ID                       # ties every row loaded in this run together
for src in sources:
    for ent in src["entities"]:
        key = f"{src['source']}.{ent['name']}"
        if wanted and key not in wanted:
            continue
        # Days waiting to be loaded: folders on disk that aren't in the ingest log yet.
        todo = [d for d in partitions(src["source"], ent["name"])
                if (not load_date or d == load_date) and (key, d) not in already]
        for d in todo:
            started = now_utc()
            path = f"{landing_root}/{src['source']}/{ent['name']}/load_date={d}/"
            # Read everything as text. Types are set in Silver, so a bad value can't fail the load here.
            reader = spark.read.option("recursiveFileLookup", "true")
            if src["format"] == "csv":
                raw = reader.option("header", True).option("inferSchema", False).option("multiLine", True).csv(path)
            else:
                raw = reader.json(path)
            df = (raw.select(*[F.col(f"`{c}`").cast("string").alias(c) for c in raw.columns],   # keep every value as text
                             F.col("_metadata.file_path").alias("_source_file"))                 # which file the row came from
                     .withColumn("_load_date", F.lit(d).cast("date"))
                     .withColumn("_ingested_at", F.current_timestamp())
                     .withColumn("_batch_id", F.lit(batch_id)))
            n = df.count()
            if n:                                                        # empty file: log it but write nothing
                (df.write.mode("append").option("mergeSchema", "true")  # allow new columns from the source
                   .saveAsTable(tbl(BRONZE, bronze_schema(src), ent["name"])))
            # Record the day as loaded, with its row count for the check below.
            spark.createDataFrame([(key, d, n, batch_id, now_utc())],
                                  "entity string, load_date string, rows long, batch_id string, ingested_at timestamp") \
                .write.mode("append").saveAsTable(ingest_log)
            log_run("nb_10_bronze_ingest", key, "bronze", n, n, started=started, lakehouse=BRONZE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Check nothing went missing
# Each source writes a manifest per day (`landing/<source>/_manifests/`) listing how many rows to expect.
# If the counts don't match, the pipeline stops here, before Silver runs.

# CELL ********************

manifest_paths = [f"{landing_root}/{s['source']}/_manifests/*.json" for s in sources
                  if nbu.fs.exists(f"{landing_root}/{s['source']}/_manifests")]
try:
    manifests = spark.read.option("multiLine", True).json(manifest_paths)
    expected = (manifests.select("load_date", F.explode("files").alias("f"))
                .select("load_date", F.concat_ws(".", "f.source", "f.entity").alias("entity"), F.col("f.rows").alias("expected_rows")))
    actual = spark.table(ingest_log).groupBy("entity", "load_date").agg(F.max("rows").alias("loaded_rows"))
    recon = (expected.join(actual, ["entity", "load_date"], "left")
             .withColumn("status", F.when(F.col("loaded_rows").isNull(), "NOT_LOADED")
                                    .when(F.col("loaded_rows") == F.col("expected_rows"), "OK").otherwise("MISMATCH"))
             .withColumn("checked_at", F.current_timestamp()))
    recon.write.mode("overwrite").saveAsTable(tbl(BRONZE, "audit", "reconciliation"))
    bad = recon.where("status = 'MISMATCH'").count()
    display(recon.groupBy("status").count())
    if bad:
        raise Exception(f"Reconciliation failed: {bad} entity/partition(s) with row-count mismatch")
except Exception as e:  # noqa: BLE001
    if "Reconciliation failed" in str(e):
        raise
    print(f"No manifests found ({e.__class__.__name__}); skipping reconciliation.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

nbu.notebook.exit("bronze ok")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
