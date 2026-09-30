"""Step 00 - Microsoft Entra security groups (Microsoft Graph).

Why: Fabric permissions are granted to GROUPS, never individuals. Joiners/leavers are
handled in Entra.
In corporate environments, access to data tools like Microsoft Fabric should never be given to individuals directly.
Instead, permissions are assigned to Security Groups. When a worker joins or leaves a company, an IT administrator
simply changes their group membership in Entra ID rather than updating permissions inside Fabric.
This script automates setting up those foundation groups.

What it does
  * creates each group in tenant.yaml > security_groups if missing (security-enabled, not mail-enabled)
  * adds YOU to sg-hh-fabric-admins (so the demo works end-to-end)
  * writes config/.generated/principals.json  (group key -> object id) for later scripts

Needs: Entra role that can create groups (Groups Administrator / Global Administrator).
Run:   uv run python scripts/00_create_security_groups.py [--dry-run] [--add-me-to all]
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
