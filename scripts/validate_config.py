"""Check the config files for mistakes before anything is created in Fabric.
This also runs automatically on every pull request.

It checks that:
  * every group used anywhere is defined in security_groups
  * domain admins are only set on the parent domain
  * item shares point at real items and groups, and don't repeat a workspace role
  * every workspace family has a valid domain and roles for every environment
  * only real workspace roles are used, and nobody can edit prod directly
  * every source says how it reaches Bronze, in a way the notebooks understand
  * every data quality rule points at a real table and column
  * every table in the OneLake security roles exists
  * restricted columns (contact details) are listed as pii, and no OneLake role can see them
  * source, schema, table and column names are plain identifiers, safe to use in SQL
  * no committed file holds tenant-specific values (IDs or email addresses); those belong in .env

Run: uv run python scripts/validate_config.py  (exits with an error if anything is wrong)
"""

import os
import re
import sys
from pathlib import Path

import yaml
from lib.config import ROOT, sources_config, tenant_config, unfilled

CONFIG = Path(__file__).resolve().parents[1] / "config"
VALID_ROLES = {"Admin", "Member", "Contributor", "Viewer"}
# Which ingestion tools land files (that nb_10 loads) and which write Bronze tables themselves.
LANDS_IN = {"copy_job": "bronze_table", "dataflow": "bronze_table", "notebook_api": "files", "shortcut": "files"}
CORE_TABLES = {"core/patron": ["patron_id", "first_name", "last_name", "email", "phone", "address_line1", "city", "state",
                               "postal_code", "country", "patron_type", "email_opt_in", "first_seen_date", "source_systems",
                               "updated_at"]}


# Names end up in SQL statements, where they can't be passed as parameters, so they must be plain identifiers.
SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Tenant-specific values must stay out of committed files. These patterns catch the usual leaks.
GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+(?:\.[\w-]+)+)\b")
EXAMPLE_DOMAINS = {"yourdomain.com", "example.com", "contoso.com"}
SCAN_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".sql", ".dax", ".toml", ".mmd", ".txt", ".example"}
# Not scanned: ignored by Git (.env, data, .generated, *.local.*), or written by Fabric itself (fabric/).
SKIP_DIRS = {".git", ".venv", "data", "__pycache__", ".generated", "fabric", "node_modules"}


def tenant_data_in_repo() -> list[str]:
    found = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]          # don't even walk into .venv, data, ...
        for name in files:
            p = Path(folder) / name
            rel = p.relative_to(ROOT)
            if ".local." in name or (p.suffix not in SCAN_SUFFIXES and name != ".env.example"):
                continue
            found += _scan(p, rel)
    return found


def _scan(p: Path, rel: Path) -> list[str]:
    found = []
    for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        guids = [g for g in GUID.findall(line) if set(g) - {"0", "-"}]
        emails = [m.group(0) for m in EMAIL.finditer(line) if m.group(1).lower() not in EXAMPLE_DOMAINS]
        for value in guids + emails:
            found.append(f"{rel.as_posix()}:{n}: looks tenant-specific ({value}) - move it to .env")
    return found


