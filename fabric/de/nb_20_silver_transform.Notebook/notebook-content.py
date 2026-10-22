# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "814881f4-8c94-4ab2-ba49-80a69a3089e9",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "9f9f5fa0-6a89-4f39-987e-240311772371",
# META       "known_lakehouses": [
# META         {
# META           "id": "814881f4-8c94-4ab2-ba49-80a69a3089e9"
# META         },
# META         {
# META           "id": "e4b5b873-13f4-4335-827c-bf8d757c7554"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_20_silver_transform: clean Bronze data into Silver
# 
# Default lakehouse: lh_silver (attach lh_bronze too).
# Run by the `pl_daily_load` pipeline after `nb_10_bronze_ingest`.
# 
# For each table, in the order listed in `sources.json` (lookup tables first):
# 1. Read only the Bronze rows that are new since the last run. How "new" is found depends on the source:
#    * files loaded by nb_10: by `_load_date`
#    * tables appended by a Copy job (Tessitura, MIP): by `updated_at`
#    * education, replaced by the Dataflow on every run: the whole (small) table is read
# 2. Set the data types, trim text, turn empty text into nulls and lower-case emails.
# 3. Keep only the latest version of each row, which also removes rows sent twice.
# 4. Run the data quality checks. Bad rows go to `dq.quarantine`.
# 5. Merge into `lh_silver.<system>.<table>`, for example `lh_silver.tessitura.order_line`. Only new or changed rows are written.
# 
# Then duplicate Tessitura constituent records are merged into one list of people, `core.patron`.
# The matches are saved in `core.patron_xref` so each person keeps the same ID.


# PARAMETERS CELL ********************

entities = ""            # empty = all tables
full_refresh = False     # True = rebuild from all of Bronze, not just the new rows

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb_00_common

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

sources = load_json_config("sources")["sources"]
dq_rules = load_json_config("dq_rules")
wanted = {e.strip() for e in entities.split(",") if e.strip()}
ensure_schemas(SILVER, ["audit", "dq", "core"] + sorted({system(s) for s in sources}))
wm_table = tbl(SILVER, "audit", "watermarks")


def get_watermark(entity: str):
    if full_refresh or not table_exists(wm_table):
        return None
    return spark.table(wm_table).where(F.col("entity") == entity).agg(F.max("last_value")).collect()[0][0]


def set_watermark(entity: str, value):
    spark.createDataFrame([(entity, value, now_utc())], "entity string, last_value timestamp, updated_at timestamp") \
        .write.mode("append").saveAsTable(wm_table)


def add_missing_meta(df, change_col):
    """Tables written by a Copy job or Dataflow don't have nb_10's tracking columns, so fill them in."""
    if "_ingested_at" not in df.columns:
        df = df.withColumn("_ingested_at", F.col(change_col).cast("timestamp") if change_col else F.current_timestamp())
    if "_load_date" not in df.columns:
        df = df.withColumn("_load_date", F.to_date("_ingested_at"))
    return df

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

entity_config = {f"{system(src)}.{ent['name']}": (src, ent) for src in sources for ent in src["entities"]}
done = set()


