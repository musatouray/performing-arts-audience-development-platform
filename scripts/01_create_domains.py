"""Step 01 - Fabric domains & subdomains (Admin API).

Why: Domains group workspaces by BUSINESS AREA so the OneLake catalog is navigable,
governance can be delegated (domain admins), and domain-level defaults (e.g. default
sensitivity label) can be applied. Domains are NOT a security boundary - domain roles
grant no access to workspaces or data; access is workspace/item/OneLake security.

Role rules (Fabric):
  * Domain admins are assigned on the PARENT domain; subdomains inherit them.
  * Domain contributors are workspace admins allowed to self-assign their workspaces.
    Not used here - step 02 assigns workspaces centrally as Fabric admin.

Topology (tenant.yaml > domains):
  Harmonia Hall (parent)
    |- Data Platform           <- hh-dataplatform-{dev,test,prod}
    |- Audience & Development  <- hh-audience-{dev,test,prod}
    |- Education & Community   <- hh-education-{dev,test,prod}

Workspaces are assigned to domains in step 02 (they must exist first).
Needs: Fabric administrator.   Run: uv run python scripts/01_create_domains.py [--dry-run]
"""

from lib.fabric import Client, banner, load_principals, save_generated, std_args, tenant_config


def main():
    a = std_args(__doc__).parse_args()
    c = Client(dry_run=a.dry_run)
    principals = load_principals()
    existing = {d["displayName"]: d for d in c.get("/admin/domains").get("domains", [])}
    ids = {}

    banner("Domains")
    for d in tenant_config()["domains"]:          # parents are listed before children in the YAML
        if d["name"] in existing:
            dom = existing[d["name"]]
            print(f"  = {d['name']:<28} exists  {dom['id']}")
        else:
            body = {"displayName": d["name"], "description": d["description"]}
            if d.get("parent"):
                body["parentDomainId"] = ids[d["parent"]]
            dom = c.post("/admin/domains", body)
            print(f"  + {d['name']:<28} created {dom.get('id')}")
        ids[d["key"]] = dom["id"]

        # Delegate governance (GROUPS only). Subdomains inherit roles from the parent,
        # so role assignments are only sent for top-level domains.
        if d.get("parent"):
            if d.get("admins") or d.get("contributors"):
                print("      (roles ignored: subdomains inherit the parent domain's admins)")
            continue
        for role_key, api_type in (("admins", "Admins"), ("contributors", "Contributors")):
            members = [{"id": principals[g]["id"], "type": "Group"} for g in d.get(role_key, [])]
            if members:
                c.post(f"/admin/domains/{dom['id']}/roleAssignments/bulkAssign", {"type": api_type, "principals": members})
                print(f"      {api_type}: {', '.join(principals[g]['name'] for g in d[role_key])}")

    if not a.dry_run:
        save_generated("domains.json", ids)


if __name__ == "__main__":
    main()
