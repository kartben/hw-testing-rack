#!/usr/bin/env python3
"""Snapshot of JLC's catalog for every part on the boards' JLC BOMs: tier, stock and price breaks.

    python tools/jlc_parts_snapshot.py

Reads electronics/<board>/fab/<board>-bom-jlcpcb.csv and asks the jlcpcb-parts MCP server
(github.com/hulryung/jlcpcb-skill-mcp, run through its jlc-call.mjs wrapper) for each LCSC number.
Writes electronics/lib/jlc_parts.json, which tools/bom.py reads to price parts at the quantity an
order reaches (JLC_PCB_PRICE's companion).  The server answers from a local snapshot of JLC's catalog
when its live API is down: the file records which.  Where the snapshot has no prices, LCSC's public
product data fills in the price breaks (no account, read only); its stock is LCSC's (`lcsc_stock`), not
JLC's assembly stock (`stock`).  Set JLC_CALL to the wrapper's command line.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOARDS = ("bay-node", "power-hub", "data-port-x4", "data-port-x4-v2", "data-port", "camera-pod")
OUT = REPO / "electronics" / "lib" / "jlc_parts.json"
# the wrapper sits in the server's checkout (it uses the server's node_modules); default: node on PATH and
# the checkout in ~/.local/mcp/jlcpcb-skill-mcp
JLC_CALL = os.environ.get(
    "JLC_CALL",
    "node --no-warnings " + (Path.home() / ".local/mcp/jlcpcb-skill-mcp/jlc-call.mjs").as_posix())


def call(tool: str, args: dict) -> dict:
    out = subprocess.run(shlex.split(JLC_CALL) + [tool, json.dumps(args)], capture_output=True, text=True,
                         encoding="utf-8", timeout=120).stdout
    m = re.search(r"```json\s*(\{.*\})\s*```", out, re.S)
    if not m:
        raise RuntimeError(f"{tool} {args}: no JSON in {out[:300]!r}")
    return json.loads(m.group(1))


LCSC_DETAIL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={lcsc}"


def lcsc_prices(lcsc: str) -> tuple[list[dict], int | None]:
    """Price breaks and stock from LCSC's public product page data (JLC buys its parts there), for
    the parts whose catalog snapshot carries no prices."""
    import time
    import urllib.request
    time.sleep(1.0)
    req = urllib.request.Request(LCSC_DETAIL.format(lcsc=lcsc), headers={"User-Agent": "curl/8.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30)).get("result") or {}
    ladder = d.get("productPriceList") or []
    breaks = [{"qFrom": p["ladder"], "qTo": (n["ladder"] - 1 if n else None), "price": p["usdPrice"]}
              for p, n in zip(ladder, ladder[1:] + [None])]
    return breaks, d.get("stockNumber")


def bom_lines() -> dict[str, list[tuple[str, int, str]]]:
    """board → [(LCSC, quantity per board, comment)] from its JLC BOM."""
    out = {}
    for b in BOARDS:
        rows = csv.DictReader((REPO / "electronics" / b / "fab" / f"{b}-bom-jlcpcb.csv").open(encoding="utf-8"))
        out[b] = [(r["LCSC Part #"], len([d for d in r["Designator"].split(",") if d.strip()]), r["Comment"])
                  for r in rows if r["LCSC Part #"]]
    return out


def main() -> int:
    lines = bom_lines()
    parts = {}
    for lcsc in sorted({l for rows in lines.values() for l, _, _ in rows}):
        try:
            p = call("get_part", {"lcsc": lcsc})
        except Exception as e:                      # not in the catalog snapshot: keep the line, priced by bom.py
            print(f"{lcsc}: {e}", file=sys.stderr)
            parts[lcsc] = {"missing": True}
            continue
        parts[lcsc] = {k: p.get(k) for k in ("mfr", "package", "stock", "tier", "priceBreaks", "category")}
        parts[lcsc]["manufacturer"] = (p.get("attributes") or {}).get("Manufacturer")
        parts[lcsc]["source"] = (p.get("attributes") or {}).get("Data Source", "live")
        if not parts[lcsc]["priceBreaks"]:          # the snapshot has no prices: LCSC's own (JLC buys there)
            try:
                parts[lcsc]["priceBreaks"], parts[lcsc]["lcsc_stock"] = lcsc_prices(lcsc)
                parts[lcsc]["source"] += "; prices from LCSC's product page (live)"
            except Exception as e:
                print(f"{lcsc}: no LCSC prices ({e})", file=sys.stderr)
        print(f"{lcsc:10s} {p.get('tier', '?'):9s} {p.get('stock', 0):>9} {str(p.get('mfr'))[:30]}")
    OUT.write_text(json.dumps({"date": datetime.date.today().isoformat(), "boards": lines, "parts": parts},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(parts)} parts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
