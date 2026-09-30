"""Step 05 - Git integration (GitHub) for the DEV workspaces only.

  hh-dataplatform-dev  <->  main : fabric/de
  hh-audience-dev      <->  main : fabric/bi-audience
  hh-education-dev     <->  main : fabric/bi-education

Why only DEV? Git is the source of truth for *development*; Test/Prod are populated by
deployment pipelines, so Prod can never drift from what was reviewed. Engineers work in
feature branches ("Branch out to new workspace" in the Fabric UI), open a PR, merge to
main, then sync DEV and promote.

Prerequisite (one-time, UI): Fabric > Settings > Manage connections and gateways >
New > "GitHub - Source control" with a fine-grained PAT (Contents: Read & write on this
repo). Paste the connection ID into tenant.yaml > git.connection_id.

Run: uv run python scripts/05_connect_git.py [--dry-run]
"""

import sys

from lib.fabric import ApiError, Client, banner, require_workspace, std_args, tenant_config, ws_name


def main():
    a = std_args(__doc__).parse_args()
    cfg = tenant_config()
    git = cfg["git"]
    if not git.get("connection_id") and not a.dry_run:
        sys.exit("Set git.connection_id in config/tenant.yaml first (see docstring).")
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

        # Initialize: workspace content wins on first sync (items were created in the workspace).
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
