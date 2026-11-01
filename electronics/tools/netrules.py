"""The layout review's rules, generated from what a board declares (plain Python: no pcbnew).

A board's NETCLASSES (design.py) and b.pcb carry the declarations; eda.py and pcbgen.py apply what these helpers
return, so every board is built and checked with them.  A board that declares none of it gets nothing new.

* Every netclass pattern must match a net of the board (unmatched_patterns): KiCad matches a pattern against the
  whole net name, sheet path included, so a bare "VIN" silently misses a sub-sheet's "/Power/VIN".
"""

from __future__ import annotations

import re


def kicad_pattern_match(pattern: str, name: str) -> bool:
    """KiCad 10's netclass pattern test: the whole net name, case-sensitive, as a wildcard (* any run, ? one
    character) or as a regular expression.  Measured on 10.0.7 (each pattern alone in a class, the DSN export
    naming the class each net landed in): "*VIN" takes VIN, "/Power/BUCK_EN" and "?Power/BUCK_EN" take
    /Power/BUCK_EN, "PORT[12]_EN" takes PORT1_EN; "BUCK_EN", "UCK_E" and "/power/buck_en" don't take
    /Power/BUCK_EN, nor "*vin" VIN."""
    wild = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    if re.fullmatch(wild, name):
        return True
    try:
        return re.fullmatch(pattern, name) is not None
    except re.error:
        return False


def unmatched_patterns(netclasses, names) -> list[str]:
    """One line per netclass pattern ("_patterns") that matches none of the board's net names, with the
    wildcard that would reach a sub-sheet's net when there is one: such a pattern leaves its nets in Default
    (its widths, its clearance, none of the class's rules) and nothing else says so."""
    names = sorted(set(names))
    out = []
    for nc in netclasses or []:
        for pat in nc.get("_patterns", []):
            if any(kicad_pattern_match(pat, n) for n in names):
                continue
            msg = f"netclass {nc['name']}: pattern {pat!r} matches no net"
            hits = [] if pat.startswith("*") else [n for n in names if kicad_pattern_match("*" + pat, n)]
            if hits:
                msg += (f" (KiCad matches the whole name, sheet path included: {'*' + pat!r} takes "
                        f"{', '.join(hits[:4])}{' ...' if len(hits) > 4 else ''})")
            out.append(msg)
    return out
