"""Step 07: set up OneLake security roles on the Silver lakehouse.

OneLake security lets you decide which groups can read which tables and
columns, and the same rules apply whether someone uses Spark, SQL or Power BI.

The roles come from tenant.yaml (onelake_security). Turn OneLake security on for
lh_silver first: Lakehouse > Manage OneLake security > Enable.

This call replaces all existing roles on the lakehouse, so the script also
re-creates the default role that lets workspace members read everything.

Run: uv run python scripts/07_apply_onelake_security.py --env dev [--dry-run]
"""

import json

from lib.fabric import Client, banner, find_item, load_principals, require_workspace, std_args, tenant_config, ws_name


def build_roles(cfg: dict, principals: dict) -> list[dict]:
    tenant_id = principals["_tenant_id"]
    roles = [{   # default role: workspace members (the engineers) can read everything
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
        if r.get("allow_columns"):     # only the listed columns are visible
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
    for r in roles:   # point the default role at this lakehouse
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
