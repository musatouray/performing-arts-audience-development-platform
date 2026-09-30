"""Convert the reviewable .py notebook sources in src/notebooks into .ipynb for Fabric import.

Source format = "percent" cells (VS Code / Jupytext style):
  # %%                      -> code cell
  # %% [markdown]           -> markdown cell (lines start with "# ")
  # %% tags=["parameters"]  -> code cell tagged as the Fabric PARAMETERS cell (pipeline overrides)
  # MAGIC %run nb_00_common -> magic line (kept as "%run nb_00_common" in the .ipynb)

Output: src/notebooks/ipynb/<name>.ipynb   ->  Fabric workspace > Import > Notebook > From this computer
Run:    uv run python scripts/build_notebooks.py
"""

import json
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "notebooks"
OUT = SRC / "ipynb"


def convert(path: Path) -> dict:
    cells, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^# %%(.*)$", line)
        if m:
            if cur:
                cells.append(cur)
            meta = m.group(1).strip()
            kind = "markdown" if "[markdown]" in meta else "code"
            tags = ["parameters"] if "parameters" in meta else []
            cur = {"cell_type": kind, "metadata": {"tags": tags} if tags else {}, "source": []}
            if kind == "code":
                cur.update(outputs=[], execution_count=None)
            continue
        if cur is None:
            continue
        if cur["cell_type"] == "markdown":
            line = re.sub(r"^# ?", "", line)
        elif line.startswith("# MAGIC "):
            line = line[len("# MAGIC "):]
        cur["source"].append(line + "\n")
    if cur:
        cells.append(cur)
    for c in cells:                                    # trim trailing blank lines
        while c["source"] and not c["source"][-1].strip():
            c["source"].pop()
        if c["source"]:
            c["source"][-1] = c["source"][-1].rstrip("\n")
    return {"cells": [c for c in cells if c["source"]], "nbformat": 4, "nbformat_minor": 5,
            "metadata": {"language_info": {"name": "python"},
                         "kernel_info": {"name": "synapse_pyspark"},
                         "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"}}}


def main():
    OUT.mkdir(exist_ok=True)
    for p in sorted(SRC.glob("nb_*.py")):
        nb = convert(p)
        (OUT / f"{p.stem}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
        print(f"{p.name:<32} -> ipynb/{p.stem}.ipynb ({len(nb['cells'])} cells)")


if __name__ == "__main__":
    main()
