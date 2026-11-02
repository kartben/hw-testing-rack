"""The USB pairs' skew, from the .kicad_pcb text alone (no pcbnew: it runs in CI).

A board lists its High-Speed pairs in design.py, b.pcb["match"] = {"tol": mm, "pairs": [(P net, N net), …]}: the
two lines of each must run the same length within `tol` (tracks only; a via joins the two faces at the same
place on both lines).  tools/tests/test_pair_skew.py checks every board that lists them.

    python skew.py BOARD.kicad_pcb P,N [P,N …]      → one line per pair: its lines' lengths and their skew
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from flowthru import Board, _net_of


def lengths(path) -> dict[str, float]:
    """Each net's track length (mm), by its name without the sheet path."""
    out: dict[str, float] = {}
    for kind, net, _, g in Board(path).items:
        if kind == "seg":
            out[_net_of(net)] = out.get(_net_of(net), 0.0) + math.dist(g[:2], g[2:4])
    return out


def skews(path, pairs) -> list[tuple[str, str, float, float]]:
    """(P net, N net, P length, N length) for each pair; a net with no track has length 0."""
    got = lengths(path)
    return [(p, n, got.get(_net_of(p), 0.0), got.get(_net_of(n), 0.0)) for p, n in pairs]


if __name__ == "__main__":
    for p, n, lp, ln in skews(Path(sys.argv[1]), [a.split(",") for a in sys.argv[2:]]):
        print(f"{p:24s} {lp:8.3f}  {n:24s} {ln:8.3f}  skew {lp - ln:+.3f} mm")
