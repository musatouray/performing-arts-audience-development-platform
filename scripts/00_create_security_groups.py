"""Step 00: create the Microsoft Entra security groups.

Fabric access is given to groups, not to individual people. When someone joins
or leaves, IT changes their group membership in Entra and nothing in Fabric
needs to be touched.

What it does:
  * creates each group listed in tenant.yaml (security_groups) if it's missing
  * adds you to sg-hh-fabric-admins so you can run the rest of the setup
  * saves the group IDs to config/.generated/principals.json for the later scripts

You need an Entra role that can create groups (Groups Administrator or Global Administrator).
Run: uv run python scripts/00_create_security_groups.py [--dry-run] [--add-me-to all]
"""

from lib.fabric import GRAPH_SCOPE, ApiError, Client, banner, save_generated, std_args, tenant_config

GRAPH = "https://graph.microsoft.com/v1.0"


def main():
    ap = std_args(__doc__)
    ap.add_argument(
        "--add-me-to",
        default="fabric_admins",
        help="comma-separated group keys to add the signed-in user to, or 'all' (handy for testing RLS)",
    )
    a = ap.parse_args()
    g = Client(GRAPH, GRAPH_SCOPE, a.dry_run)
    me = g.get("/me")
    banner(f"Signed in as {me['userPrincipalName']}")

    groups = tenant_config()["security_groups"]
    add_me = set(groups) if a.add_me_to == "all" else set(a.add_me_to.split(","))
    principals = {}
    for key, spec in groups.items():
        name = spec["name"]
        found = g.get(f"/groups?$filter=displayName eq '{name}'&$select=id,displayName")["value"]
        if found:
            gid = found[0]["id"]
            print(f"  = {name:<32} exists  {gid}")
        else:
            body = {
                "displayName": name,
                "description": spec["purpose"],
                "mailEnabled": False,
                "mailNickname": name.replace("-", ""),
                "securityEnabled": True,
            }
            gid = g.post("/groups", body)["id"]
            print(f"  + {name:<32} created {gid}")
        principals[key] = {"id": gid, "name": name, "type": "Group"}
        if key in add_me:
            try:
                g.post(f"/groups/{gid}/members/$ref", {"@odata.id": f"{GRAPH}/directoryObjects/{me['id']}"})
                print(f"      added {me['userPrincipalName']} as member")
            except ApiError as e:
                if "already exist" not in str(e.body).lower():
                    raise
    principals["_me"] = {"id": me["id"], "name": me["userPrincipalName"], "type": "User"}
    principals["_tenant_id"] = g.get("/organization?$select=id")["value"][0]["id"]
    if not a.dry_run:
        save_generated("principals.json", principals)
        print("\nWrote config/.generated/principals.json")


if __name__ == "__main__":
    main()
