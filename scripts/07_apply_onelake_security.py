"""Step 07 - OneLake security roles on lh_silver (table-level + column-level).

Why OneLake security (GA 2026)? One role definition is enforced for every engine that
reads the lake (Spark, SQL analytics endpoint, Direct Lake on OneLake). Before it, you
had to re-implement access rules per engine.

Layered access model (docs/05-governance-and-security.md):
  workspace role  -> who can build/administer   (engineers only on Data Platform)
  OneLake roles   -> who can read which TABLES/COLUMNS/ROWS in the lake   <- this script
  wh_gold T-SQL   -> GRANT/RLS/DDM for SQL consumers
  semantic model  -> RLS/OLS for report consumers (primary control for business users)

Roles come from tenant.yaml > onelake_security. The Silver lakehouse must have OneLake
security enabled first (Lakehouse > Manage OneLake security > Enable - one-time, UI).
NOTE: PUT replaces ALL custom roles on the item; DefaultReader is re-created below so
workspace members keep read access.

Run: uv run python scripts/07_apply_onelake_security.py --env dev [--dry-run]
"""

import json

from lib.fabric import Client, banner, find_item, load_principals, require_workspace, std_args, tenant_config, ws_name


def build_roles(cfg: dict, principals: dict) -> list[dict]:
    tenant_id = principals["_tenant_id"]
    roles = [{   # keep the default "all workspace readers can read everything" role for engineers
        "name": "DefaultReader",
        "decisionRules": [{"effect": "Permit", "permission": [
            {"attributeName": "Path", "attributeValueIncludedIn": ["*"]},
            {"attributeName": "Action", "attributeValueIncludedIn": ["Read"]}]}],
        "members": {"fabricItemMembers": [{"itemAccess": ["ReadAll"], "sourcePath": "{workspace}/{item}"}]},
    }]
    for r in cfg["roles"]:
        paths = [f"/Tables/{t}" for t in r["tables"]]
        rule = {"effect": "Permit", "permission": [
            {"attributeName": "Path", "attributeValueIncludedIn": paths},
            {"attributeName": "Action", "attributeValueIncludedIn": ["Read"]}]}
        if r.get("allow_columns"):     # column-level security = permit-list of columns
            rule["constraints"] = {"columns": [
                {"tablePath": f"/Tables/{t}", "columnNames": cols, "columnEffect": "Permit", "columnAction": ["Read"]}
                for t, cols in r["allow_columns"].items()]}
        roles.append({
            "name": r["name"], "decisionRules": [rule],
            "members": {"microsoftEntraMembers": [
                {"tenantId": tenant_id, "objectId": principals[m]["id"], "objectType": "Group"} for m in r["members"]]},
        })
    return roles


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    a = ap.parse_args()
    cfg = tenant_config()["onelake_security"]
    c = Client(dry_run=a.dry_run)
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    lh = find_item(c, ws["id"], cfg["lakehouse"], "Lakehouse")
    roles = build_roles(cfg, load_principals())
    for r in roles:   # the default role references this item's own path
        for m in r["members"].get("fabricItemMembers", []):
            m["sourcePath"] = f"{ws['id']}/{lh['id']}"
    banner(f"OneLake security -> {ws['displayName']}/{cfg['lakehouse']}")
    for r in roles:
        print(f"  role {r['name']}")
    if a.dry_run:
        print(json.dumps({"value": roles}, indent=2)[:3000])
    c.call("PUT", f"/workspaces/{ws['id']}/items/{lh['id']}/dataAccessRoles", {"value": roles})
    print("  applied.")


if __name__ == "__main__":
    main()
