# ADR-005: CI/CD

## Options

| Option | Pros | Cons |
|---|---|---|
| Manual publish | None worth having | Drift, no audit trail, no rollback |
| **Git integration on DEV + Fabric deployment pipelines** | Low overhead; visual stage diff; deployment rules; the Director of BI can approve in the UI | Less automatable; rules are limited for some item types |
| fabric-cicd + GitHub Actions + service principal | Fully code-first; PR-gated; parameterized IDs; scales to many workspaces | More engineering; secrets management; less visible to non-engineers |

## Decision

**Git integration on DEV workspaces plus deployment pipelines.** `fabric-cicd` is documented and wired up (`scripts/deploy_fabric_cicd.py`, `deploy-fabric-cicd.yml`) as the **scale-up path**.

How work flows:

- Developers work in feature workspaces ("Branch out"), open a PR (CI validates config, tests and notebook build), and merge to `main`.
- DEV then syncs from Git and is promoted to TEST (UAT) and then PROD (approval).
- PROD is never edited directly: builders are Viewers there (ADR-004).

**Say it in 30 seconds:** "Git is the source of truth for development, and deployment pipelines are the only way into production. I'd start with the lowest-overhead option a four-person team will actually use, and move to fabric-cicd when deploy frequency justifies it."

**Revisit when:** deploying more than a few times a week, managing more than 15 workspaces, or when an auditor asks for PR-gated production deployments.
