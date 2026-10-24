#!/usr/bin/env python3
"""The sweeps of docs/wifi-capacity-ns3.md: one line of rack-wifi arguments per run.

    python3 sweep.py ci_n          # scenario 2 against N
    python3 sweep.py all           # every sweep, in order
"""

import itertools
import sys

BASE = {"txPower": 11, "apDist": 2, "beacon11b": 1, "usbipDir": "down", "cams": 0}


def runs(scenario, seeds, **axes):
    keys = list(axes)
    for values in itertools.product(*(axes[k] for k in keys)):
        args = dict(BASE, scenario=scenario, **dict(zip(keys, values)))
        for seed in seeds:
            yield dict(args, seed=seed)


SWEEPS = {
    # scenario 1: background only (polls, scrapes, mDNS, pings, beacons)
    "idle": lambda: runs("idle", (1, 2, 3), bays=(8, 16), beacon11b=(1, 0)),
    # scenario 2: N nodes flashing over USB/IP, with their consoles
    "ci_n": lambda: runs("ci", (1, 2, 3, 4), active=(1, 2, 4, 6, 8, 12, 16)),
    # reads instead of flashing (node -> PC)
    "ci_up": lambda: runs("ci", (1, 2, 3), active=(1, 4, 8, 12, 16), usbipDir=("up",)),
    # scenario 3: CI plus cameras (1, 2, every bay)
    "ci_cam": lambda: itertools.chain(
        runs("ci", (1, 2, 3), active=(1, 4, 8, 16), cams=(1, 2, 3)),
        runs("ci", (1, 2, 3), active=(4, 8), cams=(8,), bays=(8,)),
        runs("ci", (1, 2, 3), active=(16,), cams=(16,))),
    # cameras alone: how many streams one channel takes
    "cam_only": lambda: runs("ci", (1, 2, 3), active=(0,), cams=(1, 2, 4, 8, 12, 16), bays=(16,)),
    # node TX power and AP distance
    "power_dist": lambda: runs("ci", (1, 2, 3), active=(8, 16), txPower=(20, 11, 8), apDist=(1, 2, 3)),
    # 11b beacons and broadcasts against 6 Mbit/s OFDM
    "beacon": lambda: runs("ci", (1, 2, 3), active=(8, 16), beacon11b=(1, 0)),
    # scenario 4: DUT Wi-Fi on the same channel plus a neighbouring BSS
    "harsh": lambda: runs("harsh", (1, 2, 3), active=(1, 4, 8, 16), beacon11b=(1, 0)),
    # the ESP32's block-ack window (ESP32_WIFI_TX/RX_BA_WIN, 6 by default, 32 at most)
    "ampdu": lambda: runs("ci", (1, 2, 3), active=(8, 12, 16), ampduMpdus=(6, 16, 32)),
}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "all"
    if name == "--list":
        print("\n".join(SWEEPS))
        return
    names = list(SWEEPS) if name == "all" else [name]
    for n in names:
        for r in SWEEPS[n]():
            print(" ".join(f"--{k}={v}" for k, v in r.items()))


if __name__ == "__main__":
    main()
