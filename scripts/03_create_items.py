"""Step 03: create the lakehouses and warehouse in each Data Platform workspace.

  lh_bronze  lakehouse   raw source data, stored as received
  lh_silver  lakehouse   cleaned and checked data
  wh_gold    warehouse   star schema used for reporting

These are created in dev, test and prod with the same names. Deployment
pipelines copy definitions, not data, so each environment needs its own copy of
these items. Matching names also mean the notebooks and SQL find them without
any changes per environment.

Run: uv run python scripts/03_create_items.py [--dry-run] [--env dev]
"""

from lib.fabric import Client, banner, find_item, require_workspace, std_args, tenant_config, ws_name


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", choices=["dev", "test", "prod"])
    a = ap.parse_args()
    cfg = tenant_config()
    c = Client(dry_run=a.dry_run)

    for fam in cfg["workspace_families"]:
        items = fam.get("items") or {}
        if not items:
            continue
        for env in cfg["environments"]:
            if a.env and env != a.env:
                continue
            ws = require_workspace(c, ws_name(fam["key"], env))
            banner(ws["displayName"])
            for lh in items.get("lakehouses", []):
                if find_item(c, ws["id"], lh["name"], "Lakehouse"):
                    print(f"  = Lakehouse {lh['name']} exists")
                    continue
                body = {"displayName": lh["name"], "description": lh["description"][:256]}
                if lh.get("schemas"):
                    body["creationPayload"] = {"enableSchemas": True}
                res = c.post(f"/workspaces/{ws['id']}/lakehouses", body)
                print(f"  + Lakehouse {lh['name']} {res.get('id', '')}")
            for wh in items.get("warehouses", []):
                if find_item(c, ws["id"], wh["name"], "Warehouse"):
                    print(f"  = Warehouse {wh['name']} exists")
                    continue
                res = c.post(f"/workspaces/{ws['id']}/warehouses", {"displayName": wh["name"], "description": wh["description"][:256]})
                print(f"  + Warehouse {wh['name']} {res.get('id', '')}")


if __name__ == "__main__":
    main()
