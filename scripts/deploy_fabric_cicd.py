"""Optional, for later: deploy from GitHub with Microsoft's fabric-cicd library.

Today, changes reach test and prod through deployment pipelines. Switch to this when:
  * releases happen often, or need GitHub pull request checks and approvals
  * there are more workspaces than are practical to manage in the portal
  * IDs need to be swapped per environment (parameter.yml)

It signs in as a service principal with Admin or Contributor on the target
workspace. Credentials come from GitHub secrets, never from the repo.

Run locally: uv run --group cicd python scripts/deploy_fabric_cicd.py --family dataplatform --env test
In GitHub:   .github/workflows/deploy-fabric-cicd.yml (started by hand)
"""

import argparse
import os

from lib.fabric import Client, require_workspace, tenant_config, ws_name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", required=True, choices=[f["key"] for f in tenant_config()["workspace_families"]])
    ap.add_argument("--env", required=True, choices=["test", "prod"])
    a = ap.parse_args()

    from azure.identity import ClientSecretCredential
    from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items

    fam = next(f for f in tenant_config()["workspace_families"] if f["key"] == a.family)
    ws = require_workspace(Client(), ws_name(a.family, a.env))
    cred = ClientSecretCredential(os.environ["AZURE_TENANT_ID"], os.environ["AZURE_CLIENT_ID"], os.environ["AZURE_CLIENT_SECRET"])

    target = FabricWorkspace(
        workspace_id=ws["id"],
        environment=a.env.upper(),                         # which values to use from parameter.yml
        repository_directory=fam["git_directory"],
        item_type_in_scope=["Notebook", "DataPipeline", "SemanticModel", "Report"],
        token_credential=cred,
    )
    publish_all_items(target)
    unpublish_all_orphan_items(target)                     # remove items that were deleted in Git
    print(f"Deployed {fam['git_directory']} -> {ws['displayName']}")


if __name__ == "__main__":
    main()
