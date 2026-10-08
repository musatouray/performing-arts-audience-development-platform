"""Step 06: copy config/sources.yaml and dq_rules.yaml to lh_bronze/Files/config as JSON.

Your .env values are filled into the uploaded copy, so the notebooks see the real
server and storage names while the file on GitHub only has ${NAME} placeholders.

The notebooks read these files to know which tables to load and which checks to run,
so run this again whenever you change either file.

The source data itself no longer goes through this script. Each source reaches
Fabric its own way (see docs/adr/ADR-003-ingestion-tools.md).

OneLake works with the standard Azure Data Lake (ADLS Gen2) API, so the
regular Azure storage library is used for the upload.
Run: uv run python scripts/06_upload_config.py --env dev [--dry-run]
"""

import json

import yaml
from lib.config import sources_config, unfilled
from lib.fabric import CONFIG, Client, banner, credential, find_item, require_workspace, std_args, ws_name

ONELAKE = "https://onelake.dfs.fabric.microsoft.com"


def main():
    ap = std_args(__doc__)
    ap.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    a = ap.parse_args()

    from azure.storage.filedatalake import DataLakeServiceClient

    c = Client()
    ws = require_workspace(c, ws_name("dataplatform", a.env))
    lh = find_item(c, ws["id"], "lh_bronze", "Lakehouse")
    fs = DataLakeServiceClient(ONELAKE, credential=credential()).get_file_system_client(ws["id"])
    banner(f"Upload config -> {ws['displayName']}/lh_bronze/Files/config")

    configs = {"sources": sources_config(), "dq_rules": yaml.safe_load((CONFIG / "dq_rules.yaml").read_text())}
    if unfilled(configs["sources"]):
        print(f"  note: no value yet for {', '.join(unfilled(configs['sources']))} (add to .env and run again)")
    for name, cfg in configs.items():
        payload = json.dumps(cfg, indent=2).encode()
        print(f"  config/{name}.json")
        if not a.dry_run:
            fs.get_file_client(f"{lh['id']}/Files/config/{name}.json").upload_data(payload, overwrite=True)


if __name__ == "__main__":
    main()
