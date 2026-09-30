"""Step 02 - Workspaces: create, bind to capacity, assign to domain, grant GROUP roles.

Topology = 3 workspace families x 3 environments = 9 workspaces:

  family \\ env        dev                    test                   prod
  Data Platform       hh-dataplatform-dev    hh-dataplatform-test   hh-dataplatform-prod
  Audience BI         hh-audience-dev        hh-audience-test       hh-audience-prod
  Education BI        hh-education-dev       hh-education-test      hh-education-prod

Why split DATA PLATFORM from BI workspaces?
  * Engineers own raw/bronze/silver; analysts never need workspace access to it.
  * BI workspaces hold semantic models + reports; access is granted per business area.
  * Each BI workspace publishes ONE org App -> consumers never get workspace roles.
Why Viewer-only (except Admin) in PROD? Nobody hand-edits prod; changes arrive via
deployment pipelines only (separation of duties).

Run: uv run python scripts/02_create_workspaces.py [--dry-run] [--env dev]
"""

from lib.fabric import (ApiError, Client, banner, find_workspace, load_principals, pick_capacity, save_generated,
                        std_args, tenant_config, ws_name)


def upsert_role(c: Client, ws_id: str, principal: dict, role: str):
    """Add a workspace role; if the principal already has one, update it to the desired role."""
    body = {"principal": {"id": principal["id"], "type": principal["type"]}, "role": role}
    try:
        c.post(f"/workspaces/{ws_id}/roleAssignments", body)
    except ApiError as e:
        if e.status != 409:
            raise
        current = next(r for r in c.paged(f"/workspaces/{ws_id}/roleAssignments") if r["principal"]["id"] == principal["id"])
        if current["role"] != role:
            c.call("PATCH", f"/workspaces/{ws_id}/roleAssignments/{current['id']}", {"role": role})


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", choices=["dev", "test", "prod"], help="only this environment")
    a = ap.parse_args()
    cfg = tenant_config()
    c = Client(dry_run=a.dry_run)
    principals = load_principals()
    cap = pick_capacity(c)
    domains = {d["displayName"]: d["id"] for d in c.get("/admin/domains").get("domains", [])}
    domain_by_key = {d["key"]: domains.get(d["name"]) for d in cfg["domains"]}
    print(f"Capacity: {cap['displayName']} ({cap.get('sku')})  {cap['id']}")

    created = {}
    for fam in cfg["workspace_families"]:
        banner(fam["display"])
        for env in cfg["environments"]:
            if a.env and env != a.env:
                continue
            name = ws_name(fam["key"], env)
            ws = find_workspace(c, name)
            if ws:
                print(f"  = {name:<26} exists  {ws['id']}")
            else:
                ws = c.post("/workspaces", {"displayName": name, "capacityId": cap["id"],
                                            "description": f"{fam['display']} [{env.upper()}] - managed by tenant.yaml"})
                print(f"  + {name:<26} created {ws.get('id')}")
            if ws.get("capacityId") and ws["capacityId"] != cap["id"]:
                c.post(f"/workspaces/{ws['id']}/assignToCapacity", {"capacityId": cap["id"]})

            # Roles: groups only. The signed-in admin keeps Admin as creator.
            for group_key, role in fam["roles"][env].items():
                upsert_role(c, ws["id"], principals[group_key], role)
                print(f"      {role:<11} {principals[group_key]['name']}")
            created[name] = ws["id"]

        # Domain assignment (one call per family: dev+test+prod land in the same domain).
        dom_id = domain_by_key.get(fam["domain"])
        fam_ids = [created[ws_name(fam["key"], e)] for e in cfg["environments"] if ws_name(fam["key"], e) in created]
        if dom_id and fam_ids:
            c.post(f"/admin/domains/{dom_id}/assignWorkspaces", {"workspacesIds": fam_ids})
            print(f"      domain -> {fam['domain']}")

    if not a.dry_run:
        save_generated("workspaces.json", created)


if __name__ == "__main__":
    main()
