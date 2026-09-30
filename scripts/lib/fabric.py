"""Thin Fabric REST API client + helpers shared by every provisioning script.

Design choices (say these out loud in the interview):
  * Idempotent  - every "create" is get-or-create by display name, so scripts can be re-run safely.
  * Config-driven - names/roles/domains come from config/tenant.yaml, never hard-coded.
  * LRO-aware  - Fabric returns 202 + Location for long-running ops; we poll until done.
  * Throttle-aware - 429 responses honour Retry-After (admin APIs allow ~10-25 req/min).
  * Dry-run   - pass --dry-run to any script to print the plan without calling write APIs.

Auth: service principal from AZURE_* env vars (CI) -> Azure CLI (`az login --allow-no-subscriptions`)
-> interactive browser login. The signed-in user must be a Fabric administrator for the admin
APIs (domains, tenant settings).
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
GENERATED = CONFIG / ".generated"          # tenant-specific IDs (git-ignored)

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"


# ----------------------------------------------------------------------------- config
@lru_cache
def tenant_config() -> dict:
    return yaml.safe_load((CONFIG / "tenant.yaml").read_text(encoding="utf-8"))


def ws_name(family_key: str, env: str) -> str:
    """Workspace naming convention: {org}-{family}-{env}  e.g. hh-dataplatform-dev."""
    return f"{tenant_config()['org']['code']}-{family_key}-{env}"


def load_principals() -> dict:
    """Group key -> {id, name}. Written by 00_create_security_groups.py."""
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
    # Service principal (CI, via AZURE_* env vars) -> Azure CLI (your laptop) -> browser pop-up.
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
    """Minimal REST client for Fabric (base_url=FABRIC_API) or Graph."""

    def __init__(self, base_url: str = FABRIC_API, scope: str = FABRIC_SCOPE, dry_run: bool = False):
        self.base, self.scope, self.dry_run = base_url, scope, dry_run
        self.s = requests.Session()

    def _headers(self):
        return {"Authorization": f"Bearer {token(self.scope)}", "Content-Type": "application/json"}

    def call(self, method: str, path: str, body: dict | None = None, write: bool | None = None) -> dict:
        """Send a request. Writes are skipped (and logged) in dry-run mode."""
        is_write = write if write is not None else method.upper() != "GET"
        url = path if path.startswith("http") else f"{self.base}{path}"
        if self.dry_run and is_write:
            print(f"   [dry-run] {method} {url} {json.dumps(body) if body else ''}")
            return {"id": "00000000-dry-run", "dryRun": True}
        for attempt in range(8):
            r = self.s.request(method, url, headers=self._headers(), json=body, timeout=120)
            if r.status_code == 429:                       # throttled -> honour Retry-After
                wait = int(r.headers.get("Retry-After", 30))
                print(f"   429 throttled, waiting {wait}s ...")
                time.sleep(wait)
                continue
            if r.status_code == 202 and "Location" in r.headers:   # long-running operation
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
                try:                                        # some LROs expose the created item at /result
                    res = self.s.get(f"{loc}/result", headers=self._headers(), timeout=120)
                    return res.json() if res.ok and res.content else body
                except requests.RequestException:
                    return body
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"LRO {status}: {json.dumps(body)[:600]}")

    def paged(self, path: str, key: str = "value") -> Iterator[dict]:
        """Follow continuationUri/continuationToken (Fabric) or @odata.nextLink (Graph)."""
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
    """Resolve the target capacity from tenant.yaml > capacity. Precedence:
    capacity_id (exact) > region (+ optional display_name_hint). Never guesses:
    zero or multiple matches stop the script with the candidate list."""
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
                 "Set capacity.capacity_id (safest) or a unique capacity.region.")
    return matches[0]


def banner(title: str):
    print(f"\n=== {title} " + "=" * max(0, 70 - len(title)))


def std_args(description: str):
    import argparse
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, do not call write APIs")
    return ap
