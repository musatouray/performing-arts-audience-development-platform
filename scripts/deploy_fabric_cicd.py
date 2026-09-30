"""SCALE-UP PATH (not used day-one): code-first deployment with Microsoft's `fabric-cicd` library.

When to switch from deployment pipelines to this (ADR-005):
  * deployments become frequent (daily) or need to be gated by GitHub PR checks/approvals
  * more environments/workspaces than a UI can comfortably manage
  * you need find/replace of IDs per environment in item definitions (parameter.yml)

Auth: service principal (SP) in the sg for "Service principals can use Fabric APIs", Admin/Contributor on
the target workspace. Secrets come from GitHub Actions secrets, never from the repo.

Run locally:  uv run --group cicd python scripts/deploy_fabric_cicd.py --family dataplatform --env test
In CI:        .github/workflows/deploy-fabric-cicd.yml (manual trigger)
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
        environment=a.env.upper(),                         # selects values in <dir>/parameter.yml
        repository_directory=fam["git_directory"],
        item_type_in_scope=["Notebook", "DataPipeline", "SemanticModel", "Report"],
        token_credential=cred,
    )
    publish_all_items(target)
    unpublish_all_orphan_items(target)                     # removes items deleted from Git
    print(f"Deployed {fam['git_directory']} -> {ws['displayName']}")


if __name__ == "__main__":
    main()
