"""Reads the config files and fills in your tenant-specific values from .env.

The config files are committed to GitHub, so they never hold anything that belongs
to one tenant: no server names, storage accounts, SharePoint sites or IDs. Instead
they say ${NAME}, or ${NAME:-default} for optional values, and the real value lives
in .env at the repo root, which Git ignores. Values already set in the environment
win, so CI (GitHub secrets) or a terminal session can override .env.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
_VAR = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def load_env(path: Path = ROOT / ".env"):
    """Load KEY=value lines from .env into the environment (skips blanks and # comments)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _fill(value):
    if isinstance(value, str):
        def value_for(m):
            if m.group(1) in os.environ:
                return os.environ[m.group(1)]
            return m.group(2) if m.group(2) is not None else m.group(0)     # default, or leave it unfilled
        return _VAR.sub(value_for, value)
    if isinstance(value, dict):
        return {k: _fill(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v) for v in value]
    return value


def unfilled(value) -> list[str]:
    """Names of ${...} variables that still have no value."""
    return sorted({m.group(1) for m in _VAR.finditer(yaml.safe_dump(value))})


def load_config(name: str) -> dict:
    """config/<name>.yaml with the .env values filled in."""
    load_env()
    return _fill(yaml.safe_load((CONFIG / f"{name}.yaml").read_text(encoding="utf-8")))


def sources_config() -> dict:
    return load_config("sources")


def tenant_config() -> dict:
    return load_config("tenant")
