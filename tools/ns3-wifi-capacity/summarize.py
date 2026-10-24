#!/usr/bin/env python3
"""Average the sweeps' runs over their seeds: results/summary.md (tables) and results/summary.json.

    python3 summarize.py [results-dir]

A run with a "dead" station (every MPDU of one station fails while it and the AP hold the
association: an ns-3 corner case of some seeds, docs/wifi-capacity-ns3.md) is left out and counted.
"""

import csv
import json
import math
import statistics
import sys
from pathlib import Path

NUM = ("nearLoss", "dutCm", "rackChannel", "dutChannel", "neighbourChannel", "spectrum", "ampduMpdus", "bays", "active", "cams", "txPower", "apDist", "beacon11b", "seed", "assoc", "stas", "dead")

# per sweep: the axes that vary, then the columns shown (CSV name, title, digits)
COMMON = [("airtime_pct", "airtime %", 0), ("usbip_goodput_kBps", "USB/IP kB/s per node", 0),
          ("usbip_goodput_min_kBps", "worst node kB/s", 0), ("total_MBps", "total MB/s", 2),
          ("ping_p95_ms", "ping p95 ms", 1), ("http_p50_ms", "HTTP p50 ms", 1),
          ("http_p95_ms", "HTTP p95 ms", 0), ("http_p99_ms", "HTTP p99 ms", 0),
          ("mac_retx_pct", "MAC retx %", 0), ("tcp_retx_pct", "TCP retx %", 2)]
CAM = [("cam_fps", "camera fps", 1), ("cam_skipped_pct", "frames skipped %", 0),
       ("cam_kBps", "camera kB/s", 0)]
SWEEPS = {
    "idle": (["bays", "beacon11b"], [("airtime_pct", "airtime %", 1), ("ping_p95_ms", "ping p95 ms", 2),
                                     ("http_p95_ms", "HTTP p95 ms", 1)]),
    "ci_n": (["active"], COMMON),
    "ci_up": (["active"], COMMON),
    "ci_cam": (["active", "cams"], [c for c in COMMON if c[0] not in ("ping_p95_ms", "tcp_retx_pct")] + CAM),
    "cam_only": (["cams"], [("airtime_pct", "airtime %", 0), ("http_p95_ms", "HTTP p95 ms", 0)] + CAM),
    "power_dist": (["active", "txPower", "apDist"], [("airtime_pct", "airtime %", 0),
                   ("usbip_goodput_kBps", "USB/IP kB/s per node", 0), ("http_p95_ms", "HTTP p95 ms", 0),
                   ("mac_retx_pct", "MAC retx %", 0)]),
    "beacon": (["active", "beacon11b"], [("airtime_pct", "airtime %", 0),
               ("usbip_goodput_kBps", "USB/IP kB/s per node", 0), ("http_p95_ms", "HTTP p95 ms", 0)]),
    "harsh": (["active", "beacon11b"], COMMON + [("dut_goodput_Mbps", "DUT Wi-Fi Mbit/s", 1),
              ("neighbour_goodput_Mbps", "neighbour Mbit/s", 1)]),
    "channel": (["active", "rackChannel", "dutChannel", "neighbourChannel"], COMMON + [
                ("dut_goodput_Mbps", "DUT Wi-Fi Mbit/s", 1), ("neighbour_goodput_Mbps", "neighbour Mbit/s", 1)]),
    "channel_near": (["active", "rackChannel", "dutChannel", "neighbourChannel"], COMMON + [
                     ("dut_goodput_Mbps", "DUT Wi-Fi Mbit/s", 1), ("neighbour_goodput_Mbps", "neighbour Mbit/s", 1)]),
    "ci_near": (["active"], COMMON),
    "racks": (["bays", "scenario", "cams", "active"], COMMON + CAM + [
              ("dut_goodput_Mbps", "DUT Wi-Fi Mbit/s", 1), ("neighbour_goodput_Mbps", "neighbour Mbit/s", 1)]),
    "wifi6": (["bays", "standard", "heMcs", "cams", "active"], [
              ("airtime_pct", "airtime %", 0), ("usbip_goodput_kBps", "USB/IP kB/s per node", 0),
              ("usbip_goodput_min_kBps", "worst node kB/s", 0), ("http_p95_ms", "HTTP p95 ms", 0),
              ("mac_retx_pct", "MAC retx %", 0), ("ul_tb_pct", "UL in TB PPDUs %", 0),
              ("cam_fps", "camera fps", 1)]),
    "ampdu": (["active", "ampduMpdus"], [("airtime_pct", "airtime %", 0),
              ("usbip_goodput_kBps", "USB/IP kB/s per node", 0), ("total_MBps", "total MB/s", 2),
              ("http_p95_ms", "HTTP p95 ms", 0), ("mac_retx_pct", "MAC retx %", 0)]),
}


def num(v):
    try:
        return float(v)
    except ValueError:
        return math.nan


def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            row = {k: (v if k in ("scenario", "usbipDir", "standard", "ru_dl", "ru_ul") else num(v)) for k, v in r.items()}
            row["ping_loss_pct"] = max(0.0, row["ping_loss_pct"]) if not math.isnan(row["ping_loss_pct"]) else math.nan
            g, a = row["usbip_goodput_kBps"], row["active"]
            row["total_MBps"] = g * a / 1e3 if not math.isnan(g) else math.nan
            rows.append(row)
    return rows


def mean(vals):
    vals = [v for v in vals if not math.isnan(v)]
    return statistics.mean(vals) if vals else math.nan


def fmt(v, digits):
    if isinstance(v, float) and math.isnan(v):
        return "–"
    return f"{v:.{digits}f}"


def summarise(name, rows, axes, cols):
    groups = {}
    dropped = {}
    for r in rows:
        key = tuple(r.get(a, math.nan) for a in axes)
        if r["dead"] > 0:
            dropped[key] = dropped.get(key, 0) + 1
            continue
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(set(groups) | set(dropped)):
        rs = groups.get(key, [])
        rec = dict(zip(axes, key))
        rec["runs"] = len(rs)
        rec["dropped"] = dropped.get(key, 0)
        for c, _, _ in cols:
            rec[c] = mean([r[c] for r in rs])
        out.append(rec)
    head = axes + [t for _, t, _ in cols] + ["runs"]
    lines = [f"### {name}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for rec in out:
        cells = [fmt(rec[a], 0 if a != "apDist" else 0) if isinstance(rec[a], float) else str(rec[a])
                 for a in axes]
        cells += [fmt(rec[c], d) for c, _, d in cols]
        cells.append(f"{rec['runs']}" + (f" (+{rec['dropped']} dropped)" if rec["dropped"] else ""))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n", out


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "results"
    md = ["# ns-3 rack Wi-Fi sweeps: means over seeds", ""]
    js = {}
    for name, (axes, cols) in SWEEPS.items():
        p = d / f"{name}.csv"
        if not p.exists():
            continue
        rows = load(p)
        text, out = summarise(name, rows, axes, cols)
        md.append(text)
        js[name] = out
    (d / "summary.md").write_text("\n".join(md))
    (d / "summary.json").write_text(json.dumps(js, indent=1, default=lambda x: None))
    print("\n".join(md))


if __name__ == "__main__":
    main()