def process_entity(key: str):
    """Bronze to Silver for one table: steps 1-5 above. Safe to re-run on its own while debugging."""
    done.add(key)
    if wanted and key not in wanted:
        return
    if key not in entity_config:
        print(f"skip {key}: not in sources.yaml")
        return
    src, ent = entity_config[key]
    bronze = tbl(BRONZE, bronze_schema(src), ent["name"])
    started = now_utc()
    if not table_exists(bronze):
        print(f"skip {key}: no Bronze table yet ({bronze})")
        log_run("nb_20_silver_transform", key, "silver", 0, 0, status="Skipped", message=f"no Bronze table yet ({bronze})",
                started=started)
        return
    change_col = src["ingestion"].get("change_column", "_load_date")    # None = read the whole table
    df = add_missing_meta(spark.table(bronze), change_col)
    new_wm = None
    if change_col:                                                       # step 1
        wm = get_watermark(key)
        if wm is not None:
            df = df.where(F.col(change_col).cast("timestamp") > F.lit(wm))
        new_wm = df.agg(F.max(F.col(change_col).cast("timestamp"))).collect()[0][0]
        if new_wm is None:
            print(f"skip {key}: nothing new since {wm}")
            # Logged as a success: the table was checked and is current. Without this, a source with
            # no changes looks stale in rpt.vw_source_freshness, which means "last confirmed current".
            log_run("nb_20_silver_transform", key, "silver", 0, 0, message=f"checked: nothing new since {wm}",
                    started=started)
            return
    rows_in = df.count()

    cols = ent["columns"]
    df = conform(df, cols)                                                       # step 2
    df = latest_per_key(df, ent["primary_key"], ent["order_by"])                 # step 3
    df, n_bad, dq_cache = apply_dq(df, key, dq_rules, ent.get("restricted", []))  # step 4
    df = with_row_hash(df, list(cols)).select(
        *cols, "_row_hash", F.col("_load_date"), F.current_timestamp().alias("_silver_updated_at")).cache()
    rows_out = df.count()                     # computed once, then reused by the merge
    merge_into(tbl(SILVER, system(src), ent["name"]), df, ent["primary_key"])  # step 5
    if new_wm is not None:
        set_watermark(key, new_wm)
    log_run("nb_20_silver_transform", key, "silver", rows_in, rows_out, n_bad, started=started)
    # Free the memory before the next table, so a long run doesn't pile up cached data.
    df.unpersist()
    if dq_cache is not None:
        dq_cache.unpersist()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Tessitura: database tables
# Source: the on-premises Tessitura SQL Server, copied by `cj_tessitura`. Lookup tables run first,
# because `order_line` is checked against `performance` and `order`.

# CELL ********************

process_entity("tessitura.season")

process_entity("tessitura.venue")

process_entity("tessitura.performance")

process_entity("tessitura.constituent")

process_entity("tessitura.order")

# Lines pointing at a show that doesn't exist, or with a negative price, go to quarantine.
process_entity("tessitura.order_line")

process_entity("tessitura.subscription")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Tessitura: REST API
# Source: the Tessitura REST API, landed by `nb_05_api_ingest`. Overlapping API pages send some
# records twice; step 3 keeps one of each.

# CELL ********************

process_entity("tessitura.campaign")

process_entity("tessitura.fund")

# Contributions dated in the future, or for a constituent that doesn't exist, go to quarantine.
process_entity("tessitura.contribution")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## MIP: the general ledger
# Source: the on-premises MIP SQL Server, copied by `cj_mip`. Accounts, departments and funds
# run first, because every journal line is checked against them. A line that is both a debit
# and a credit, or points at an account that doesn't exist, goes to quarantine.

# CELL ********************

process_entity("mip.gl_account")

process_entity("mip.department")

process_entity("mip.fund")

process_entity("mip.gl_transaction")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Diese: hall and room bookings
# Source: the Diese booking API, landed by `nb_05_api_ingest`. Rooms and events run before
# bookings, which are checked against both. Bookings that end before they start go to quarantine.
# Concert events point at their Tessitura performance; a missing link is allowed here and
# counted in Gold, where venue operations confirm the match.

# CELL ********************

process_entity("diese.room")

process_entity("diese.event")

process_entity("diese.booking")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Education
# Source: SharePoint workbooks, loaded by the Dataflow into `lh_bronze.dbo`. Small tables,
# so they're read in full every run.

# CELL ********************

process_entity("education.programs")

process_entity("education.schools")

# Sessions with no participants go to quarantine.
process_entity("education.enrollments")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Marketing
# Source: ADLS exports, read through the `marketing` shortcut and loaded by `nb_10`.

# CELL ********************

process_entity("marketing.email_campaigns")

# Clicks exported twice are removed; clicks for an unknown campaign go to quarantine.
process_entity("marketing.email_clicks")

# Ad platforms restate the last two days; the latest version of each day wins.
process_entity("marketing.ad_spend_daily")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Tables added to sources.yaml but not listed above
# A new table still gets loaded, with a reminder to add it to its source's cell above.

# CELL ********************

for key in entity_config:
    if key not in done:
        print(f"note: {key} isn't listed in its source's cell yet; loading it here")
        process_entity(key)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Identity: merge duplicate Tessitura constituents → core.patron
# Tessitura often holds the same person twice, for example once from a ticket purchase and
# again from a gift entered by the development team. Two records are the same person if they
# have the same email or, failing that, the same first name, last name and zip code.
# People already matched keep their ID; only new records are matched.
# When records disagree, the most complete record (one with an address) wins, then the latest.
# More systems (MIP, Diese) can add their people here later with their own `source_system`.

