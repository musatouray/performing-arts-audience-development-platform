"""Validate config/*.yaml BEFORE anything touches the tenant (runs in CI on every PR).

Checks referential integrity of the design:
  * every group referenced by domains / workspace roles / OneLake roles is defined
  * domain roles are set on parent domains only (subdomains inherit them)
  * item shares reference declared items/groups and don't duplicate a workspace role
  * every workspace family points at an existing domain; roles exist for every environment
  * only valid Fabric workspace roles are used; PROD grants no Contributor/Member to builders
  * every DQ rule targets a declared entity + column; FK rules reference declared entities
  * every OneLake-secured table exists in sources.yaml (or the core/ identity tables)

Run: uv run python scripts/validate_config.py     (exit code 1 on any error)
"""

import sys
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config"
VALID_ROLES = {"Admin", "Member", "Contributor", "Viewer"}
CORE_TABLES = {"core/patron": ["patron_id", "first_name", "last_name", "email", "phone", "address_line1", "city", "state",
                               "postal_code", "country", "patron_type", "email_opt_in", "first_seen_date", "source_systems",
                               "updated_at"]}


def main() -> int:
    tenant = yaml.safe_load((CONFIG / "tenant.yaml").read_text())
    sources = yaml.safe_load((CONFIG / "sources.yaml").read_text())
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
                    errors.append(f"family {fam['key']}/prod: {g} has {role} - prod must be deploy-only")

    entities = {}
    for s in sources["sources"]:
        for e in s["entities"]:
            entities[f"{s['source']}.{e['name']}"] = set(e["columns"])
            for pk in e["primary_key"]:
                if pk not in e["columns"]:
                    errors.append(f"{s['source']}.{e['name']}: primary key {pk} not in columns")
            if e["order_by"] not in e["columns"]:
                errors.append(f"{s['source']}.{e['name']}: order_by {e['order_by']} not in columns")

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

    for e in errors:
        print(f"ERROR  {e}")
    n_ws = len(tenant["workspace_families"]) * len(tenant["environments"])
    print(f"{'FAILED' if errors else 'OK'}: {len(groups)} groups, {len(domains)} domains, {n_ws} workspaces, "
          f"{len(entities)} entities, {sum(len(r) for r in dq['rules'].values())} DQ rules")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
