# nb_rebind_sm_finance: point a Direct Lake model at its own stage's Gold warehouse, after each deployment.
#
# Why: sm_finance is Direct Lake on OneLake. Its source is a OneLake URL holding the workspace and item IDs
# of DEV's wh_gold, a deployment pipeline copies that URL as is, and semantic models can't read a variable
# library. Without this step the TEST model quietly reads DEV data.
#
# How: create this notebook once in hh-finance-dev with the variable library vl_finance next to it, and
# let the deployment pipeline carry both to TEST and PROD. Each stage's vl_finance has its own active value
# set (DEV / TEST / PROD) holding that stage's Gold IDs, so the same notebook does the right thing in every
# stage with no edits. Run it after every deployment; in DEV it changes nothing. IDs live in the variable
# library inside Fabric, never in the repo.
#
# vl_finance variables (String): gold_workspace_id, gold_warehouse_id

# --- cell 1 (parameters) ---
MODEL = "sm_finance"
LIBRARY = "vl_finance"
EXPRESSION = "DirectLake - wh_gold"

# --- cell 2: in the notebook, this line on its own (it's a notebook magic, so commented out here) ---
# %pip install -q semantic-link-labs

# --- cell 3 ---
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

# Reframe Direct Lake and recalculate the calculated tables (Statement Line, Trend Metric) and the calculation group.
refresh_semantic_model(dataset=MODEL, workspace=bi_workspace)
print("refreshed")
