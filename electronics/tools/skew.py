"""The USB links' skew, from the .kicad_pcb text alone (no pcbnew: it runs in CI).

A link is what the signal sees from one chip's pin to the far pin: the hub's pair on to its USBLC6, then the ESD's
crossover on to the receptacle, one line a side made of several nets.  A board lists its High-Speed links in
design.py, b.pcb["skew"] = {"tol": mm, "links": {name: ((P nets…), (N nets…)), …}, "loose": {name: (mm, why)}}:
the two sides of each run the same length within `tol` (tracks only; a via joins the two faces at the same place
on both lines), or within its own figure where "loose" gives one, with its reason.
tools/tests/test_pair_skew.py checks every board that lists them.

    python skew.py BOARD.kicad_pcb P[+P…],N[+N…] …      → one line per link: its sides' lengths and their skew
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


def skews(path, links) -> list[tuple[str, float, float, list[str]]]:
    """(name, P side's length, N side's length, nets with no track) for each link ({name: (P nets, N nets)})."""
    got = lengths(path)
    out = []
    for name, (ps, ns) in links.items():
        missing = [x for x in (*ps, *ns) if not got.get(_net_of(x))]
        out.append((name, sum(got.get(_net_of(x), 0.0) for x in ps), sum(got.get(_net_of(x), 0.0) for x in ns),
                    missing))
    return out


if __name__ == "__main__":
    spec = {a: tuple(tuple(s.split("+")) for s in a.split(",")) for a in sys.argv[2:]}
    for name, lp, ln, missing in skews(Path(sys.argv[1]), spec):
        print(f"{name:40s} {lp:8.3f} {ln:8.3f}  skew {lp - ln:+.3f} mm{'  no track: ' + ' '.join(missing) if missing else ''}")
