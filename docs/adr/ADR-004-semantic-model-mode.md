# ADR-004: Semantic model storage mode

## Options

| Mode | Pros | Cons |
|---|---|---|
| Import | Fastest queries; full Power Query; any DAX | Scheduled refreshes; a data copy; refresh CU cost; stale between refreshes |
| DirectQuery | Always live | Slow; heavy load on the source; limited DAX performance |
| Direct Lake on SQL endpoint | No copy; respects SQL views and security | **Falls back to DirectQuery** for views and SQL-level RLS, so performance is unpredictable |
| **Direct Lake on OneLake** | No copy; near-real-time; **no DirectQuery fallback**; can combine tables from several items | Needs OneLake access, or a **fixed identity**; SQL RLS/DDM don't apply, so security must live in the model |

## Decision

Enterprise models (`sm_audience_development`, `sm_education_impact`) use **Direct Lake on OneLake** with a **fixed-identity connection** owned by the platform team.

- Security for report consumers is **model RLS/OLS**.
- Small departmental models can still use Import.

## Consequences

- There's no refresh schedule. Reports reflect Gold as soon as `usp_load_gold` commits (the model reframes).
- The security design is explicit about layers. See ADR-006.
- **Promotion gotcha:** the models live in BI workspaces but read `wh_gold` in the Data Platform workspace. A deployment copies the model's source as is, so after deploying to TEST or PROD it still reads DEV's Gold. `nb_rebind_sm_finance` (deployed with the model) reads that stage's Gold IDs from the `vl_finance` variable library and rewrites the source; semantic models can't read a variable library themselves. See the runbook, 4.6 and 5.4.

> [!NOTE]
> *"Direct Lake on OneLake gives us import-like speed with no refresh to babysit and no silent fallback to DirectQuery. The trade-off is that security moves into the model, which is where report users are anyway."*

**Revisit when:** a model needs heavy Power Query transforms, or data outside OneLake. Then use Import or a composite model.
