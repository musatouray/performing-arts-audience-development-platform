"""Step 01: create the Fabric domain and its subdomains.

Domains group workspaces by business area so data is easy to find in the
OneLake catalog. They don't give anyone access to data; workspace roles do.

  Harmonia Hall (parent)
    |- Data Platform           hh-dataplatform-dev/test/prod
    |- Audience & Development  hh-audience-dev/test/prod
    |- Education & Community   hh-education-dev/test/prod

Domain admins are set on the parent only, and the subdomains inherit them.
Workspaces are added to their domains in step 02, once they exist.

You need to be a Fabric administrator.
Run: uv run python scripts/01_create_domains.py [--dry-run]
"""

from lib.fabric import Client, banner, load_principals, save_generated, std_args, tenant_config


def main():
    a = std_args(__doc__).parse_args()
    c = Client(dry_run=a.dry_run)
    principals = load_principals()
    existing = {d["displayName"]: d for d in c.get("/admin/domains").get("domains", [])}
    ids = {}

    banner("Domains")
    for d in tenant_config()["domains"]:          # the parent comes first in tenant.yaml
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

        # Subdomains inherit their admins from the parent, so only the parent gets roles.
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
