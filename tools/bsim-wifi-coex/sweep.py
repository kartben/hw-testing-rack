#!/usr/bin/env python3
"""The rack's Wi-Fi against BLE between two DUTs, on BabbleSim (README.md).

Runs inside the zephyr-build container after setup.sh.  A scenario is one
simulation of RUN_S seconds:

  device 0, 1   the two DUTs (app/, Zephyr's own BLE stack on nrf52_bsim):
                the central and the peripheral, 0 dBm
  device 2      the AP's data traffic \\ one WLAN activity model: the rack's
  3 ..          the nodes' traffic   / BSS, one port per transmitter
  last          the AP's beacons (a second, periodic model at the basic rate)

on the multiatt channel (a fixed attenuation per path, from GEOMETRY) and
the BLE_simple modem (SNR from the interferer's spectrum overlapping the
BLE channel, BER from the SNR).  It is a model: compare scenarios with each
other, not with the field.

usage: sweep.py <plan> [--jobs N] [--out results.csv]
plans: smoke, flow, disc, afh, racks, extra, all
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import os
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BSIM = Path(os.environ.get("BSIM_OUT_PATH", "/ws/tools/bsim"))
BIN = BSIM / "bin"
RUN_S = 60  # app/src/main.c's RUN_S

# --- Geometry and radio assumptions -----------------------------------------
# Free space at 2.45 GHz: 40.2 dB at 1 m, 20 dB a decade, plus LOSSES for the
# small PCB antennas, their mismatch and the printed enclosure.
LOSSES = 5.0
DUT_TO_DUT_M = 0.10       # two sub-slots of one drawer
AP_M = 2.0                # the rack's AP, 1-3 m away
AP_DBM = 20.0             # a typical AP
# config/rack.yaml: columns 165.8 mm apart, rows 165 mm; rows A and B today
# (8 bays), C and D once fitted (16).  The DUTs sit in B2's drawer, the inner
# bay with the camera; a node's antenna is NODE_TO_DRAWER_M from its own
# drawer.  The hub sits in the base cell under row A, column 1.
COL_PITCH, ROW_PITCH = 0.1658, 0.165
DUT_BAY = (1, 1)          # (row, column) from 0: B2
HUB_CELL = (-1, 0)
NODE_TO_DRAWER_M = 0.10

CHANNELS = {1: 2412, 6: 2437, 11: 2462}


def fspl(d_m: float) -> float:
    return 20 * math.log10(d_m) + 40.2 + LOSSES


def distance(cell: tuple[int, int]) -> float:
    dy = ROW_PITCH * (cell[0] - DUT_BAY[0])
    dx = COL_PITCH * (cell[1] - DUT_BAY[1])
    return math.sqrt(dx * dx + dy * dy + NODE_TO_DRAWER_M ** 2)


def node_distances(n: int) -> list[float]:
    """The first n nodes' distances to the DUTs, their own bay's first: rows A
    and B for up to 8 nodes, A to D beyond."""
    rows = 2 if n <= 8 else 4
    return sorted(distance((r, c)) for r in range(rows) for c in range(4))[:n]


# --- Wi-Fi traffic profiles ------------------------------------------------------
# The BSS's channel occupancy (WLAN_actmod: one semi-Markov active/idle process)
# and who transmits: (args, AP share, hub share, active nodes); the active
# nodes, nearest first, share the rest.
PROFILES = {
    # beacons apart: mDNS, ARP, keep-alives, status polls: ~1-2 %
    "idle": (["-DataRate=54", "-PacketMinSize=100", "-PacketMaxSize=400", "-pr=0",
              "-sigma=8", "-kappa=0"], 0.45, 0.05, 16),
    # the DUTs' own node being flashed: AP downlink, its TCP ACKs; ~10 %
    "flash": (["-ConfigSet=10"], 0.8, 0.0, 1),
    # stress: 4 flashes and 2 cameras streaming up at once; ~50 % asked
    "stress": (["-ConfigSet=50"], 0.45, 0.05, 6),
    # stress for 16 bays: 8 flashes and 4 cameras, ~70 % of the air (ns-3)
    "stress16": (["-ConfigSet=100"], 0.45, 0.05, 12),
}

# The settings compared per rack size: today's, and the proposals (8 dBm,
# channel 11, 11b off; the AP stays 2 m away)
SETTINGS = {
    "today": {"node_dbm": 11, "ch": 6, "beacons": "11b"},
    "proposed": {"node_dbm": 8, "ch": 11, "beacons": "ofdm"},
}

# Beacons every 102.4 ms, ~300 bytes, at the basic rate: 1 Mbps (11b rates
# on, long preamble 192 us) or 6 Mbps (11b off, OFDM preamble 20 us = 120 bits)
BEACONS = {
    "11b": ["-DataRate=1", "-PacketHeaderSize=192"],
    "ofdm": ["-DataRate=6", "-PacketHeaderSize=120"],
}
BEACON_COMMON = ["-PacketMinSize=300", "-PacketMaxSize=300", "-SIFS=0", "-ACKBe=0", "-ACKT=0",
                 "-AveCWSize=67.5", "-pr=0", "-sigma=1e9", "-kappa=0", "-BeaconPeriod=0.1024"]


def scenario_cmds(sim: str, s: dict) -> tuple[list[list[str]], int]:
    """The processes of one scenario, and the number of phy devices."""
    seed = s["seed"]
    test = "central_disc" if s["mode"] == "disc" else "central"
    central = [str(BIN / "bs_coex_dut"), f"-s={sim}", "-d=0", f"-testid={test}", f"-rs={seed}"]
    if s.get("afh"):
        central += ["-argstest", f"wifi_ch={s['ch']}"]
    procs = [central,
             [str(BIN / "bs_coex_dut"), f"-s={sim}", "-d=1", "-testid=peripheral",
              f"-rs={seed + 1}"]]
    dut_m = s.get("dut_m", DUT_TO_DUT_M)
    paths = {(0, 1): fspl(dut_m), (1, 0): fspl(dut_m)}
    ndev = 2

    if s["profile"] != "none":
        # Ports: 0 the AP (device 2), 1 the hub (3), 2.. the nodes (4..)
        args, ap_share, hub_share, active = PROFILES[s["profile"]]
        n = s["nodes"]
        active = min(n, active)
        dists = node_distances(n)
        if "own_m" in s:
            # The DUTs on their own node's drawer floor, a few cm from it
            dists[0] = s["own_m"]
        shares = [ap_share, hub_share] + [(1 - ap_share - hub_share) / active] * active
        shares += [0.0] * (n - active)
        ports = ["-d=2"] + [f"-d{k}={2 + k}" for k in range(1, n + 2)]
        probs = [f"-pp{k}={p:.6f}" for k, p in enumerate(shares)]
        # The model has one power: a station's lower power is extra attenuation
        sta_extra = AP_DBM - s["node_dbm"]
        for dut in (0, 1):
            paths[(2, dut)] = fspl(s.get("ap_m", AP_M))
            paths[(3, dut)] = fspl(distance(HUB_CELL)) + sta_extra
            for k, d in enumerate(dists):
                paths[(4 + k, dut)] = fspl(d) + sta_extra
        procs.append([str(BIN / "bs_device_2G4_WLAN_actmod"), f"-s={sim}",
                      f"-nports={n + 2}"] + ports + probs +
                     [f"-power={AP_DBM}", f"-channel={s['ch']}", f"-rs={seed + 2}"] + args)
        ndev = 4 + n
        beacon_dev = ndev
        for dut in (0, 1):
            paths[(beacon_dev, dut)] = fspl(s.get("ap_m", AP_M))
        procs.append([str(BIN / "bs_device_2G4_WLAN_actmod"), f"-s={sim}", f"-d={beacon_dev}",
                      f"-power={AP_DBM}", f"-channel={s['ch']}", f"-rs={seed + 3}"] +
                     BEACONS[s["beacons"]] + BEACON_COMMON)
        ndev += 1

    matrix = Path(f"/tmp/{sim}.matrix")
    matrix.write_text("".join(f"{tx} {rx} : {att:.1f}\n" for (tx, rx), att in paths.items()))
    phy = [str(BIN / "bs_2G4_phy_v1"), f"-s={sim}", f"-D={ndev}", f"-sim_length={RUN_S}e6",
           "-defmodem=BLE_simple", "-channel=multiatt", "-argschannel", f"-file={matrix}",
           "-at=100", "-argsmain"]
    return [phy] + procs, ndev


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


ADV_MHZ = (2.0, 26.0, 80.0)  # 2402, 2426, 2480 MHz: the advertising channels


def phy_stats(sim: str, ndev: int) -> dict:
    """On the data channels: the share of each DUT's packets the other did not
    receive intact (lost: no sync, or a CRC or header error), and the CRC and
    header errors alone among the receptions that synced, leaving out those
    the receiver cut short itself (the link layer closing a connection event).
    And the Wi-Fi's measured share of the air."""
    res = BSIM / "results" / sim
    sent = got = synced = bad = 0
    for dut in (0, 1):
        for row in read_csv(res / f"d_2G4_{dut:02d}.Tx.csv"):
            sent += float(row["center_freq"]) not in ADV_MHZ
        for row in read_csv(res / f"d_2G4_{dut:02d}.Rx.csv"):
            if float(row["center_freq"]) in ADV_MHZ or row["tx_nbr"] != str(1 - dut):
                continue
            if row["status"] == "1":      # P2G4_RXSTATUS_OK
                got += 1
                synced += 1
            elif row["status"] in ("2", "3") and int(row["abort_time"]) >= int(row["payload_end"]):
                bad += 1                  # packet content (CRC) or header error
                synced += 1
    wifi_us = 0
    for dev in range(2, ndev):
        for row in read_csv(res / f"d_2G4_{dev:02d}.Tx.csv"):
            wifi_us += int(row["end_time"]) - int(row["start_time"])
    return {"ll_sent": sent, "ll_ok": got,
            "loss_pct": round(100 * (1 - got / sent), 2) if sent else "",
            "crc_pct": round(100 * bad / synced, 2) if synced else "",
            "wifi_duty_pct": round(100 * wifi_us / (RUN_S * 1e6), 2)}


