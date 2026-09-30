"""Step 06 - Land source extracts + ingestion config into lh_bronze/Files (OneLake DFS API).

Simulates what a Copy activity / SFTP drop / Dataflow would do in production:
  data/landing/<source>/<entity>/load_date=YYYY-MM-DD/*   ->  lh_bronze/Files/landing/...
  data/landing/_manifests/*                               ->  lh_bronze/Files/landing/_manifests/
  config/sources.yaml + dq_rules.yaml (as JSON)          ->  lh_bronze/Files/config/

OneLake speaks the ADLS Gen2 API, so any ADLS tool/SDK works:
  account  https://onelake.dfs.fabric.microsoft.com
  fs       <workspace id>          path  <lakehouse id>/Files/...

Idempotent: files already present with the same size are skipped (use --force to re-upload).
Run: uv run python scripts/06_upload_landing_files.py --env dev [--load-date 2026-09-28] [--dry-run]
"""

import json
from pathlib import Path

import yaml
from lib.fabric import CONFIG, ROOT, Client, banner, credential, find_item, require_workspace, std_args, ws_name

ONELAKE = "https://onelake.dfs.fabric.microsoft.com"


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    ap.add_argument("--landing", type=Path, default=ROOT / "data" / "landing")
    ap.add_argument("--load-date", help="only upload this load_date partition (default: all)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    from azure.storage.filedatalake import DataLakeServiceClient

    c = Client()
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    lh = find_item(c, ws["id"], "lh_bronze", "Lakehouse")
    fs = DataLakeServiceClient(ONELAKE, credential=credential()).get_file_system_client(ws["id"])
    root = f"{lh['id']}/Files"
    banner(f"Upload -> {ws['displayName']}/lh_bronze/Files")

    # 1) config as JSON (notebooks read JSON; no YAML dependency in Spark)
    for name in ("sources", "dq_rules"):
        payload = json.dumps(yaml.safe_load((CONFIG / f"{name}.yaml").read_text()), indent=2).encode()
        target = f"{root}/config/{name}.json"
        print(f"  config/{name}.json")
        if not a.dry_run:
            fs.get_file_client(target).upload_data(payload, overwrite=True)

    # 2) landing partitions
    files = sorted(p for p in a.landing.rglob("*") if p.is_file())
    if a.load_date:
        files = [p for p in files if f"load_date={a.load_date}" in p.as_posix()]
    uploaded = skipped = 0
    for p in files:
        rel = p.relative_to(a.landing).as_posix()
        target = f"{root}/landing/{rel}"
        fc = fs.get_file_client(target)
        if not a.force:
            try:
                if fc.get_file_properties().size == p.stat().st_size:
                    skipped += 1
                    continue
            except Exception:     # noqa: BLE001 - not found -> upload
                pass
        if a.dry_run:
            print(f"   [dry-run] {rel}")
        else:
            fc.upload_data(p.read_bytes(), overwrite=True)
        uploaded += 1
    print(f"\n  uploaded {uploaded} file(s), skipped {skipped} unchanged")


if __name__ == "__main__":
    main()
