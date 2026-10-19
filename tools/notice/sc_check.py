#!/usr/bin/env python3
"""SolidCraft's interference check on check.py's step scenes: real overlaps and screwdrivers'
obstacles, sorted from the expected ones.

    python tools/notice/sc_check.py [step ...]      (default: every <build>/check/*.step)
    -> <build>/check/report.json, and a summary on stdout

inspect.clearance on each scene; the bodies of one part (a board's components) are not paired.
An overlap is expected when it is a fastener in its hole (its centre on the fastener's axis,
within its reach) or a lead's plug in its header (lead vs board); a tool_<screw> body hitting
anything but its own screw is a screwdriver that cannot reach the screw along its axis.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parents[1] / "mechanical" / "build" / "notice"
CHECK = BUILD / "check"
SC = os.environ.get("SOLIDCRAFT") or next(iter(sorted(glob.glob(os.path.expandvars(
    r"%LOCALAPPDATA%\Programs\SolidCraft-*\solidcraft-cli.exe")))), "solidcraft-cli")
MIN_VOLUME = 0.05                       # mm³: below it, contact
STEP_TIMEOUT = 600                      # s per SolidCraft run: past it, the step is reported as not checked
LEADS = ("data_lead", "data_lead_free", "data_lead_stub", "jumper", "feed", "pd_cable")


def base(body: str) -> str:
    return re.sub(r" \(\d+\)$", "", body)


def on_axis(f: dict, c: list[float], reach: float) -> bool:
    """Is c within `reach` of the fastener's axis, between its tip (or an insert's bottom) and its head?"""
    s, a = f["seat"], f["axis"]
    d = [c[i] - s[i] for i in range(3)]
    t = sum(d[i] * a[i] for i in range(3))                 # along the axis, + towards the head
    r = math.sqrt(max(sum(x * x for x in d) - t * t, 0))
    return r <= reach and -(f["depth"] + 1) <= t <= f["head"] + 1


def classify(info: dict, o: dict) -> tuple[str, str]:
    a, b = base(o["a"]), base(o["b"])
    kinds, fast = info["bodies"], info["fasteners"]
    for x, y in ((a, b), (b, a)):
        if x in info["tools"]:
            if y == info["tools"][x]:
                return "skip", ""
            return "tool", f"screwdriver for {info['tools'][x]} hits {y} ({kinds.get(y, '?')})"
    for x, y in ((a, b), (b, a)):
        if x in fast:
            reach = {"insert": 3.3, "w25": 3.3}.get(fast[x]["kind"], 2.0)
            if on_axis(fast[x], o["center"], reach):
                return "expected", f"{x} in {y}"
    if kinds.get(a) in LEADS or kinds.get(b) in LEADS:
        return "lead", f"{a} ({kinds.get(a)}) / {b} ({kinds.get(b)})"
    return "overlap", f"{a} ({kinds.get(a)}) / {b} ({kinds.get(b)})"


def sc(step: str, commands: list[dict], tag: str) -> list:
    """SolidCraft's results for `commands` run on the step's scene."""
    script, out = CHECK / f"_{tag}.json", CHECK / f"{step}_{tag}.json"
    script.write_text(json.dumps({"commands": commands}))
    subprocess.run([SC, "run", str(script), "--in", str(CHECK / f"{step}.step"), "--results", "--json-out", str(out)],
                   check=True, capture_output=True, timeout=STEP_TIMEOUT)
    res = json.load(open(out, encoding="utf-8"))
    return res if isinstance(res, list) else [res]


def check(step: str) -> dict:
    """A part made of several bodies (a board, the chain, a lead) is only paired with the others'
    bodies (`against`): its own bodies touch by design, and their pairs would be most of the work."""
    info = json.load(open(CHECK / f"{step}.json"))
    comps = sc(step, [{"command": "component.list", "params": {"compact": True, "bodies": True}}], "list")[0]["components"]
    groups = {}
    for name in (b for c in comps for b in c["bodies"]):
        groups.setdefault(base(name), []).append(name)
    singles = [g[0] for g in groups.values() if len(g) == 1]
    p = {"min_volume": MIN_VOLUME}
    cmds = [{"command": "inspect.clearance", "params": {**p, "bodies": singles}}]
    for x, g in groups.items():
        if len(g) > 1:
            cmds.append({"command": "inspect.clearance", "params": {
                **p, "bodies": g, "against": [n for y, h in groups.items() if y != x for n in h]}})
    found = {"overlap": [], "lead": [], "tool": [], "expected": 0, "unchecked": []}
    seen = set()
    for r in sc(step, cmds, "sc"):
        found["unchecked"] += r.get("unchecked", [])
        for o in r.get("overlaps", []):
            key = (frozenset((base(o["a"]), base(o["b"]))), tuple(round(v) for v in o["center"]))
            if key in seen:                    # a pair of two multi-body parts comes twice
                continue
            seen.add(key)
            k, what = classify(info, o)
            if k == "expected":
                found["expected"] += 1
            elif k != "skip":
                found[k].append({"what": what, "volume_mm3": round(o["volume_mm3"], 2),
                                 "center": [round(v, 1) for v in o["center"]]})
    return found


def main() -> None:
    steps = sys.argv[1:] or [p.stem for p in sorted(CHECK.glob("*.step"), key=lambda p: p.stat().st_mtime)]   # notice order
    report, first = {}, {}
    for s in steps:
        try:
            f = report[s] = check(s)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            report[s] = {"error": type(e).__name__}
            print(f"{s}: NOT CHECKED ({type(e).__name__})", flush=True)
            continue
        print(f"{s}: {len(f['overlap'])} overlaps, {len(f['tool'])} screwdriver hits, {len(f['lead'])} lead contacts, "
              f"{f['expected']} fasteners in their holes" + (f", {len(f['unchecked'])} unchecked" if f["unchecked"] else ""),
              flush=True)
        for k in ("overlap", "tool", "lead"):
            for x in f[k]:
                first.setdefault((k, x["what"], tuple(round(v) for v in x["center"])), (s, x["volume_mm3"]))
    print("\nEach finding once, with the first step it shows in:")
    for (k, what, c), (s, vol) in sorted(first.items()):
        print(f"  {k}: {what}, {vol} mm³ at {list(c)} (from {s})")
    json.dump(report, open(CHECK / "report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
