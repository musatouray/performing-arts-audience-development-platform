"""Prints the setup steps in order. Each step is its own script (see docs/01-runbook.md).
"""

STEPS = [
    ("validate", "uv run python scripts/validate_config.py", "Lint the tenant design (runs in CI too)"),
    ("00", "uv run python scripts/00_create_security_groups.py", "Entra security groups"),
    ("01", "uv run python scripts/01_create_domains.py", "Domains + subdomains"),
    ("02", "uv run python scripts/02_create_workspaces.py", "9 workspaces, capacity, domain, group roles"),
    ("03", "uv run python scripts/03_create_items.py", "lh_bronze, lh_silver, wh_gold in every env"),
    ("04", "uv run python scripts/04_create_deployment_pipelines.py", "Dev -> Test -> Prod pipelines"),
    ("05", "uv run python scripts/05_connect_git.py", "GitHub integration for DEV workspaces"),
    ("data", "uv run python -m data_generator.generate full", "Synthetic data for all four sources"),
    ("06", "uv run python scripts/06_upload_config.py --env dev", "Config files for the notebooks"),
    ("11", "uv run python scripts/11_load_ticketing_db.py", "Ticketing data into SQL Server"),
    ("10", "uv run python scripts/10_create_shortcuts.py --env dev", "Shortcut to the marketing ADLS container"),
    ("07", "uv run python scripts/07_apply_onelake_security.py --env dev", "OneLake security roles"),
    ("09", "uv run python scripts/09_verify_item_shares.py", "Share wh_gold with BI developers (UI) + verify"),
    ("08", "uv run python scripts/08_audit_tenant_settings.py", "Tenant settings audit"),
]


def main():
    print("Performing Arts Audience & Development Platform - build order\n")
    for key, cmd, what in STEPS:
        print(f"  [{key:>8}] {what:<45} {cmd}")
    print("\nAdd --dry-run to any provisioning script to preview. Full guide: docs/01-runbook.md")


if __name__ == "__main__":
    main()
