"""Tests for the BOM lines of a board and of its assembly variants (electronics/tools/build_board.py › bom_rows).

A variant (b.pcb["variants"]) leaves some references unfitted on the same PCB: they must land on their own
DNP line, and JLC's BOM must drop them, while their fitted twins keep theirs.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))

import build_board  # noqa: E402


def part(ref, value="100n", lcsc="C1525", dnp=False):
    return SimpleNamespace(ref=ref, value=value, footprint="Capacitor_SMD:C_0402_1005Metric", dnp=dnp,
                           fields={"LCSC": lcsc}, in_bom=True, on_board=True, description="")


def board(*parts):
    return SimpleNamespace(parts={p.ref: p for p in parts})


class BomVariants(unittest.TestCase):
    def test_as_drawn(self):
        rows = build_board.bom_rows(board(part("C1"), part("C2"), part("C3")))
        self.assertEqual([(r["Designator"], r["DNP"]) for r in rows], [("C1,C2,C3", "")])

    def test_variant_splits_a_line(self):
        b = board(part("C1"), part("C2"), part("C3"))
        rows = build_board.bom_rows(b, frozenset({"C2"}))
        self.assertEqual(sorted((r["Designator"], r["DNP"]) for r in rows), [("C1,C3", ""), ("C2", "yes")])
        self.assertEqual(build_board.jlc_bom_rows(rows), [["100n", "C1,C3", "C_0402_1005Metric", "C1525"]])

    def test_own_dnp_stays_apart(self):
        # a part DNP by itself never shares (and so never sets) its fitted twins' line
        rows = build_board.bom_rows(board(part("C1", dnp=True), part("C2")))
        self.assertEqual(sorted((r["Designator"], r["DNP"]) for r in rows), [("C1", "yes"), ("C2", "")])

    def test_whole_line_unfitted(self):
        b = board(part("U1", "RP2354B", "C39843328"), part("C1"))
        rows = build_board.bom_rows(b, frozenset({"U1"}))
        self.assertEqual(build_board.jlc_bom_rows(rows), [["100n", "C1", "C_0402_1005Metric", "C1525"]])


if __name__ == "__main__":
    unittest.main()