def main() -> int:
    tenant = tenant_config()            # with your .env values filled in
    sources = sources_config()          # with your .env values filled in
    dq = yaml.safe_load((CONFIG / "dq_rules.yaml").read_text())
    errors: list[str] = []
    groups = set(tenant["security_groups"])
    domains = {d["key"] for d in tenant["domains"]}

    for d in tenant["domains"]:
        if d.get("parent") and d["parent"] not in domains:
            errors.append(f"domain {d['key']}: unknown parent {d['parent']}")
        if d.get("parent") and (d.get("admins") or d.get("contributors")):
            errors.append(f"domain {d['key']}: subdomains inherit roles from their parent - remove admins/contributors")
        for g in d.get("admins", []) + d.get("contributors", []):
            if g not in groups:
                errors.append(f"domain {d['key']}: unknown group {g}")

    for fam in tenant["workspace_families"]:
        if fam["domain"] not in domains:
            errors.append(f"family {fam['key']}: unknown domain {fam['domain']}")
        for env in tenant["environments"]:
            roles = fam["roles"].get(env)
            if roles is None:
                errors.append(f"family {fam['key']}: no roles for env {env}")
                continue
            for g, role in roles.items():
                if g not in groups:
                    errors.append(f"family {fam['key']}/{env}: unknown group {g}")
                if role not in VALID_ROLES:
                    errors.append(f"family {fam['key']}/{env}: invalid role {role}")
                if env == "prod" and role in ("Contributor", "Member") and g != "fabric_admins":
                    errors.append(f"family {fam['key']}/prod: {g} has {role} (prod should only change through a deployment pipeline)")

    warnings: list[str] = []
    for s in sources["sources"]:
        ing = s.get("ingestion") or {}
        method, lands_in = ing.get("method"), ing.get("lands_in")
        if method not in LANDS_IN:
            errors.append(f"{s['source']}: ingestion.method must be one of {sorted(LANDS_IN)}")
        elif lands_in != LANDS_IN[method]:
            errors.append(f"{s['source']}: a {method} lands in {LANDS_IN[method]}, not {lands_in}")
        if lands_in == "files" and s.get("format") not in ("csv", "json"):
            errors.append(f"{s['source']}: sources that land files need format: csv or json")
        missing = unfilled(ing) + (["connection_id"] if ing.get("adls", {}).get("connection_id") == "" else [])
        if missing:
            warnings.append(f"{s['source']}: no value yet for {', '.join(missing)} (add it to .env)")

    entities = {}
    restricted_by_table: dict[str, set] = {}
    for s in sources["sources"]:
        names = [s["source"], (s.get("ingestion") or {}).get("bronze_schema") or s["source"]]
        for e in s["entities"]:
            names += [e["name"], *e["columns"]]
        for n in names:
            if not SAFE_NAME.match(n):
                errors.append(f"{s['source']}: '{n}' isn't a safe name (letters, digits and _ only)")
        for e in s["entities"]:
            entities[f"{s['source']}.{e['name']}"] = set(e["columns"])
            for pk in e["primary_key"]:
                if pk not in e["columns"]:
                    errors.append(f"{s['source']}.{e['name']}: primary key {pk} not in columns")
            if e["order_by"] not in e["columns"]:
                errors.append(f"{s['source']}.{e['name']}: order_by {e['order_by']} not in columns")
            pii, restricted = set(e.get("pii", [])), set(e.get("restricted", []))
            if pii - set(e["columns"]):
                errors.append(f"{s['source']}.{e['name']}: pii columns not in columns {sorted(pii - set(e['columns']))}")
            if restricted - pii:
                errors.append(f"{s['source']}.{e['name']}: restricted columns must also be pii {sorted(restricted - pii)}")
            restricted_by_table[f"{s['source']}/{e['name']}"] = restricted

    for ent, rules in dq["rules"].items():
        if ent not in entities:
            errors.append(f"dq: unknown entity {ent}")
            continue
        for r in rules:
            if r.get("column") and r["column"] not in entities[ent]:
                errors.append(f"dq {ent}: unknown column {r['column']}")
            if r["rule"] == "foreign_key" and r["ref_entity"] not in entities:
                errors.append(f"dq {ent}: unknown ref_entity {r['ref_entity']}")
            if r["severity"] not in ("error", "warn"):
                errors.append(f"dq {ent}: bad severity {r['severity']}")

    families = {f["key"]: f for f in tenant["workspace_families"]}
    item_perms = {"Read", "ReadData", "ReadAll", "Monitor", "Audit"}
    for sh in tenant.get("item_shares", []):
        fam = families.get(sh["workspace_family"])
        if not fam:
            errors.append(f"item_share {sh['item']}: unknown workspace family {sh['workspace_family']}")
            continue
        declared = {i["name"] for kind in (fam.get("items") or {}).values() for i in kind}
        if sh["item"] not in declared:
            errors.append(f"item_share {sh['item']}: item not declared in family {fam['key']}")
        for g in sh["grant_to"]:
            if g not in groups:
                errors.append(f"item_share {sh['item']}: unknown group {g}")
            if any(g in (fam["roles"].get(e) or {}) for e in tenant["environments"]):
                errors.append(f"item_share {sh['item']}: {g} already has a workspace role in {fam['key']} - item share is redundant")
        if "Read" not in sh["permissions"] or set(sh["permissions"]) - item_perms:
            errors.append(f"item_share {sh['item']}: permissions must include Read and only use {sorted(item_perms)}")

    known_tables = {k.replace(".", "/"): v for k, v in entities.items()} | {k: set(v) for k, v in CORE_TABLES.items()}
    # core/patron is built from ticket buyers and donors, so it carries their restricted columns.
    restricted_by_table["core/patron"] = ((restricted_by_table.get("ticketing/customers", set())
                                           | restricted_by_table.get("fundraising/donors", set()))
                                          & set(CORE_TABLES["core/patron"]))
    for role in tenant["onelake_security"]["roles"]:
        for m in role["members"]:
            if m not in groups:
                errors.append(f"onelake role {role['name']}: unknown group {m}")
        for t in role["tables"]:
            if t not in known_tables:
                errors.append(f"onelake role {role['name']}: unknown table {t}")
        for t, cols in (role.get("allow_columns") or {}).items():
            missing = set(cols) - set(known_tables.get(t, []))
            if missing:
                errors.append(f"onelake role {role['name']}: {t} unknown columns {sorted(missing)}")
        # Restricted columns must never be readable through a OneLake role.
        allowed = role.get("allow_columns") or {}
        for t in role["tables"]:
            restricted = restricted_by_table.get(t, set())
            if not restricted:
                continue
            if t not in allowed:
                errors.append(f"onelake role {role['name']}: {t} has restricted columns {sorted(restricted)} - "
                              "list the allowed columns in allow_columns")
            elif restricted & set(allowed[t]):
                errors.append(f"onelake role {role['name']}: {t} exposes restricted columns {sorted(restricted & set(allowed[t]))}")

    errors += tenant_data_in_repo()
    if unfilled(tenant):
        warnings.append(f"tenant.yaml: no value yet for {', '.join(unfilled(tenant))} (add it to .env)")

    for w in warnings:
        print(f"WARN   {w}")
    for e in errors:
        print(f"ERROR  {e}")
    n_ws = len(tenant["workspace_families"]) * len(tenant["environments"])
    print(f"{'FAILED' if errors else 'OK'}: {len(groups)} groups, {len(domains)} domains, {n_ws} workspaces, "
          f"{len(entities)} entities, {sum(len(r) for r in dq['rules'].values())} DQ rules")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
