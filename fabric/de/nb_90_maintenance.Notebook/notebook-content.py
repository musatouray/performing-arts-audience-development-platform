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

# # nb_90_maintenance: weekly table clean-up for Bronze and Silver
# 
# Run every Sunday at 03:00 by `pl_weekly_maintenance`.
# * `OPTIMIZE ... VORDER` combines the many small files left by daily loads into
#   fewer, larger ones, which makes reports and queries faster.
# * `VACUUM ... RETAIN 168 HOURS` deletes old files no longer in use, but keeps
#   seven days of history so a table can be restored if needed.
# It runs overnight so it doesn't slow down reports during the day.

# PARAMETERS CELL ********************

retain_hours = 168
lakehouses = "lh_bronze,lh_silver"

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

# The list of tables comes from the same config file the loads use.
sources = load_json_config("sources")["sources"]
inventory = {
    "lh_bronze": [(bronze_schema(s), e["name"]) for s in sources for e in s["entities"]]
                 + [("audit", "ingest_log"), ("audit", "reconciliation"), ("audit", "run_log")],
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
            log_run("nb_90_maintenance", f"{lh}.{schema}.{table}", "maintenance", 0, 0, started=started, lakehouse=lh)
        except Exception as e:  # noqa: BLE001 - log the failure and move on to the next table
            log_run("nb_90_maintenance", f"{lh}.{schema}.{table}", "maintenance", 0, 0,
                    status="Failed", message=str(e), started=started, lakehouse=lh)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
