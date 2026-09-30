"""Step 04 - Deployment pipelines: one per workspace family, stages Dev -> Test -> Prod.

  dp-hh-dataplatform : hh-dataplatform-dev -> hh-dataplatform-test -> hh-dataplatform-prod
  dp-hh-audience     : hh-audience-dev     -> hh-audience-test     -> hh-audience-prod
  dp-hh-education    : hh-education-dev    -> hh-education-test    -> hh-education-prod

Why deployment pipelines (not scripted fabric-cicd) for a 4-person team? Lowest operational
overhead, visual diff between stages, deployment rules for connection swaps, and the
Director of BI can approve/see promotions without reading YAML. fabric-cicd is the
documented scale-up path (see .github/workflows/deploy-fabric-cicd.yml, disabled).

Needs: Admin on every workspace being assigned.
Run:   uv run python scripts/04_create_deployment_pipelines.py [--dry-run]
"""

from lib.fabric import ApiError, Client, banner, load_principals, require_workspace, std_args, tenant_config, ws_name


def main():
    a = std_args(__doc__).parse_args()
    cfg = tenant_config()
    dp_cfg = cfg["deployment_pipelines"]
    c = Client(dry_run=a.dry_run)
    principals = load_principals()
    existing = {p["displayName"]: p for p in c.paged("/deploymentPipelines")}

    for fam in cfg["workspace_families"]:
        name = f"dp-{cfg['org']['code']}-{fam['key']}"
        banner(name)
        if name in existing:
            dp = existing[name]
            print(f"  = exists {dp['id']}")
        else:
            dp = c.post("/deploymentPipelines", {
                "displayName": name,
                "description": f"{fam['display']}: Dev -> Test -> Prod",
                "stages": [{"displayName": s["name"], "description": f"{s['env']} stage", "isPublic": s["public"]}
                           for s in dp_cfg["stages"]],
            })
            print(f"  + created {dp.get('id')}")
        if a.dry_run and dp.get("dryRun"):
            continue

        stages = sorted(c.paged(f"/deploymentPipelines/{dp['id']}/stages"), key=lambda s: s["order"])
        for stage, s_cfg in zip(stages, dp_cfg["stages"]):
            ws = require_workspace(c, ws_name(fam["key"], s_cfg["env"]))
            if stage.get("workspaceId") == ws["id"]:
                print(f"    = {stage['displayName']:<12} -> {ws['displayName']}")
                continue
            c.post(f"/deploymentPipelines/{dp['id']}/stages/{stage['id']}/assignWorkspace", {"workspaceId": ws["id"]})
            print(f"    + {stage['displayName']:<12} -> {ws['displayName']}")

        for g in dp_cfg["admins"]:
            try:
                c.post(f"/deploymentPipelines/{dp['id']}/roleAssignments",
                       {"principal": {"id": principals[g]["id"], "type": "Group"}, "role": "Admin"})
                print(f"    Admin: {principals[g]['name']}")
            except ApiError as e:
                if e.status != 409:
                    raise


if __name__ == "__main__":
    main()
