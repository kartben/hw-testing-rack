"""The Zephyr board targets the node's page suggests, from mechanical/boards/boards.yaml.

    python board_targets.py <boards.yaml> <out.json>      # the build does this (CMakeLists.txt)

Every family's `zephyr:` gives its target (`platform`, or several `choices`), its west runner and
the VID:PID its debug USB shows (`usb`); `targets:` overrides the runner and the ids per target (a
XIAO is an ESP32 one day and an nRF52840 the next).  The page offers the targets whose ids match the
device in a slot ("1366:*": any J-Link), and completes the others by name.

    {"targets": [{"board": "nucleo_g474re", "runner": "stm32cubeprogrammer",
                  "family": "ST NUCLEO-64 (MB1136 / MB1367)", "usb": ["0483:374b", ...]}, ...],
     "runners": ["bossac", "dfu-util", "esp32", ...]}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

USB_ID = re.compile(r"[0-9a-f]{4}:([0-9a-f]{4}|\*)$")
# west runners a rack's boards use, offered even when no target defaults to them
RUNNERS = ("bossac", "dfu-util", "esp32", "jlink", "linkserver", "nrfutil", "openocd", "pyocd",
           "stm32cubeprogrammer", "uf2")


def targets(boards_yaml: Path) -> dict:
    boards = (yaml.safe_load(boards_yaml.read_text(encoding="utf-8")) or {}).get("boards", {})
    out: list[dict] = []
    runners = set(RUNNERS)
    for family, info in boards.items():
        z = info.get("zephyr") or {}
        names = ([z["platform"]] if z.get("platform") else []) + list(z.get("choices", []))
        per = z.get("targets") or {}
        for board in names:
            own = per.get(board) or {}
            runner = own.get("runner", z.get("runner"))
            usb = [str(u).lower() for u in own.get("usb", z.get("usb", []))]
            for u in usb:
                if not USB_ID.match(u):
                    raise SystemExit(f"{boards_yaml}: {family}: {board}: usb {u!r} is not vvvv:pppp (or vvvv:*)")
            out.append({"board": board, "runner": runner, "family": info.get("name", family), "usb": usb})
            if runner:
                runners.add(runner)
    return {"targets": out, "runners": sorted(runners)}


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(json.dumps(targets(src), separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