def run(s: dict) -> dict:
    sim = f"coex_{s['id']}_{random.randrange(1 << 30)}"
    cmds, ndev = scenario_cmds(sim, s)
    procs = [subprocess.Popen(c, cwd=BIN, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True) for c in cmds]
    outs = [p.communicate(timeout=1800)[0] for p in procs]
    row = dict(s)
    for line in outs[1].splitlines():
        m = re.search(r"RESULT (\w+) (.*)", line)
        if m:
            row.update({k: v for k, v in (kv.split("=") for kv in m.group(2).split())})
    row.update(phy_stats(sim, ndev))
    if "rx_bytes" not in row and "cycles" not in row:
        row["error"] = outs[1][-300:].replace("\n", " | ")
    subprocess.run(["rm", "-rf", str(BSIM / "results" / sim), f"/tmp/{sim}.matrix"])
    return row


def plan(name: str) -> list[dict]:
    base = {"seed": 1, "nodes": 8, "node_dbm": 11, "beacons": "11b", "afh": False, "ch": 6}
    out = []

    def add(**kw):
        out.append({**base, **kw, "id": len(out)})

    if name in ("smoke", "all", "flow"):
        add(mode="flow", profile="none")
    if name == "smoke":
        add(mode="flow", profile="stress", ch=6, node_dbm=20)
        add(mode="disc", profile="stress", ch=6, node_dbm=20)
        return out
    if name in ("flow", "all"):
        for ch, dbm in itertools.product(CHANNELS, (20, 11, 8, 5, 2)):
            add(mode="flow", profile="flash", ch=ch, node_dbm=dbm)
            for prof, nodes in itertools.product(("idle", "stress"), (1, 4, 8, 16)):
                add(mode="flow", profile=prof, ch=ch, node_dbm=dbm, nodes=nodes)
    if name in ("disc", "all"):
        add(mode="disc", profile="none")
        for ch, prof, beacons, dbm in itertools.product(CHANNELS, ("idle", "flash", "stress"),
                                                        ("11b", "ofdm"), (11, 2)):
            add(mode="disc", profile=prof, ch=ch, beacons=beacons, node_dbm=dbm)
    if name in ("afh", "all"):
        for mode, ch, prof in itertools.product(("flow", "disc"), CHANNELS, ("flash", "stress")):
            add(mode=mode, profile=prof, ch=ch, afh=True)
    if name in ("racks", "all"):
        # Per rack size, every node on the air: 8 bays (32 DUTs) and 16 (64),
        # today's settings and the proposals, with and without the host's
        # channel classification; then the BLE pair in one bay (one DATA x4:
        # 4 cm apart, their node 3 cm away)
        add(mode="flow", profile="none")
        add(mode="flow", profile="none", dut_m=0.04)
        add(mode="disc", profile="none")
        for bays, setting, prof in itertools.product((8, 16), SETTINGS,
                                                     ("idle", "flash", "stress")):
            if prof == "stress" and bays == 16:
                prof = "stress16"
            kw = dict(SETTINGS[setting], profile=prof, nodes=bays, bays=bays, setting=setting)
            add(mode="flow", **kw)
            add(mode="flow", afh=True, **kw)
            add(mode="disc", **kw)
        for setting, prof, afh in itertools.product(SETTINGS, ("idle", "flash", "stress16"),
                                                    (False, True)):
            add(mode="flow", **SETTINGS[setting], profile=prof, nodes=16, bays=16,
                setting=setting, afh=afh, dut_m=0.04, own_m=0.03)
    if name in ("extra", "all"):
        # OFDM beacons on the flow; the AP 1 or 3 m away; other seeds (the noise)
        for ch in (6, 11):
            add(mode="flow", profile="idle", ch=ch, beacons="ofdm", nodes=16)
        for prof, ap_m in itertools.product(("flash", "stress"), (1.0, 3.0)):
            add(mode="flow", profile=prof, ap_m=ap_m)
        for ch, seed in itertools.product(CHANNELS, (2, 3)):
            add(mode="flow", profile="stress", ch=ch, seed=seed)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plan", choices=["smoke", "flow", "disc", "afh", "racks", "extra", "all"])
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", type=Path, default=Path("results.csv"))
    args = ap.parse_args()

    scenarios = plan(args.plan)
    print(f"{len(scenarios)} scenarios, {args.jobs} at a time", flush=True)
    rows = []
    with ThreadPoolExecutor(args.jobs) as pool:
        for i, row in enumerate(pool.map(run, scenarios), start=1):
            rows.append(row)
            print(f"[{i}/{len(scenarios)}] {row['mode']} {row['profile']} ch{row['ch']} "
                  f"{row['node_dbm']} dBm n{row['nodes']} {row['beacons']} afh={row['afh']}: "
                  f"tput={row.get('throughput_Bps', '-')} avg={row.get('avg_ms', '-')} "
                  f"loss={row.get('loss_pct', '-')}% duty={row.get('wifi_duty_pct')}% "
                  f"{row.get('error', '')}", flush=True)
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in scenarios[0], k))
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
