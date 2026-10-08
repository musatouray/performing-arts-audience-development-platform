"""Step 10: create the OneLake shortcuts for sources that already live in Azure storage.

Marketing exports are dropped into an ADLS Gen2 container. Instead of copying them,
a shortcut makes the container appear inside lh_bronze as Files/landing/marketing.
nb_10 then reads it like any other landed folder. Nothing is copied or stored twice.

Before running:
  1. Upload data/marketing_adls/ to the container named in config/sources.yaml (marketing-exports).
  2. In Fabric, Settings > Manage connections and gateways > New > Cloud >
     Azure Data Lake Storage Gen2, pointing at the storage account.
  3. Put the account URL and that connection's ID in .env
     (MARKETING_ADLS_ACCOUNT_URL, MARKETING_ADLS_CONNECTION_ID).

The script skips shortcuts that already exist.
Run: uv run python scripts/10_create_shortcuts.py --env dev [--dry-run]
"""

import sys
from urllib.parse import quote

from lib.config import sources_config, unfilled
from lib.fabric import ApiError, Client, banner, credential, find_item, require_workspace, std_args, ws_name

ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
SHORTCUT_PATH = "Files/landing"


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    a = ap.parse_args()

    sources = [s for s in sources_config()["sources"]
               if (s.get("ingestion") or {}).get("method") == "shortcut"]
    c = Client(dry_run=a.dry_run)
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    lh = find_item(c, ws["id"], "lh_bronze", "Lakehouse")
    banner(f"Shortcuts -> {ws['displayName']}/lh_bronze/{SHORTCUT_PATH}")

    # The shortcut has to sit inside an existing folder.
    if not a.dry_run:
        from azure.storage.filedatalake import DataLakeServiceClient
        fs = DataLakeServiceClient(ONELAKE, credential=credential()).get_file_system_client(ws["id"])
        fs.get_directory_client(f"{lh['id']}/{SHORTCUT_PATH}").create_directory()

    for s in sources:
        adls = s["ingestion"]["adls"]
        if unfilled(adls) or not adls.get("connection_id"):
            sys.exit(f"Add MARKETING_ADLS_ACCOUNT_URL and MARKETING_ADLS_CONNECTION_ID to .env first ({s['source']}).")
        base = f"/workspaces/{ws['id']}/items/{lh['id']}/shortcuts"
        try:
            c.get(f"{base}/{quote(SHORTCUT_PATH)}/{s['source']}")
            print(f"  = {SHORTCUT_PATH}/{s['source']} already exists")
            continue
        except ApiError as e:
            if e.status != 404:
                raise
        body = {"path": SHORTCUT_PATH, "name": s["source"],
                "target": {"adlsGen2": {"location": adls["account_url"].rstrip("/"),
                                        "subpath": f"/{adls['container']}",
                                        "connectionId": adls["connection_id"]}}}
        c.post(f"{base}?shortcutConflictPolicy=Abort", body)
        print(f"  + {SHORTCUT_PATH}/{s['source']} -> {adls['account_url']}/{adls['container']}")


if __name__ == "__main__":
    main()
