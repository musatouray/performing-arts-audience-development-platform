"""Step 08 - Audit tenant settings against the governance baseline (read-only).

Tenant settings are the outermost governance layer (who can create items, share
externally, publish to web, use service principals, etc.). We treat them as
*audited configuration*: export them, compare to a baseline, review drift monthly.
Changes themselves are made by a Fabric admin in the Admin portal (and recorded in
docs/05-governance-and-security.md) - deliberately not automated.

Output: docs/tenant-settings-audit.md  (commit it -> audit trail in Git history)
Run:    uv run python scripts/08_audit_tenant_settings.py
"""

from datetime import datetime

from lib.fabric import ROOT, Client, std_args

# (keyword in setting title, recommended state, reason)
BASELINE = [
    ("Publish to web", False, "Public, anonymous links are a data-leak vector (donor data)."),
    ("Users can create Fabric items", True, "Enabled, but scoped to sg-hh-fabric-admins / engineers / BI developers."),
    ("Create workspaces", True, "Scoped to platform admins; everyone else requests a workspace (keeps topology clean)."),
    ("Service principals can", True, "Needed for CI/CD (fabric-cicd) - scoped to a dedicated security group."),
    ("Git integration", True, "Users can synchronize workspace items with their Git repositories."),
    ("GitHub", True, "Allow GitHub as a Git provider."),
    ("Export to Excel", True, "Allowed, but sensitivity labels + DLP travel with the export."),
    ("sensitivity labels", True, "Allow users to apply sensitivity labels (Purview)."),
    ("External data sharing", False, "No cross-tenant OneLake sharing without review."),
    ("guest users", False, "B2B guests off by default; exceptions per workspace."),
    ("Domain admins", True, "Allow domain admins to delegate settings (domain governance)."),
    ("Microsoft Fabric", True, "Fabric enabled (scoped to the BI & data groups during rollout)."),
    ("Copilot", True, "Allowed once Gold layer is certified (AI-readiness)."),
    ("Workspace identity", True, "Trusted workspace access without secrets."),
]


def main():
    std_args(__doc__).parse_args()
    c = Client()
    settings = list(c.paged("/admin/tenantsettings", key="tenantSettings"))
    lines = [f"# Tenant settings audit\n\n_Generated {datetime.now():%Y-%m-%d %H:%M} by scripts/08_audit_tenant_settings.py_\n",
             "## Baseline checks\n", "| Setting | Enabled | Scoped to groups | Recommended | Status | Why |", "|---|---|---|---|---|---|"]
    for kw, want, why in BASELINE:
        matches = [s for s in settings if kw.lower() in s.get("title", "").lower()]
        if not matches:
            lines.append(f"| _{kw}_ (not found) | | | {want} | REVIEW | {why} |")
        for s in matches:
            groups = ", ".join(g.get("name", "") for g in s.get("enabledSecurityGroups", []) or []) or "entire org"
            status = "OK" if s.get("enabled") == want else "DRIFT"
            lines.append(f"| {s['title']} | {s.get('enabled')} | {groups} | {want} | {status} | {why} |")
    lines += ["\n## All settings\n", "| Group | Setting | Enabled |", "|---|---|---|"]
    for s in sorted(settings, key=lambda x: (x.get("tenantSettingGroup", ""), x.get("title", ""))):
        lines.append(f"| {s.get('tenantSettingGroup', '')} | {s.get('title', '')} | {s.get('enabled')} |")
    out = ROOT / "docs" / "tenant-settings-audit.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    drift = sum(1 for line in lines if "| DRIFT |" in line)
    print(f"{len(settings)} settings exported, {drift} drift item(s) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
