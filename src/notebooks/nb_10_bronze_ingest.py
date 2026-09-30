# %% [markdown]
# # nb_10_bronze_ingest — Files/landing → Bronze Delta tables (metadata-driven)
#
# **Workload:** Spark notebook · default lakehouse **lh_bronze** (+ lh_silver attached)
# **Called by:** `pl_daily_load` pipeline (parameter `load_date`), or run manually.
#
# What it does, per entity in `sources.json`:
# 1. Finds landing partitions `load_date=YYYY-MM-DD` not yet ingested (**idempotent** — re-runs skip them).
# 2. Reads them **as strings** (Bronze = raw & immutable; typing happens in Silver).
# 3. Adds lineage columns `_load_date, _source_file, _ingested_at, _batch_id`.
# 4. **Appends** to `lh_bronze.<source>.<entity>` (history is never overwritten).
# 5. Reconciles row counts against the source manifest → `audit.reconciliation`.

# %% tags=["parameters"]
load_date = ""          # "" = all pending partitions; "2026-09-28" = only that one
entities = ""           # "" = all; "ticketing.orders,fundraising.gifts" = subset
reprocess = False       # True = re-ingest partitions already logged (use with care: duplicates in Bronze)

# %%
# MAGIC %run nb_00_common

# %%
sources = load_json_config("sources")["sources"]
landing_root = f"{lakehouse_path(BRONZE)}/Files/landing"
wanted = {e.strip() for e in entities.split(",") if e.strip()}
ensure_schemas(BRONZE, ["audit"] + [s["source"] for s in sources])
ingest_log = tbl(BRONZE, "audit", "ingest_log")
already = set()
if table_exists(ingest_log) and not reprocess:
    already = {(r.entity, r.load_date) for r in spark.table(ingest_log).select("entity", "load_date").distinct().collect()}


def partitions(source: str, entity: str) -> list[str]:
    """List load_date=... folders for an entity in OneLake."""
    try:
        return sorted(f.name.rstrip("/").split("=")[1] for f in nbu.fs.ls(f"{landing_root}/{source}/{entity}")
                      if f.name.startswith("load_date="))
    except Exception:  # noqa: BLE001 - folder not landed yet
        return []


# %%
batch_id = RUN_ID
for src in sources:
    for ent in src["entities"]:
        key = f"{src['source']}.{ent['name']}"
        if wanted and key not in wanted:
            continue
        todo = [d for d in partitions(src["source"], ent["name"])
                if (not load_date or d == load_date) and (key, d) not in already]
        for d in todo:
            started = now_utc()
            path = f"{landing_root}/{src['source']}/{ent['name']}/load_date={d}/"
            reader = spark.read.option("recursiveFileLookup", "true")
            if src["format"] == "csv":
                raw = reader.option("header", True).option("inferSchema", False).option("multiLine", True).csv(path)
            else:
                raw = reader.json(path)
            df = (raw.select(*[F.col(f"`{c}`").cast("string").alias(c) for c in raw.columns],   # Bronze = strings
                             F.col("_metadata.file_path").alias("_source_file"))                 # lineage to the file
                     .withColumn("_load_date", F.lit(d).cast("date"))
                     .withColumn("_ingested_at", F.current_timestamp())
                     .withColumn("_batch_id", F.lit(batch_id)))
            n = df.count()
            if n:                                                        # empty extract -> log it, write nothing
                (df.write.mode("append").option("mergeSchema", "true")  # tolerate source schema drift
                   .saveAsTable(tbl(BRONZE, src["source"], ent["name"])))
            spark.createDataFrame([(key, d, n, batch_id, now_utc())],
                                  "entity string, load_date string, rows long, batch_id string, ingested_at timestamp") \
                .write.mode("append").saveAsTable(ingest_log)
            log_run("nb_10_bronze_ingest", key, "bronze", n, n, started=started)

# %% [markdown]
# ## Source-to-Bronze reconciliation
# The generator (and, in production, the extract job) writes a manifest with expected row counts.
# Any mismatch is a **load completeness** failure — the pipeline fails before Silver runs.

# %%
manifest_path = f"{landing_root}/_manifests/"
try:
    manifests = spark.read.option("multiLine", True).json(manifest_path)
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

# %%
nbu.notebook.exit("bronze ok")
