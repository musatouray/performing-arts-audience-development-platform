"""Step 99: remove everything the setup created (pipelines, workspaces, domains).

Only items named in tenant.yaml are deleted. Without --confirm it just lists
what would be removed. Security groups are kept; delete those in Entra.

Run: uv run python scripts/99_teardown.py            # preview
     uv run python scripts/99_teardown.py --confirm  # delete
"""

import argparse

from lib.fabric import Client, banner, find_workspace, tenant_config, ws_name


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    cfg = tenant_config()
    c = Client(dry_run=not a.confirm)
    if not a.confirm:
        print("PREVIEW ONLY - re-run with --confirm to delete.")

    banner("Deployment pipelines")
    names = {f"dp-{cfg['org']['code']}-{f['key']}" for f in cfg["workspace_families"]}
    for dp in c.paged("/deploymentPipelines"):
        if dp["displayName"] in names:
            for st in c.paged(f"/deploymentPipelines/{dp['id']}/stages"):
                if st.get("workspaceId"):
                    c.post(f"/deploymentPipelines/{dp['id']}/stages/{st['id']}/unassignWorkspace")
            c.call("DELETE", f"/deploymentPipelines/{dp['id']}")
            print(f"  - {dp['displayName']}")

    banner("Workspaces")
    for fam in cfg["workspace_families"]:
        for env in cfg["environments"]:
            ws = find_workspace(c, ws_name(fam["key"], env))
            if ws:
                c.call("DELETE", f"/workspaces/{ws['id']}")
                print(f"  - {ws['displayName']}")

    banner("Domains (children first)")
    existing = {d["displayName"]: d["id"] for d in c.get("/admin/domains").get("domains", [])}
    for d in reversed(cfg["domains"]):
        if d["name"] in existing:
            c.call("DELETE", f"/admin/domains/{existing[d['name']]}")
            print(f"  - {d['name']}")


if __name__ == "__main__":
    main()
