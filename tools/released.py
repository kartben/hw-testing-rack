#!/usr/bin/env python3
"""Board revisions that went to a fab, and the check that keeps them as they were sent.

electronics/released.json lists each revision a fab received: the board, its revision, the date, and the SHA-256 of
its fabrication files (Gerbers, BOM, placement).  While a board still carries a released revision, those files must
be the ones recorded: a change to them is a change to a board that already exists on a bench, so it belongs to a new
revision (docs/electronics.md › Revisions at the fab).

    python tools/released.py                       # check every board against the list
    python tools/released.py --record bay-node --date 2026-11-11 --fab NextPCB --pcbs 5 --assembled 2
                                                   # print the entry of the board as it is, to add to the list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "electronics" / "released.json"
# what a fab is sent, relative to electronics/<board>/
FILES = ("fab/{b}-gerbers.zip", "{b}-bom.csv", "fab/{b}-cpl-jlcpcb.csv")


def digest(path: Path) -> str:
    """SHA-256 of a file; a text file's line ends don't count (git may check a .csv out with CR LF)."""
    data = path.read_bytes()
    if path.suffix == ".csv":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def revision(board: str) -> str:
    """The revision in the board file's title block."""
    text = (ROOT / "electronics" / board / f"{board}.kicad_pcb").read_text(encoding="utf-8")
    m = re.search(r'\(rev "([^"]*)"\)', text)
    if not m:
        raise ValueError(f"{board}: no revision in its title block")
    return m.group(1)


def as_tuple(rev: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", rev))


def entry(board: str, date: str, fab: str, pcbs: int, assembled: int) -> dict:
    """The list entry of a board as it is in the working tree."""
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    folder = ROOT / "electronics" / board
    return {"board": board, "rev": revision(board), "date": date, "fab": fab, "pcbs": pcbs, "assembled": assembled,
            "commit": commit, "files": {f.format(b=board): digest(folder / f.format(b=board)) for f in FILES}}


def findings() -> list[str]:
    """What differs between the released revisions and the boards as they are: nothing, on a healthy tree."""
    out = []
    for rel in json.loads(LIST.read_text(encoding="utf-8"))["releases"]:
        board, rev = rel["board"], rel["rev"]
        now = revision(board)
        if as_tuple(now) < as_tuple(rev):
            out.append(f"{board}: revision {now} is older than v{rev}, which was sent to {rel['fab']} on {rel['date']}")
        if now != rev:
            continue                                   # a later revision: free to change until it is released too
        for name, sha in rel["files"].items():
            path = ROOT / "electronics" / board / name
            if not path.exists():
                out.append(f"{board} v{rev}: {name} is missing")
            elif digest(path) != sha:
                out.append(f"{board} v{rev} was sent to {rel['fab']} on {rel['date']} and is frozen, but {name} "
                           f"changed: give the board a new revision in its design.py before changing it "
                           f"(docs/electronics.md, Revisions at the fab)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", metavar="BOARD", help="print the list entry of this board as it is")
    ap.add_argument("--date", default="")
    ap.add_argument("--fab", default="")
    ap.add_argument("--pcbs", type=int, default=0)
    ap.add_argument("--assembled", type=int, default=0)
    a = ap.parse_args()
    if a.record:
        print(json.dumps(entry(a.record, a.date, a.fab, a.pcbs, a.assembled), indent=2))
        return 0
    found = findings()
    for line in found:
        print(line)
    print(f"released boards: {len(found)} differences")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
