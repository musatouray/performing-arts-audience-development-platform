"""Step 09: share the Gold warehouse with BI developers, then check it.

BI developers have no role in the Data Platform workspaces, so they can't see
Bronze or Silver. Their reports still need Gold, so the wh_gold warehouse is
shared with them directly.

Fabric has no API for sharing a warehouse; it has to be done in the portal.
This script prints the steps for each environment, then reads the permissions
back and reports anything missing or unexpected.

Permissions (tenant.yaml, item_shares):
  Read     = connect to the warehouse (always included)
  ReadData = query all tables with SQL
  ReadAll  = read the underlying files in OneLake (needed for Direct Lake models)

Report viewers don't need a share; the semantic models connect with a fixed identity.

Run: uv run python scripts/09_verify_item_shares.py [--env dev]
"""

import argparse

from lib.fabric import ApiError, Client, banner, find_item, load_principals, require_workspace, tenant_config, ws_name

UI_LABELS = {
    "ReadData": 'tick "Read all data using SQL (ReadData)"',
    "ReadAll": 'tick "Read all OneLake data (ReadAll)"',
}


def granted_permissions(entry: dict) -> set[str]:
    d = entry.get("itemAccessDetails", {})
    perms = [*d.get("permissions", []), *d.get("additionalPermissions", [])]
    return {p.lower() for p in perms}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", choices=["dev", "test", "prod"], help="only this environment")
    a = ap.parse_args()
    cfg = tenant_config()
    principals = load_principals()
    c = Client()
    missing_total = 0

    for share in cfg.get("item_shares", []):
        envs = [a.env] if a.env else share.get("environments", cfg["environments"])
        for env in envs:
            ws = require_workspace(c, ws_name(share["workspace_family"], env))
            item = find_item(c, ws["id"], share["item"], share["item_type"])
            banner(f"{ws['displayName']} / {share['item']}")
            if not item:
                print(f"  ! {share['item']} not found - run scripts/03_create_items.py first")
                continue

            # Steps to follow in the portal
            print("  UI: open the item > ... > Share > 'Grant people access'")
            for g in share["grant_to"]:
                print(f"      add group  {principals[g]['name']}")
            for p in share["permissions"]:
                if p in UI_LABELS:
                    print(f"      {UI_LABELS[p]}")
            print("      untick 'Notify recipients by email' > Grant  (propagation can take up to 2 hours)")

            # Check what was actually granted
            try:
                details = c.get(f"/admin/workspaces/{ws['id']}/items/{item['id']}/users").get("accessDetails", [])
            except ApiError as e:
                print(f"  ? could not verify ({e.status} {e.code}) - needs Fabric admin + Tenant.Read.All")
                continue
            by_id = {d["principal"]["id"]: d for d in details}
            wanted = {p.lower() for p in share["permissions"]}
            for g in share["grant_to"]:
                entry = by_id.get(principals[g]["id"])
                have = granted_permissions(entry) if entry else set()
                gaps = wanted - have
                if not entry:
                    print(f"  MISSING  {principals[g]['name']}: not shared yet")
                    missing_total += 1
                elif gaps:
                    print(f"  PARTIAL  {principals[g]['name']}: missing {sorted(gaps)}")
                    missing_total += 1
                else:
                    print(f"  OK       {principals[g]['name']}: {sorted(have)}")

            # Flag access that isn't in tenant.yaml, such as a share with one person
            declared = {principals[g]["id"] for g in share["grant_to"]}
            for d in details:
                p = d["principal"]
                if p["id"] not in declared and p.get("type") in ("User", "Group") and d.get("itemAccessDetails", {}).get("permissions"):
                    via_ws = d.get("itemAccessDetails", {}).get("type") == "Workspace"
                    if not via_ws:
                        print(f"  REVIEW   {p.get('displayName')} ({p.get('type')}) has access not declared in tenant.yaml")

    print(f"\n{'All declared item shares are in place.' if not missing_total else f'{missing_total} share(s) to fix.'}")
    return 1 if missing_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
