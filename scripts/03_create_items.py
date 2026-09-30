"""Step 03 - Core data items in every Data Platform workspace (dev/test/prod).

  lh_bronze  Lakehouse (schemas enabled)  raw landing files + append-only Delta copies
  lh_silver  Lakehouse (schemas enabled)  cleaned/conformed/identity-resolved + DQ results
  wh_gold    Warehouse                    star schema, T-SQL stored procs, SQL security

Why create items by script in TEST/PROD instead of letting deployment pipelines do it?
Storage items (lakehouse/warehouse) are "containers": deployment pipelines deploy their
*definition*, not their data. Pre-creating them with IDENTICAL NAMES in every stage means
notebooks and cross-database SQL (lh_silver.ticketing.orders) resolve by name - no ID
rebinding per environment. Pipelines/notebooks/semantic models are promoted by deployment.

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
