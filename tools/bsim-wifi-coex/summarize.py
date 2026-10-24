#!/usr/bin/env python3
"""Markdown tables from sweep.py's CSVs (results/*.csv), for docs/wifi-coexistence.md.

usage: summarize.py results/flow.csv [results/disc.csv ...]
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

CHANNELS = ("1", "6", "11")
POWERS = ("20", "11", "8", "5", "2")


def load(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        with Path(p).open(newline="") as f:
            rows += list(csv.DictReader(f))
    return rows


def pick(rows, **kw):
    return [r for r in rows if all(r.get(k) == str(v) for k, v in kw.items())]


def one(rows, **kw):
    found = pick(rows, **kw)
    return found[0] if found else None


def tput_cell(r, base) -> str:
    if r is None or not r.get("throughput_Bps"):
        return "—"
    t = int(r["throughput_Bps"])
    rel = 100 * t / base if base else 0
    extra = []
    if r.get("timeouts") not in ("0", "", None):
        extra.append(f"{r['timeouts']} timeouts")
    return f"{rel:.0f} % ({r['loss_pct']} % lost{', ' + ', '.join(extra) if extra else ''})"


def flow_tables(rows) -> None:
    base = one(rows, mode="flow", profile="none")
    if base is None:
        return
    b = int(base["throughput_Bps"])
    print(f"Baseline, no Wi-Fi: {b / 1000:.0f} kB/s, {base['loss_pct']} % of the packets lost.\n")
    for prof, nodes in (("idle", 16), ("flash", 8), ("stress", 8)):
        sample = one(rows, mode="flow", profile=prof, ch=6, node_dbm=11, nodes=nodes, afh=False)
        duty = sample["wifi_duty_pct"] if sample else "?"
        print(f"**{prof}** ({nodes} nodes, Wi-Fi on the air {duty} % of the time): throughput "
              "against the baseline (link-layer packets lost)\n")
        print("| node TX power | " + " | ".join(f"channel {c}" for c in CHANNELS) + " |")
        print("|---|" + "---|" * len(CHANNELS))
        for p in POWERS:
            cells = [tput_cell(one(rows, mode="flow", profile=prof, ch=c, node_dbm=p,
                                   nodes=nodes, afh=False), b) for c in CHANNELS]
            print(f"| {p} dBm | " + " | ".join(cells) + " |")
        print()
    print("**Nodes on the air** (stress, 11 dBm): throughput against the baseline\n")
    print("| nodes | " + " | ".join(f"channel {c}" for c in CHANNELS) + " |")
    print("|---|" + "---|" * len(CHANNELS))
    for n in (1, 4, 8, 16):
        cells = [tput_cell(one(rows, mode="flow", profile="stress", ch=c, node_dbm=11, nodes=n,
                               afh=False), b) for c in CHANNELS]
        print(f"| {n} | " + " | ".join(cells) + " |")
    print()


def disc_cell(r) -> str:
    if r is None or not r.get("avg_ms"):
        return "—"
    return f"{r['avg_ms']} / {r['p90_ms']} / {r['max_ms']} ms" + \
        (f", {r['failed']} failed" if r.get("failed") not in ("0", "", None) else "")


def disc_tables(rows) -> None:
    base = one(rows, mode="disc", profile="none")
    if base is None:
        return
    print(f"Baseline, no Wi-Fi: {disc_cell(base)} (average / 90th percentile / worst, "
          f"{base['cycles']} connections).\n")
    for dbm in ("11", "2"):
        print(f"**Scan to connected**, nodes at {dbm} dBm: average / p90 / worst\n")
        print("| traffic, beacons | " + " | ".join(f"channel {c}" for c in CHANNELS) + " |")
        print("|---|" + "---|" * len(CHANNELS))
        for prof in ("idle", "flash", "stress"):
            for bea in ("11b", "ofdm"):
                cells = [disc_cell(one(rows, mode="disc", profile=prof, ch=c, beacons=bea,
                                       node_dbm=dbm, afh=False)) for c in CHANNELS]
                print(f"| {prof}, {bea} | " + " | ".join(cells) + " |")
        print()


def afh_table(rows) -> None:
    flows = pick(rows, afh=True)
    if not flows:
        return
    b = one(rows, mode="flow", profile="none")
    b = int(b["throughput_Bps"]) if b else 0
    print("**Host channel classification** (the central marks the data channels under the "
          "Wi-Fi channel bad; 8 nodes at 11 dBm)\n")
    print("| traffic | channel | flow without | flow with | connect without | connect with |")
    print("|---|---|---|---|---|---|")
    for prof in ("flash", "stress"):
        for c in CHANNELS:
            kw = dict(profile=prof, ch=c, node_dbm=11, nodes=8)
            print(f"| {prof} | {c} | {tput_cell(one(rows, mode='flow', afh=False, **kw), b)} | "
                  f"{tput_cell(one(rows, mode='flow', afh=True, **kw), b)} | "
                  f"{disc_cell(one(rows, mode='disc', afh=False, beacons='11b', **kw))} | "
                  f"{disc_cell(one(rows, mode='disc', afh=True, **kw))} |")
    print()


def main() -> None:
    rows = load(sys.argv[1:])
    flow_tables(rows)
    disc_tables(rows)
    afh_table(rows)


if __name__ == "__main__":
    main()
