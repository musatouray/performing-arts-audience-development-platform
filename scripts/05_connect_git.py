"""Step 05: connect the dev workspaces to GitHub.

  hh-dataplatform-dev  syncs with  main:/fabric/de
  hh-audience-dev      syncs with  main:/fabric/bi-audience
  hh-education-dev     syncs with  main:/fabric/bi-education

Only dev is connected. Test and prod get changes through deployment pipelines,
so prod always matches what was reviewed and merged.

Before running: create a GitHub connection in Fabric (Settings > Manage
connections and gateways > New > GitHub - Source control) using a fine-grained
personal access token, then put its ID in .env (FABRIC_GIT_CONNECTION_ID).

Run: uv run python scripts/05_connect_git.py [--dry-run]
"""

import sys

from lib.config import unfilled
from lib.fabric import ApiError, Client, banner, require_workspace, std_args, tenant_config, ws_name


def main():
    a = std_args(__doc__).parse_args()
    cfg = tenant_config()
    git = cfg["git"]
    if (not git.get("connection_id") or unfilled(git["connection_id"])) and not a.dry_run:
        sys.exit("Add FABRIC_GIT_CONNECTION_ID to .env first (see docstring).")
    c = Client(dry_run=a.dry_run)

    for fam in cfg["workspace_families"]:
        ws = require_workspace(c, ws_name(fam["key"], "dev"))
        banner(f"{ws['displayName']} <-> {git['branch']}:{fam['git_directory']}")
        try:
            c.post(f"/workspaces/{ws['id']}/git/connect", {
                "gitProviderDetails": {"gitProviderType": "GitHub", "ownerName": git["owner"],
                                       "repositoryName": git["repository"], "branchName": git["branch"],
                                       "directoryName": fam["git_directory"]},
                "myGitCredentials": {"source": "ConfiguredConnection", "connectionId": git.get("connection_id") or "<set-me>"},
            })
            print("  + connected")
        except ApiError as e:
            if "AlreadyConnected" not in e.code:
                raise
            print("  = already connected")

        # On the first sync, keep what is in the workspace, since the items were created there.
        init = c.post(f"/workspaces/{ws['id']}/git/initializeConnection", {"initializationStrategy": "PreferWorkspace"})
        action = init.get("requiredAction", "None")
        print(f"  requiredAction: {action}")
        if action == "CommitToGit":
            c.post(f"/workspaces/{ws['id']}/git/commitToGit",
                   {"mode": "All", "workspaceHead": init.get("workspaceHead"), "comment": "Initial sync from Fabric workspace"})
            print("  committed workspace items to Git")
        elif action == "UpdateFromGit":
            c.post(f"/workspaces/{ws['id']}/git/updateFromGit",
                   {"remoteCommitHash": init.get("remoteCommitHash"), "workspaceHead": init.get("workspaceHead"),
                    "conflictResolution": {"conflictResolutionType": "Workspace", "conflictResolutionPolicy": "PreferWorkspace"},
                    "options": {"allowOverrideItems": True}})
            print("  updated workspace from Git")


if __name__ == "__main__":
    main()
