"""Unit tests for the synthetic data generator (stdlib unittest; also runs under pytest).

Run:  python -m unittest discover -s tests     (or)  uv run pytest
Uses a short date range so the suite runs in a few seconds.
"""

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from data_generator.generate import Generator, State, fiscal_year, main


def read_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class FiscalYearTests(unittest.TestCase):
    def test_fiscal_year_boundaries(self):
        self.assertEqual(fiscal_year(date(2025, 6, 30)), 2025)
        self.assertEqual(fiscal_year(date(2025, 7, 1)), 2026)


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out, cls.state = cls.tmp / "landing", cls.tmp / "state.json"
        main(["full", "--start", "2025-07-01", "--end", "2025-12-31", "--out", str(cls.out), "--state", str(cls.state)])
        main(["incremental", "--days", "2", "--out", str(cls.out), "--state", str(cls.state)])

    def _rows(self, source, entity, load_date, ext="csv"):
        p = self.out / source / entity / f"load_date={load_date}" / f"{entity}.{ext}"
        if ext == "csv":
            return read_csv(p)
        return [json.loads(line) for line in p.read_text().splitlines() if line]

    def test_partitions_and_manifests_exist(self):
        for d in ("2025-12-31", "2026-01-01", "2026-01-02"):
            m = json.loads((self.out / "_manifests" / f"load_date={d}.json").read_text())
            self.assertEqual(len(m["files"]), 14)

    def test_manifest_counts_match_files(self):
        m = json.loads((self.out / "_manifests" / "load_date=2025-12-31.json").read_text())
        orders = next(f for f in m["files"] if f["entity"] == "orders")
        self.assertEqual(orders["rows"], len(self._rows("ticketing", "orders", "2025-12-31")))

    def test_incremental_ids_do_not_collide_with_history(self):
        hist = {r["order_id"] for r in self._rows("ticketing", "orders", "2025-12-31")}
        inc = [r for r in self._rows("ticketing", "orders", "2026-01-01") if r["status"] == "Complete"]
        self.assertTrue(inc, "incremental produced no new orders")
        self.assertFalse(hist & {r["order_id"] for r in inc})

    def test_defects_are_injected(self):
        lines = self._rows("ticketing", "order_lines", "2025-12-31")
        ids = [r["order_line_id"] for r in lines]
        self.assertGreater(len(ids), len(set(ids)), "expected re-sent duplicate order lines")
        custs = self._rows("ticketing", "customers", "2025-12-31")
        self.assertTrue(any(c["email"] == "" for c in custs), "expected missing emails")

    def test_never_oversold(self):
        perfs = {p["performance_id"]: int(p["capacity"]) for p in self._rows("ticketing", "performances", "2025-12-31")}
        sold = {}
        seen = set()
        for r in self._rows("ticketing", "order_lines", "2025-12-31"):
            if r["order_line_id"] in seen or r["performance_id"] not in perfs:
                continue
            seen.add(r["order_line_id"])
            sold[r["performance_id"]] = sold.get(r["performance_id"], 0) + int(r["quantity"])
        self.assertTrue(all(sold[p] <= perfs[p] for p in sold))

    def test_deterministic_for_same_seed(self):
        a = Generator(State(seed=7, start="2025-09-01", end="2025-09-30")).full()[1]
        b = Generator(State(seed=7, start="2025-09-01", end="2025-09-30")).full()[1]
        self.assertEqual(len(a[("ticketing", "orders")]), len(b[("ticketing", "orders")]))
        self.assertEqual(a[("fundraising", "gifts")][:5], b[("fundraising", "gifts")][:5])


if __name__ == "__main__":
    unittest.main()
