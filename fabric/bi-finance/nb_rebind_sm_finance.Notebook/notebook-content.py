# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ### Rebind sm_finance
# 
# point a Direct Lake model at its own stage's Gold warehouse, after each deployment.
# 
# Why: sm_finance is Direct Lake on OneLake. Its source is a OneLake URL holding the workspace and item IDs of DEV's wh_gold, a deployment pipeline copies that URL as is, and semantic models can't read a variable library. Without this step the TEST model quietly reads DEV data.
# 
# How: set (DEV / TEST / PROD) holding that stage's Gold IDs, so the same notebook does the right thing in every stage with no edits. Run it after every deployment.


# CELL ********************

# install semantic link labs library
%pip install -q semantic-link-labs

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- parameters
MODEL = "sm_finance"
LIBRARY = "vl_finance"
EXPRESSION = "DirectLake - wh_gold"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# rebind the workspace

import re

import notebookutils
from sempy_labs import refresh_semantic_model
from sempy_labs.tom import connect_semantic_model

bi_workspace = notebookutils.runtime.context["currentWorkspaceName"]
gold_ws = notebookutils.variableLibrary.get(f"$(/**/{LIBRARY}/gold_workspace_id)")
gold_item = notebookutils.variableLibrary.get(f"$(/**/{LIBRARY}/gold_warehouse_id)")
target = f"https://onelake.dfs.fabric.microsoft.com/{gold_ws}/{gold_item}"
ONELAKE_URL = re.compile(r"https://onelake\.dfs\.fabric\.microsoft\.com/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}")

with connect_semantic_model(dataset=MODEL, workspace=bi_workspace, readonly=False) as tom:
    expr = tom.model.Expressions[EXPRESSION]
    current = ONELAKE_URL.search(expr.Expression)
    if current is None:
        raise ValueError(f"No OneLake URL in expression '{EXPRESSION}':\n{expr.Expression}")
    print(f"{bi_workspace}/{MODEL}")
    print("  was:", current.group(0))
    print("  now:", target)
    if current.group(0) != target:
        expr.Expression = ONELAKE_URL.sub(target, expr.Expression)

# Reframe Direct Lake and recalculate the calculated tables
refresh_semantic_model(dataset=MODEL, workspace=bi_workspace)
print("refreshed")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
