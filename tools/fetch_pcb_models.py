#!/usr/bin/env python3
"""Fetch the 3D models KiCad's library lacks from LCSC / EasyEDA, into an uncommitted cache.

    python tools/fetch_pcb_models.py            # every catalog part whose model is easyeda/<LCSC>.step
    python tools/fetch_pcb_models.py --refresh  # download again

Parts whose vendor model has a clear licence are kept in the repo (electronics/lib/3dmodels,
see its README).  LCSC / EasyEDA models are fetched here instead, on demand, into
electronics/lib/3dmodels/easyeda/ (git-ignored: their redistribution terms are unclear).  The
catalog (electronics/tools/catalog.py, Cat.model) places each one on its KiCad footprint;
tools/kicad.sh <board> --fab then exports it, and tools/pcb_glb.py --check reports any part still
without a body (it falls back to a stand-in, or fails with --strict).

Run it before `tools/kicad.sh <board> --fab` (CI too); it needs network access only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))
CACHE = REPO / "electronics" / "lib" / "3dmodels" / "easyeda"
API = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
STEP = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hw-testing-rack/fetch_pcb_models"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def wanted() -> dict[str, str]:
    """LCSC number → the MPNs that use its model (catalog entries with model easyeda/<LCSC>.step)."""
    import catalog
    out: dict[str, str] = {}
    for c in catalog.CAT.values():
        if c.model and c.model[0].startswith("easyeda/"):
            out.setdefault(Path(c.model[0]).stem, c.mpn)
    return out


def fetch(lcsc: str, refresh: bool = False) -> Path:
    dst = CACHE / f"{lcsc}.step"
    if dst.exists() and not refresh:
        return dst
    comp = json.loads(get(API.format(lcsc=lcsc)))["result"]
    node = None
    for s in comp["packageDetail"]["dataStr"]["shape"]:
        if s.startswith("SVGNODE"):
            node = json.loads(s.split("~", 1)[1])["attrs"]
    if node is None:
        raise SystemExit(f"{lcsc}: EasyEDA has no 3D model for {comp['title']}")
    data = get(STEP.format(uuid=node["uuid"]))
    if not data.startswith(b"ISO-10303-21"):
        raise SystemExit(f"{lcsc}: the download is not a STEP file")
    CACHE.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    meta = {"lcsc": lcsc, "part": comp["title"], "model": node.get("title"), "uuid": node["uuid"],
            "source": STEP.format(uuid=node["uuid"]), "component": API.format(lcsc=lcsc),
            "easyeda_origin": node.get("c_origin"), "easyeda_z": node.get("z"), "easyeda_rotation": node.get("c_rotation"),
            "fetched": datetime.date.today().isoformat(),
            "licence": "LCSC / EasyEDA library model: not redistributed, fetched on demand"}
    dst.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    bad = 0
    for lcsc, mpn in sorted(wanted().items()):
        try:
            p = fetch(lcsc, a.refresh)
            print(f"{lcsc:12s} {mpn:28s} {p.relative_to(REPO)} ({p.stat().st_size // 1024} kB)")
        except Exception as e:          # keep going: the part falls back to a stand-in in the viewer
            print(f"{lcsc:12s} {mpn:28s} FAILED: {e}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
