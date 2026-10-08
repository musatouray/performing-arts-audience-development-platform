"""Shared helpers for the provisioning scripts: config, sign-in and Fabric API calls.

How the scripts behave:
  * Safe to re-run. Each script looks for an item by name before creating it.
  * Names, roles and domains come from config/tenant.yaml.
  * Long-running Fabric operations are polled until they finish.
  * If Fabric says "too many requests", the script waits and tries again.
  * --dry-run prints what would change without changing anything.

Sign-in order: a service principal (CI), then the Azure CLI (`az login`), then a
browser window. Domain and tenant-settings calls need a Fabric administrator.
"""

from __future__ import annotations

import json
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
GENERATED = CONFIG / ".generated"          # IDs from your tenant; not committed to Git

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"


# ----------------------------------------------------------------------------- config
@lru_cache
def tenant_config() -> dict:
    """tenant.yaml with your .env values filled in (see lib/config.py)."""
    from lib.config import tenant_config as filled_tenant_config
    return filled_tenant_config()


def ws_name(family_key: str, env: str) -> str:
    """Workspace name, for example hh-dataplatform-dev."""
    return f"{tenant_config()['org']['code']}-{family_key}-{env}"


def load_principals() -> dict:
    """Group IDs saved by 00_create_security_groups.py."""
    p = GENERATED / "principals.json"
    if not p.exists():
        sys.exit("principals.json not found - run scripts/00_create_security_groups.py first.")
    return json.loads(p.read_text())


def save_generated(name: str, data: Any):
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / name).write_text(json.dumps(data, indent=2))


# ----------------------------------------------------------------------------- auth
@lru_cache
def _credential():
    from azure.identity import AzureCliCredential, ChainedTokenCredential, EnvironmentCredential, InteractiveBrowserCredential
    return ChainedTokenCredential(EnvironmentCredential(), AzureCliCredential(), InteractiveBrowserCredential())


def credential():
    return _credential()


def token(scope: str) -> str:
    return _credential().get_token(scope).token


# ----------------------------------------------------------------------------- http
class ApiError(RuntimeError):
    def __init__(self, resp: requests.Response):
        self.status = resp.status_code
        try:
            self.body = resp.json()
        except ValueError:
            self.body = {"raw": resp.text}
        self.code = self.body.get("errorCode") or self.body.get("error", {}).get("code", "")
        super().__init__(f"{resp.request.method} {resp.url} -> {resp.status_code} {self.code}: {json.dumps(self.body)[:600]}")


class Client:
    """Small REST client for the Fabric API (default) or Microsoft Graph."""

    def __init__(self, base_url: str = FABRIC_API, scope: str = FABRIC_SCOPE, dry_run: bool = False):
        self.base, self.scope, self.dry_run = base_url, scope, dry_run
        self.s = requests.Session()

    def _headers(self):
        return {"Authorization": f"Bearer {token(self.scope)}", "Content-Type": "application/json"}

    def call(self, method: str, path: str, body: dict | None = None, write: bool | None = None) -> dict:
        """Send a request. In dry-run mode, changes are printed instead of sent."""
        is_write = write if write is not None else method.upper() != "GET"
        url = path if path.startswith("http") else f"{self.base}{path}"
        if self.dry_run and is_write:
            print(f"   [dry-run] {method} {url} {json.dumps(body) if body else ''}")
            return {"id": "00000000-dry-run", "dryRun": True}
        for attempt in range(8):
            r = self.s.request(method, url, headers=self._headers(), json=body, timeout=120)
            if r.status_code == 429:                       # too many requests: wait and retry
                wait = int(r.headers.get("Retry-After", 30))
                print(f"   429 throttled, waiting {wait}s ...")
                time.sleep(wait)
                continue
            if r.status_code == 202 and "Location" in r.headers:   # still running: poll until done
                return self._poll(r)
            if r.status_code >= 400:
                raise ApiError(r)
            return r.json() if r.content else {}
        raise RuntimeError(f"Gave up after retries: {method} {url}")

    def _poll(self, r: requests.Response) -> dict:
        loc = r.headers["Location"]
        while True:
            time.sleep(int(r.headers.get("Retry-After", 5)))
            r = self.s.get(loc, headers=self._headers(), timeout=120)
            if r.status_code >= 400:
                raise ApiError(r)
            body = r.json() if r.content else {}
            status = body.get("status", "Succeeded" if r.status_code == 200 and "status" not in body else "")
            if status in ("Succeeded", "Completed"):
                try:                                        # some operations return the new item at /result
                    res = self.s.get(f"{loc}/result", headers=self._headers(), timeout=120)
                    return res.json() if res.ok and res.content else body
                except requests.RequestException:
                    return body
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"LRO {status}: {json.dumps(body)[:600]}")

    def paged(self, path: str, key: str = "value") -> Iterator[dict]:
        """Return every result, following the "next page" links."""
        url = path
        while url:
            body = self.call("GET", url)
            yield from body.get(key, [])
            url = body.get("continuationUri") or body.get("@odata.nextLink")

    get = lambda self, p: self.call("GET", p)                      # noqa: E731
    post = lambda self, p, b=None: self.call("POST", p, b)         # noqa: E731


# ----------------------------------------------------------------------------- lookups
def find_workspace(c: Client, name: str) -> dict | None:
    return next((w for w in c.paged("/workspaces") if w["displayName"] == name), None)


def require_workspace(c: Client, name: str) -> dict:
    ws = find_workspace(c, name)
    if not ws:
        sys.exit(f"Workspace '{name}' not found - run scripts/02_create_workspaces.py first.")
    return ws


def find_item(c: Client, workspace_id: str, name: str, item_type: str) -> dict | None:
    return next((i for i in c.paged(f"/workspaces/{workspace_id}/items?type={item_type}") if i["displayName"] == name), None)


def pick_capacity(c: Client) -> dict:
    """Find the capacity set in tenant.yaml (by ID, or else by region).
    Stops with a list of capacities if there isn't exactly one match."""
    cfg = tenant_config()["capacity"]
    caps = [x for x in c.paged("/capacities") if x.get("state") == "Active"]
    if cfg.get("capacity_id"):
        matches = [x for x in caps if x["id"] == cfg["capacity_id"]]
    else:
        matches = caps
        if cfg.get("region"):
            want = cfg["region"].replace(" ", "").lower()
            matches = [x for x in matches if x.get("region", "").replace(" ", "").lower() == want]
        if cfg.get("display_name_hint"):
            hint = cfg["display_name_hint"].lower()
            matches = [x for x in matches if hint in x["displayName"].lower()]
    if len(matches) != 1:
        listing = "\n".join(f"   {x['id']}  {x['displayName']:<40} {x.get('sku', ''):<6} {x.get('region', '')}" for x in caps)
        reason = "No capacity matches" if not matches else f"{len(matches)} capacities match"
        sys.exit(f"{reason} tenant.yaml > capacity. Active capacities:\n{listing}\n"
                 "Set FABRIC_CAPACITY_ID in .env (safest) or a unique capacity.region in tenant.yaml.")
    return matches[0]


def banner(title: str):
    print(f"\n=== {title} " + "=" * max(0, 70 - len(title)))


def std_args(description: str):
    import argparse
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, do not call write APIs")
    return ap
