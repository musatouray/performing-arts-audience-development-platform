# fabric/de

**Managed by Fabric Git integration. Don't hand-edit.**

The DEV workspace syncs its items here: notebooks, pipelines, semantic models and reports, each as an `<name>.<ItemType>/` folder with a `.platform` file.
Create or change items in the Fabric UI (or a feature workspace), then **Source control › Commit**.
Deployment pipelines promote from the DEV workspace to TEST and PROD.

## Exceptions to "don't hand-edit"

- `df_education_sharepoint.Dataflow/mashup.pq`: the `DefaultDestination` line reads `WorkspaceId` and `LakehouseId` from `vl_platform`. The Dataflow editor doesn't show the default destination, so that one line is maintained in Git.
- Stage-specific values (warehouse, lakehouses, connections) live in `vl_platform.VariableLibrary`: one value set per stage, made active in each stage's workspace.
