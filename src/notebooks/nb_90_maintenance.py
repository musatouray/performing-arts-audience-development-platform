# %% [markdown]
# # nb_90_maintenance — weekly Delta table maintenance (Bronze + Silver)
#
# **Workload:** Spark notebook · scheduled weekly by `pl_weekly_maintenance` (Sunday 03:00).
# * `OPTIMIZE ... VORDER` — compacts small files from daily appends/MERGEs and applies V-Order
#   (the read-optimised layout Direct Lake and the SQL endpoint benefit from).
# * `VACUUM ... RETAIN 168 HOURS` — removes unreferenced files older than 7 days
#   (keeps 7 days of time travel for recovery; never go below the default without a reason).
# Cost note: maintenance runs off-hours so it does not compete with daytime report queries for capacity.

# %% tags=["parameters"]
retain_hours = 168
lakehouses = "lh_bronze,lh_silver"

# %%
# MAGIC %run nb_00_common

# %%
# Table inventory comes from the same ingestion contract (no catalog crawling needed).
sources = load_json_config("sources")["sources"]
inventory = {
    "lh_bronze": [(s["source"], e["name"]) for s in sources for e in s["entities"]]
                 + [("audit", "ingest_log"), ("audit", "reconciliation")],
    "lh_silver": [(s["source"], e["name"]) for s in sources for e in s["entities"]]
                 + [("core", "patron"), ("core", "patron_xref"), ("dq", "dq_results"), ("dq", "quarantine"),
                    ("audit", "run_log"), ("audit", "watermarks")],
}
for lh in [x.strip() for x in lakehouses.split(",")]:
    for schema, table in inventory.get(lh, []):
        name = tbl(lh, schema, table)
        if not table_exists(name):
            continue
        started = now_utc()
        try:
            spark.sql(f"OPTIMIZE {name} VORDER")
            spark.sql(f"VACUUM {name} RETAIN {int(retain_hours)} HOURS")
            log_run("nb_90_maintenance", f"{lh}.{schema}.{table}", "maintenance", 0, 0, started=started)
        except Exception as e:  # noqa: BLE001 - keep going, log the failure
            log_run("nb_90_maintenance", f"{lh}.{schema}.{table}", "maintenance", 0, 0,
                    status="Failed", message=str(e), started=started)
