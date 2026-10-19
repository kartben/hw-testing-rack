#!/usr/bin/env python3
"""Resolve generic passives (R/C by value + package) to JLC *basic* parts.

    python electronics/tools/passives.py            # resolve everything the designs use
    python electronics/tools/passives.py --refresh  # ignore the cache

Results are cached in electronics/lib/passives.json, which the board
descriptions read to fill the LCSC field.  Uses the @jlcpcb/mcp server
(tools/jlc_mcp.py) so stock and basic/extended status are live.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
CACHE = REPO / "electronics" / "lib" / "passives.json"

# what the designs need (kind, value as written in the schematic, package, extra query words)
WANTED = [
    ("C", "100n", "0603", "50V"), ("C", "1u", "0603", "50V"), ("C", "22n", "0603", "50V"),
    ("C", "6.8n", "0603", "50V"), ("C", "39p", "0603", "50V"), ("C", "10u", "0805", "25V"),
    ("C", "22u", "0805", "25V"), ("C", "10u", "1206", "50V"), ("C", "22u", "1206", "25V"), ("C", "1u", "0805", "50V"),
    ("R", "10k", "0603", ""), ("R", "100k", "0603", ""), ("R", "5.1k", "0603", ""), ("R", "4.7k", "0603", ""),
    ("R", "1k", "0603", ""), ("R", "22k", "0603", ""), ("R", "18k", "0603", ""), ("R", "20k", "0603", ""),
    ("R", "162k", "0603", ""), ("R", "53.6k", "0603", ""), ("R", "10.2k", "0603", ""), ("R", "13k", "0603", ""),
    ("R", "523k", "0603", ""), ("R", "84.5k", "0603", ""), ("R", "33", "0603", ""), ("R", "10", "0603", ""),
    ("R", "5.36k", "0603", ""), ("R", "470k", "0603", ""), ("R", "10k", "0805", ""), ("R", "0", "0603", ""),
    ("C", "47p", "0603", "50V"), ("R", "150k", "0603", ""), ("R", "120k", "0603", ""), ("R", "5.6k", "0603", ""),
    ("R", "82k", "0603", ""), ("R", "15k", "0603", ""), ("C", "4.7u", "0805", "25V"),
    ("R", "1M", "0603", ""), ("R", "7.5k", "0603", ""),
    # power hub v0.4
    ("C", "10n", "0603", "50V"), ("C", "4.7n", "0603", "50V"), ("R", "680", "0603", ""), ("R", "330", "0603", ""),
    ("R", "56", "0603", ""),
    # power hub v0.5 (USB-C PD)
    ("R", "6.2k", "0603", ""), ("R", "200", "0603", ""), ("R", "39k", "0603", ""), ("R", "27k", "0603", ""),
    ("R", "47k", "0603", ""),
    # DATA ×4 (USB-C Rp 56k, the hub's 12k bias and 33 pF crystal loads)
    ("R", "56k", "0603", ""), ("R", "12k", "0603", ""), ("C", "33p", "0603", "50V"),
]

UNITS_C = {"p": "pF", "n": "nF", "u": "uF"}


def norm_value(kind: str, v: str) -> str:
    """Schematic value → the way LCSC descriptions write it (e.g. 4.7k → 4.7kΩ, 100n → 100nF)."""
    if kind == "C":
        m = re.fullmatch(r"([\d.]+)([pnu])", v)
        return f"{m.group(1)}{UNITS_C[m.group(2)]}"
    m = re.fullmatch(r"([\d.]+)([kM]?)", v)
    return f"{m.group(1)}{m.group(2)}Ω"


def key(kind, value, package):
    return f"{kind}:{value}:{package}"


def resolve(m, kind, value, package, extra):
    want = norm_value(kind, value)
    q = f"{package} {want} {extra}".strip()
    r = m.tool("component_search", {"query": q, "limit": 12, "basic_only": True, "in_stock": True})
    rows = r.get("results", []) if isinstance(r, dict) else []
    for c in rows:
        desc = c.get("description") or ""
        if c.get("package") != package:
            continue
        if kind == "C" and not re.search(rf"(^|\s){re.escape(want)}\s", desc):
            continue
        if kind == "R" and not re.search(rf"(^|\s){re.escape(want)}(\s|$)", desc):
            continue
        return {"lcsc": c["lcsc_id"], "mpn": c.get("name"), "manufacturer": c.get("manufacturer"),
                "description": desc, "price": c.get("price"), "stock": c.get("stock"), "basic": True}
    return None


def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def lookup(kind: str, value: str, package: str) -> dict | None:
    return load_cache().get(key(kind, value, package))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    from jlc_mcp import Mcp
    cache = {} if a.refresh else load_cache()
    todo = [w for w in WANTED if key(*w[:3]) not in cache]
    if todo:
        m = Mcp()
        try:
            for kind, value, package, extra in todo:
                hit = resolve(m, kind, value, package, extra)
                cache[key(kind, value, package)] = hit
                print(f"{key(kind, value, package):16s} → {hit['lcsc'] + ' ' + hit['mpn'] if hit else 'NOT FOUND (basic)'}")
        finally:
            m.close()
    CACHE.write_text(json.dumps(dict(sorted(cache.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = [k for k, v in cache.items() if not v]
    print(f"{len(cache) - len(missing)} resolved, {len(missing)} without a basic part: {missing}")


if __name__ == "__main__":
    main()
