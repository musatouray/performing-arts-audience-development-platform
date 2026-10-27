"""Step 08: check the tenant settings against the agreed baseline. Read-only.

Tenant settings control things like who can create items, publish to the web or
share data outside the organization. They are changed by hand in the Admin
portal; this script exports them and flags any that differ from the baseline.

Output: docs/tenant-settings-audit.md. Commit it to keep a history of changes.
Run: uv run python scripts/08_audit_tenant_settings.py
"""

from datetime import datetime

from lib.fabric import ROOT, Client, std_args

ADMINS, BUILDERS = ["sg-hh-fabric-admins"], ["sg-hh-fabric-admins", "sg-hh-data-engineers", "sg-hh-bi-developers"]

# (setting title as the Admin portal shows it, expected on/off, groups it must be limited to or None, reason)
# Titles are matched exactly, ignoring case, spaces at the ends and a trailing "(preview)".
BASELINE = [
    ("Publish to web", False, None, "Public, anonymous links: the main leak risk for donor data."),
    ("External data sharing", False, None, "No cross-tenant OneLake sharing without review."),
    ("Guest users can access Microsoft Fabric", False, None, "B2B guests off by default; exceptions per workspace."),
    ("Create workspaces", True, ADMINS, "Only platform admins create workspaces, so the topology stays as designed."),
    ("Users can create Fabric items", True, BUILDERS, "Builders only: no shadow items."),
    ("Certification", True, ADMINS, "Only the people who apply the certification criteria can certify."),
    ("Service principals can call Fabric public APIs", True, None, "CI/CD (fabric-cicd), limited to a dedicated group."),
    ("Users can synchronize workspace items with their Git repositories", True, None, "Git integration on DEV."),
    ("Users can sync workspace items with GitHub repositories", True, None, "The repo lives on GitHub."),
    ("Allow tenant and domain admins to override workspace assignments", True, None, "Script 02 assigns workspaces to domains."),
    ("Users can access data stored in OneLake with apps external to Fabric", True, None, "Script 06 uploads config over the ADLS API."),
    ("Users can work with semantic models in Excel using a live connection", True, None, "Excel is a main way to use the models."),
    ("Allow users to apply sensitivity labels for content", True, BUILDERS, "Builders label what they publish (Purview)."),
    ("Apply sensitivity labels from data sources to their data in Power BI", True, None, "Gold's label reaches the models."),
    ("Automatically apply sensitivity labels to downstream content", True, None, "Labels follow data into reports and Excel exports."),
    ("Users can use Copilot, AI Agents and other AI experiences powered by Azure OpenAI", True, None, "Data agents and Copilot (TODO section 9)."),
    ("Users can create Ontology (preview) items", True, None, "Fabric IQ ontology (TODO section 9)."),
    ("Enable anonymous data access for Fabric Apps", False, None, "Apps sign users in with Entra; never anonymous."),
]


def _norm(title: str) -> str:
    t = (title or "").strip().lower()
    return t[: -len("(preview)")].strip() if t.endswith("(preview)") else t


def main():
    std_args(__doc__).parse_args()
    c = Client()
    settings = list(c.paged("/admin/tenantsettings", key="tenantSettings"))
    lines = [f"# Tenant settings audit\n\n_Generated {datetime.now():%Y-%m-%d %H:%M} by scripts/08_audit_tenant_settings.py_\n",
             "## Baseline checks\n", "| Setting | Enabled | Scoped to groups | Expected | Status | Why |", "|---|---|---|---|---|---|"]
    by_title = {_norm(t["title"]): t for t in settings if t.get("title")}
    for title, want, scope, why in BASELINE:
        s = by_title.get(_norm(title))
        if s is None:
            lines.append(f"| _{title}_ (not found) | | | {want} | REVIEW | {why} |")
            continue
        groups = [g.get("name", "") for g in s.get("enabledSecurityGroups", []) or []]
        status = "OK"
        if s.get("enabled") != want:
            status = "DRIFT"
        elif want and scope and not set(scope) <= set(groups):
            status = "SCOPE"   # on, but not limited to (or missing) the expected groups
        expected = f"{want}" + (f" for {', '.join(scope)}" if scope else "")
        lines.append(f"| {s['title'].strip()} | {s.get('enabled')} | {', '.join(groups) or 'entire org'} | {expected} | {status} | {why} |")
    lines += ["\n## All settings\n", "| Group | Setting | Enabled |", "|---|---|---|"]
    for s in sorted(settings, key=lambda x: (x.get("tenantSettingGroup", ""), x.get("title", ""))):
        lines.append(f"| {s.get('tenantSettingGroup', '')} | {s.get('title', '')} | {s.get('enabled')} |")
    out = ROOT / "docs" / "tenant-settings-audit.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    drift = sum(1 for line in lines if "| DRIFT |" in line)
    scope = sum(1 for line in lines if "| SCOPE |" in line)
    print(f"{len(settings)} settings exported, {drift} drift and {scope} scope item(s) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
