# %% [markdown]
# # nb_20_silver_transform — Bronze → Silver (conform, dedupe, DQ, MERGE) + identity resolution
#
# **Workload:** Spark notebook · default lakehouse **lh_silver** (+ lh_bronze attached)
# **Called by:** `pl_daily_load` after `nb_10_bronze_ingest`.
#
# Per entity (order in `sources.json` = dependency order, reference data first):
# 1. **Incremental read** — only Bronze rows with `_load_date` > the entity's Silver watermark.
# 2. **Conform** to the schema contract (`try_cast`, trim, `''→NULL`, lower-case email).
# 3. **Dedupe** — latest version per business key (CDC, last-writer-wins) → removes re-sent rows.
# 4. **DQ** — error rows quarantined, warnings logged (`dq.dq_results`, `dq.quarantine`).
# 5. **MERGE** into `lh_silver.<source>.<entity>` — only rows whose content hash changed are rewritten.
#
# Then **identity resolution** builds one golden `core.patron` across ticketing customers and
# fundraising donors, persisted in `core.patron_xref` (stable patron_id across runs).

# %% tags=["parameters"]
entities = ""            # "" = all
full_refresh = False     # True = ignore watermarks and rebuild from all Bronze history

# %%
# MAGIC %run nb_00_common

# %%
sources = load_json_config("sources")["sources"]
dq_rules = load_json_config("dq_rules")
wanted = {e.strip() for e in entities.split(",") if e.strip()}
ensure_schemas(SILVER, ["audit", "dq", "core"] + [s["source"] for s in sources])
wm_table = tbl(SILVER, "audit", "watermarks")


def get_watermark(entity: str):
    if full_refresh or not table_exists(wm_table):
        return None
    r = spark.table(wm_table).where(F.col("entity") == entity).agg(F.max("last_load_date")).collect()[0][0]
    return r


def set_watermark(entity: str, value):
    spark.createDataFrame([(entity, value, now_utc())], "entity string, last_load_date date, updated_at timestamp") \
        .write.mode("append").saveAsTable(wm_table)


# %%
for src in sources:
    for ent in src["entities"]:
        key = f"{src['source']}.{ent['name']}"
        if wanted and key not in wanted:
            continue
        bronze = tbl(BRONZE, src["source"], ent["name"])
        if not table_exists(bronze):
            print(f"skip {key}: no bronze table yet")
            continue
        started = now_utc()
        wm = get_watermark(key)
        df = spark.table(bronze)
        if wm is not None:
            df = df.where(F.col("_load_date") > F.lit(wm))
        max_ld = df.agg(F.max("_load_date")).collect()[0][0]
        if max_ld is None:
            print(f"skip {key}: nothing new since {wm}")
            continue
        rows_in = df.count()

        cols = ent["columns"]
        df = conform(df, cols)                                                       # 2. type contract
        df = latest_per_key(df, ent["primary_key"], ent["order_by"])                 # 3. CDC dedupe
        df, n_bad = apply_dq(df, key, dq_rules)                                      # 4. DQ gate
        df = with_row_hash(df, list(cols)).select(
            *cols, "_row_hash", F.col("_load_date"), F.current_timestamp().alias("_silver_updated_at"))
        target = tbl(SILVER, src["source"], ent["name"])
        merge_into(target, df, ent["primary_key"])                                   # 5. upsert
        set_watermark(key, max_ld)
        log_run("nb_20_silver_transform", key, "silver", rows_in, df.count(), n_bad, started=started)

# %% [markdown]
# ## Identity resolution → `core.patron_xref` + golden `core.patron`
# Match rules (deterministic, explainable to business users):
# 1. same **normalised email**, else 2. same **first + last name + postal code**.
# Existing mappings are **kept** (stable IDs); only new source records are matched.
# Survivorship: most recently updated ticketing record wins, then fundraising.

# %%
started = now_utc()
cust_t, donor_t = tbl(SILVER, "ticketing", "customers"), tbl(SILVER, "fundraising", "donors")
xref_t = tbl(SILVER, "core", "patron_xref")

