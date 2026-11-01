"""The layout review's rules, generated from what a board declares (plain Python: no pcbnew).

A board's NETCLASSES (design.py) and b.pcb carry the declarations; eda.py and pcbgen.py apply what these helpers
return, so every board is built and checked with them.  A board that declares none of it gets nothing new.

* Every netclass pattern must match a net of the board (unmatched_patterns): KiCad matches a pattern against the
  whole net name, sheet path included, so a bare "VIN" silently misses a sub-sheet's "/Power/VIN".
* A class's "_min_width" (mm): its tracks at least that wide, a DRC error, but where b.pcb["min_width_except"] says
  (min_width_rules).
* A "Sensitive" class (enables, faults, resets) beside a "USB" class: 3 × the USB track width between them, the
  layout review's spacing between a fast bus and the lines outside it that must not pick up its edges
  (sensitive_rules).
* b.pcb["severities"]: the board's own DRC severities, written into its .kicad_pro (apply_severities).

Keys starting with "_" stay out of the .kicad_pro (eda.write_project).  No track_angle constraint here, ever: KiCad
drops the whole .kicad_dru on it, silently.
"""

from __future__ import annotations

import re

# the classes the spacing rule pairs: the lines that must stay quiet, and the fast buses they keep off
SENSITIVE = "Sensitive"
FAST = ("USB",)
FAST_SPACING = 3            # × the fast class's track width


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


def _mm(v: float) -> str:
    return f"{round(float(v), 4):g}"


def _listed(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def min_width_rules(netclasses, pcb: dict, net_name=lambda n: n) -> str:
    """The classes that declare "_min_width" (mm) keep every track at least that wide, a DRC error: one rule per
    width, the widest last (a net in two classes keeps the wider floor: the last rule that matches wins).
    b.pcb["min_width_except"]: {"courtyards": [references], "nets": [net names], "why": "..."} where the floor
    doesn't hold (a fine-pitch part's fan-out necking down at its pads, a line drawn thinner on purpose); net_name
    turns a design's net name into the board's (Board.pcb_net_name).  A net is excepted as !(A.NetName == '…'):
    the order panel renames that form for each copy (panelize.py)."""
    widths: dict[float, list[str]] = {}
    for nc in netclasses or []:
        if nc.get("_min_width") is not None:
            widths.setdefault(float(nc["_min_width"]), []).append(nc["name"])
    exc = pcb.get("min_width_except") or {}
    unless = "".join(f" && !A.intersectsCourtyard('{r}')" for r in exc.get("courtyards", ()))
    unless += "".join(f" && !(A.NetName == '{net_name(n)}')" for n in exc.get("nets", ()))
    why = f", but {exc['why']}" if exc.get("why") else ""
    out = []
    for w, names in sorted(widths.items()):
        classes = " || ".join(f"A.hasNetclass('{n}')" for n in names)
        out.append(f'\n(rule "{_listed(names)}: {_mm(w)} mm at least{why}"\n'
                   f"\t(severity error)\n"
                   f"\t(condition \"A.Type == 'Track' && ({classes}){unless}\")\n"
                   f"\t(constraint track_width (min {_mm(w)}mm)))\n")
    return "".join(out)


def sensitive_spacing(netclasses) -> list[tuple[str, str, float]]:
    """(the Sensitive class, a fast class, their clearance in mm) for each FAST class a board declares beside a
    Sensitive one: FAST_SPACING × the fast class's track width (its pairs' width if wider)."""
    byname = {nc["name"]: nc for nc in netclasses or []}
    if SENSITIVE not in byname:
        return []
    out = []
    for fast in FAST:
        if fast in byname:
            nc = byname[fast]
            w = max(float(nc.get("track_width", 0)), float(nc.get("diff_pair_width", 0)))
            if w <= 0:
                raise ValueError(f"netclass {fast}: no track_width to keep the {SENSITIVE} class off it by")
            out.append((SENSITIVE, fast, round(FAST_SPACING * w, 4)))
    return out


def sensitive_rules(netclasses) -> str:
    """The Sensitive class kept sensitive_spacing() off each fast class, a DRC error (a clearance rule: KiCad checks
    a pair both ways round, tracks, vias, pads and pours alike)."""
    return "".join(f'\n(rule "{s}: {_mm(c)} mm off {f}, {FAST_SPACING} times its track width"\n'
                   f"\t(severity error)\n"
                   f"\t(condition \"A.hasNetclass('{f}') && B.hasNetclass('{s}')\")\n"
                   f"\t(constraint clearance (min {_mm(c)}mm)))\n" for s, f, c in sensitive_spacing(netclasses))


def class_rules(netclasses, pcb: dict, net_name=lambda n: n) -> str:
    """Every rule the board's netclasses ask for, as .kicad_dru text ("" when they ask for none)."""
    return min_width_rules(netclasses, pcb, net_name) + sensitive_rules(netclasses)


SEVERITIES = ("error", "warning", "ignore")


def apply_severities(rule_severities: dict, severities: dict | None) -> dict:
    """b.pcb["severities"] {KiCad check: error | warning | ignore} into the .kicad_pro's
    board.design_settings.rule_severities, in place: one board's own call on one check, by name, never a
    generator-wide silence.  A check the file doesn't list (KiCad writes every one it knows) or a severity KiCad
    doesn't know is an error: KiCad would skip it without a word."""
    for check, sev in (severities or {}).items():
        if sev not in SEVERITIES:
            raise ValueError(f"DRC severity {check}: {sev!r}, not one of {', '.join(SEVERITIES)}")
        if rule_severities and check not in rule_severities:
            raise ValueError(f"DRC severity {check}: no such KiCad check")
        rule_severities[check] = sev
    return rule_severities
