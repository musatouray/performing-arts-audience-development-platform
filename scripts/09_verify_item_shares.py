"""Step 09 - Item-level shares: give BI developers Gold, and ONLY Gold.

Problem it solves
  BI developers have no role in the Data Platform workspaces (that would expose Bronze/Silver).
  Their Direct Lake models still need to read wh_gold. The least-privilege answer is an
  ITEM share on wh_gold only - never a workspace role.

Why this script only GUIDES + VERIFIES (does not grant)
  Microsoft Learn: "Currently, sharing a Warehouse is only available through the user
  experience." There is no public API to grant warehouse item permissions. So the grant is
  a UI step; this script prints exactly what to share per environment, then reads the
  actual permissions back through the Admin API (Items - List Item Access Details) and
  flags anything missing or extra. That's the audit trail.

Permissions (tenant.yaml > item_shares):
  Read     - connect to the item (always granted with a share)
  ReadData - read all tables via SQL (validate numbers against rpt.* views)
  ReadAll  - read the Delta files in OneLake -> required for Direct Lake ON ONELAKE authoring

Report viewers get NOTHING here: models use a fixed-identity connection (ADR-003).

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

            # 1) What to do in the UI
            print("  UI: open the item > ... > Share > 'Grant people access'")
            for g in share["grant_to"]:
                print(f"      add group  {principals[g]['name']}")
            for p in share["permissions"]:
                if p in UI_LABELS:
                    print(f"      {UI_LABELS[p]}")
            print("      untick 'Notify recipients by email' > Grant  (propagation can take up to 2 hours)")

            # 2) Verify against the Admin API (read-only)
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

            # 3) Flag direct shares nobody declared (drift / someone shared to an individual)
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
