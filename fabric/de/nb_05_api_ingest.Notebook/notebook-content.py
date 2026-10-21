# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e4b5b873-13f4-4335-827c-bf8d757c7554",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "9f9f5fa0-6a89-4f39-987e-240311772371",
# META       "known_lakehouses": [
# META         {
# META           "id": "e4b5b873-13f4-4335-827c-bf8d757c7554"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb_05_api_ingest: pull new data from every REST API source
# 
# Default lakehouse: lh_bronze (the only one it needs: it reads config and writes files, both in Bronze).
# Run by the `pl_daily_load` pipeline before `nb_10_bronze_ingest`, or by hand.
# 
# One notebook for every source in `sources.yaml` with `method: notebook_api`. Today that is
# Tessitura's REST API (contributions, campaigns, funds) and Diese's booking API (rooms, events,
# bookings). Adding another API source is a `sources.yaml` entry, not a new notebook.
# For each source, it:
# 1. Reads the API's index to see which days of data exist.
# 2. Skips days it has already saved.
# 3. Follows each table's pages (page 1 links to page 2, and so on), retrying when the API is busy.
# 4. Saves the records to `Files/landing/<source>/<table>/load_date=D/`, one JSON record per line,
#    plus a manifest with the record counts the API reported.
# 
# nb_10 then loads those files into `lh_bronze.<system>` (for example `lh_bronze.diese`),
# the same way it loads the marketing files. One source failing doesn't stop the others,
# but the notebook still fails at the end, so the pipeline alert goes out.
# 
# The mock APIs are static JSON files on GitHub Pages, with simple paging
# (`count`, `value`, `next_link`). Real APIs need a service login; keep it in
# Azure Key Vault and read it with `notebookutils.credentials.getSecret`.


# PARAMETERS CELL ********************

api_sources = ""        # empty = every API source; "diese_api" = just that one (comma-separated for several)
load_date = ""          # empty = every day not saved yet; "2026-09-28" = just that day
redownload = False      # True = fetch days again even if already saved
api_workers = 4         # tables fetched at the same time; keep low to respect the vendor's rate limits

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb_00_common

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests

wanted = {x.strip() for x in api_sources.split(",") if x.strip()}
api_list = [s for s in load_json_config("sources")["sources"]
            if (s.get("ingestion") or {}).get("method") == "notebook_api" and (not wanted or s["source"] in wanted)]
print("API sources:", [s["source"] for s in api_list])
_local = threading.local()


def get_json(url: str) -> dict:
    """GET with retries. Waits and tries again on 429 (too many requests) and 5xx errors."""
    if not hasattr(_local, "session"):            # one connection pool per thread
        _local.session = requests.Session()
    for attempt in range(6):
        r = _local.session.get(url, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            print(f"   {r.status_code} from API, waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise Exception(f"API still failing after retries: {url}")


def saved_days(landing: str) -> set:
    try:
        return {f.name.split("=")[1].removesuffix(".json") for f in nbu.fs.ls(f"{landing}/_manifests")}
    except Exception:  # noqa: BLE001 - nothing saved yet
        return set()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

def fetch_entity(base_url: str, entity: str, d: str):
    """Follow one table's pages for one day. Pages have to be read in order, because each one
    says where the next one is, so the parallelism is across tables, not across pages."""
    started = now_utc()
    url, records, pages, expected = urljoin(base_url, f"{entity}/{d}/page-1.json"), [], 0, None
    while url:
        body = get_json(url)
        expected = body["count"] if expected is None else expected
        records += body["value"]
        pages += 1
        url = urljoin(url, body["next_link"]) if body.get("next_link") else None
    return entity, records, pages, expected, started


def ingest_api(source: dict) -> int:
    """Fetch every day this source's API has that isn't saved yet. Returns the number of days saved."""
    base_url = source["ingestion"]["api_base_url"].rstrip("/") + "/"
    entities = [e["name"] for e in source["entities"]]
    landing = f"{lakehouse_path(BRONZE)}/Files/landing/{source['source']}"
    # GitHub Pages caches files for a few minutes; the timestamp makes sure we get the latest index.
    index = get_json(urljoin(base_url, f"index.json?t={int(time.time())}"))
    done = set() if redownload else saved_days(landing)
    todo = [d for d in index["load_dates"] if (not load_date or d == load_date) and d not in done]
    print(f"{source['source']}: API has {len(index['load_dates'])} day(s); {len(todo)} to fetch: "
          f"{todo[:5]}{' ...' if len(todo) > 5 else ''}")
    for d in todo:
        manifest = {"load_date": d, "generated_at": now_utc().isoformat(sep=" ", timespec="seconds"), "files": []}
        # The API calls run in parallel; saving and logging stay in this thread.
        with ThreadPoolExecutor(max_workers=api_workers) as pool:
            results = list(pool.map(lambda e: fetch_entity(base_url, e, d), entities))
        for entity, records, pages, expected, started in results:
            if len(records) != expected:
                # Overlapping pages repeat a few records. Bronze keeps them as received; Silver removes duplicates.
                print(f"   note: {entity} {d} returned {len(records):,} records for a count of {expected:,}")
            path = f"{landing}/{entity}/load_date={d}/{entity}.json"
            nbu.fs.put(path, "\n".join(json.dumps(r) for r in records), True)
            manifest["files"].append({"source": system(source), "entity": entity, "rows": len(records), "api_count": expected})
            log_run("nb_05_api_ingest", f"{system(source)}.{entity}", "api", expected, len(records), started=started,
                    message=f"{pages} page(s) for {d}", lakehouse=BRONZE)
        # The manifest goes last, so a day only counts as saved once every table is in.
        nbu.fs.put(f"{landing}/_manifests/load_date={d}.json", json.dumps(manifest, indent=2), True)
    return len(todo)


# Each source on its own: one vendor's API being down shouldn't stop the others from loading.
saved, failed = {}, {}
for src in api_list:
    try:
        saved[src["source"]] = ingest_api(src)
    except Exception as e:  # noqa: BLE001 - recorded, then raised below
        failed[src["source"]] = str(e)[:500]
        log_run("nb_05_api_ingest", system(src), "api", 0, 0, status="Failed", message=str(e), lakehouse=BRONZE)
        print(f"{src['source']} FAILED: {e}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

if failed:
    raise Exception(f"API ingest failed for {sorted(failed)}: {failed}")
nbu.notebook.exit(f"api ok: {saved}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