name_zip = F.lower(F.concat_ws("|", F.col("first_name"), F.col("last_name"), F.col("postal_code")))
candidates = (
    spark.table(cust_t).select(F.lit("ticketing").alias("source_system"), F.col("customer_id").alias("source_id"),
                               "first_name", "last_name", "email", "phone", "address_line1", "city", "state", "postal_code",
                               "country", F.col("customer_type").alias("patron_type"), "email_opt_in",
                               F.to_date("created_at").alias("first_seen_date"), "updated_at")
    .unionByName(
        spark.table(donor_t).select(F.lit("fundraising").alias("source_system"), F.col("donor_id").alias("source_id"),
                                    "first_name", "last_name", "email", F.lit(None).cast("string").alias("phone"),
                                    F.lit(None).cast("string").alias("address_line1"), "city", "state", "postal_code",
                                    F.lit("USA").alias("country"), F.lit("Individual").alias("patron_type"),
                                    F.lit(None).cast("boolean").alias("email_opt_in"),
                                    F.col("donor_since").alias("first_seen_date"), "updated_at"))
    .withColumn("email_key", F.col("email"))                 # already trimmed + lower-cased in conform()
    .withColumn("name_zip_key", name_zip)
)

if table_exists(xref_t):
    xref = spark.table(xref_t)
else:
    xref = spark.createDataFrame([], "source_system string, source_id string, patron_id string, email_key string, "
                                     "name_zip_key string, match_rule string, matched_at timestamp")

new = candidates.join(xref.select("source_system", "source_id"), ["source_system", "source_id"], "left_anti")

# Pass 1: match new records to EXISTING patrons by email, then by name+zip.
by_email = xref.where("email_key IS NOT NULL").groupBy("email_key").agg(F.min("patron_id").alias("pid_email"))
by_nz = xref.groupBy("name_zip_key").agg(F.min("patron_id").alias("pid_nz"))
matched = (new.join(by_email, "email_key", "left").join(by_nz, "name_zip_key", "left")
              .withColumn("patron_id", F.coalesce("pid_email", "pid_nz"))
              .withColumn("match_rule", F.when(F.col("pid_email").isNotNull(), "email")
                                         .when(F.col("pid_nz").isNotNull(), "name_zip")))

# Pass 2: brand-new people -> cluster among themselves on email (else name+zip) and mint a stable ID.
cluster_key = F.coalesce(F.col("email_key"), F.col("name_zip_key"))
fresh = (matched.where("patron_id IS NULL")
         .withColumn("patron_id", F.concat(F.lit("PAT-"), F.substring(F.sha2(cluster_key, 256), 1, 12)))
         .withColumn("match_rule", F.when(F.col("email_key").isNotNull(), "new:email").otherwise("new:name_zip")))
new_xref = (matched.where("patron_id IS NOT NULL").unionByName(fresh)
            .select("source_system", "source_id", "patron_id", "email_key", "name_zip_key", "match_rule",
                    F.current_timestamp().alias("matched_at")))
new_xref.write.mode("append").saveAsTable(xref_t)

# Golden record (small table -> full recompute each run is simpler and safe).
xref = spark.table(xref_t)
w = Window.partitionBy("patron_id").orderBy(F.when(F.col("source_system") == "ticketing", 0).otherwise(1),
                                            F.col("updated_at").desc_nulls_last())
golden = (candidates.join(xref.select("source_system", "source_id", "patron_id"), ["source_system", "source_id"])
          .withColumn("_rn", F.row_number().over(w)))
agg = golden.groupBy("patron_id").agg(F.min("first_seen_date").alias("first_seen_date"),
                                      F.concat_ws(",", F.sort_array(F.collect_set("source_system"))).alias("source_systems"))
patron = (golden.where("_rn = 1").drop("_rn", "first_seen_date", "source_system", "source_id", "email_key", "name_zip_key")
          .join(agg, "patron_id")
          .withColumn("_silver_updated_at", F.current_timestamp()))
patron.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(tbl(SILVER, "core", "patron"))

n_src, n_pat = candidates.count(), patron.count()
log_run("nb_20_silver_transform", "core.patron", "identity", n_src, n_pat, started=started,
        message=f"{n_src:,} source records -> {n_pat:,} patrons ({1 - n_pat / max(n_src, 1):.1%} de-duplicated)")

# %% [markdown]
# ## Refresh the SQL analytics endpoint metadata
# Spark writes Delta files; the SQL endpoint syncs metadata asynchronously. `wh_gold` stored procs
# read Silver through that endpoint, so force a sync **before** the pipeline runs them
# (classic gotcha: "the proc didn't see today's rows").

# %%
try:
    import sempy.fabric as fabric
    lh = nbu.lakehouse.get(SILVER)
    sql_ep = lh["properties"]["sqlEndpointProperties"]["id"]
    resp = fabric.FabricRestClient().post(f"/v1/workspaces/{WORKSPACE_ID}/sqlEndpoints/{sql_ep}/refreshMetadata", json={})
    print("SQL endpoint metadata refresh:", resp.status_code)
except Exception as e:  # noqa: BLE001
    print(f"Metadata refresh skipped ({e}); the endpoint will sync on its own within minutes.")

# %%
nbu.notebook.exit("silver ok")