# CELL ********************

started = now_utc()
const_t = tbl(SILVER, "tessitura", "constituent")
xref_t = tbl(SILVER, "core", "patron_xref")

name_zip = F.lower(F.concat_ws("|", F.col("first_name"), F.col("last_name"), F.col("postal_code")))
candidates = (
    spark.table(const_t).select(F.lit("tessitura").alias("source_system"), F.col("constituent_id").alias("source_id"),
                                "first_name", "last_name", "email", "phone", "address_line1", "city", "state",
                                "postal_code", "country", F.col("constituent_type").alias("patron_type"), "email_opt_in",
                                F.to_date("created_at").alias("first_seen_date"), "updated_at")
    .withColumn("email_key", F.col("email"))                 # already trimmed and lower-cased in step 2
    .withColumn("name_zip_key", name_zip)
)

if table_exists(xref_t):
    xref = spark.table(xref_t)
else:
    xref = spark.createDataFrame([], "source_system string, source_id string, patron_id string, email_key string, "
                                     "name_zip_key string, match_rule string, matched_at timestamp")

new = candidates.join(xref.select("source_system", "source_id"), ["source_system", "source_id"], "left_anti")

# First, match new records to people we already know, by email and then by name and zip.
by_email = xref.where("email_key IS NOT NULL").groupBy("email_key").agg(F.min("patron_id").alias("pid_email"))
by_nz = xref.groupBy("name_zip_key").agg(F.min("patron_id").alias("pid_nz"))
matched = (new.join(by_email, "email_key", "left").join(by_nz, "name_zip_key", "left")
              .withColumn("patron_id", F.coalesce("pid_email", "pid_nz"))
              .withColumn("match_rule", F.when(F.col("pid_email").isNotNull(), "email")
                                         .when(F.col("pid_nz").isNotNull(), "name_zip")))

# Then group the remaining new records into new people and give each one an ID.
cluster_key = F.coalesce(F.col("email_key"), F.col("name_zip_key"))
fresh = (matched.where("patron_id IS NULL")
         .withColumn("patron_id", F.concat(F.lit("PAT-"), F.substring(F.sha2(cluster_key, 256), 1, 12)))
         .withColumn("match_rule", F.when(F.col("email_key").isNotNull(), "new:email").otherwise("new:name_zip")))
new_xref = (matched.where("patron_id IS NOT NULL").unionByName(fresh)
            .select("source_system", "source_id", "patron_id", "email_key", "name_zip_key", "match_rule",
                    F.current_timestamp().alias("matched_at")))
new_xref.write.mode("append").saveAsTable(xref_t)

# Build one record per person. The table is small, so it is rebuilt every run.
xref = spark.table(xref_t)
w = Window.partitionBy("patron_id").orderBy(F.when(F.col("address_line1").isNotNull(), 0).otherwise(1),
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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Make the new data visible to SQL
# The Gold warehouse reads Silver through its SQL endpoint, which can take a few
# minutes to see new data. This forces it to catch up now, so the Gold load that
# runs next doesn't miss today's rows.

# CELL ********************

try:
    import sempy.fabric as fabric
    lh = nbu.lakehouse.get(SILVER)
    sql_ep = lh["properties"]["sqlEndpointProperties"]["id"]
    resp = fabric.FabricRestClient().post(f"/v1/workspaces/{WORKSPACE_ID}/sqlEndpoints/{sql_ep}/refreshMetadata", json={})
    print("SQL endpoint metadata refresh:", resp.status_code)
except Exception as e:  # noqa: BLE001
    print(f"Metadata refresh skipped ({e}); the endpoint will sync on its own within minutes.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

nbu.notebook.exit("silver ok")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC SELECT 'programs', COUNT(*) FROM lh_silver.education.programs
# MAGIC UNION ALL 
# MAGIC SELECT 'schools', COUNT(*) FROM lh_silver.education.schools
# MAGIC UNION ALL 
# MAGIC SELECT 'enrollments', COUNT(*) FROM lh_silver.education.enrollments
# MAGIC UNION ALL 
# MAGIC SELECT 'quarantined', COUNT(*) FROM lh_silver.dq.quarantine 
# MAGIC WHERE entity LIKE 'education.%';

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }
