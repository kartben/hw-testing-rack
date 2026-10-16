#!/usr/bin/env python3
"""Fetch the CC0 textures the photo renders use (Poly Haven) into render/assets/ (not committed).

    python tools/fetch_render_assets.py

render/live_photo.py falls back to procedural materials when they are missing.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "render" / "assets" / "polyhaven"
ASSETS = {"wood_table_001": ("Diffuse", "nor_gl", "Rough"), "painted_plaster_wall": ("Diffuse", "nor_gl", "Rough")}
RES = "2k"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hw-testing-rack/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    for asset, maps in ASSETS.items():
        files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
        out = DEST / asset
        out.mkdir(parents=True, exist_ok=True)
        for m in maps:
            info = files[m][RES]["jpg"]
            dst = out / Path(info["url"]).name
            if dst.exists() and dst.stat().st_size == info["size"]:
                print("have", dst.relative_to(REPO))
                continue
            dst.write_bytes(get(info["url"]))
            print("got ", dst.relative_to(REPO), f"{dst.stat().st_size / 1e6:.1f} MB")
    (DEST / "LICENSE.txt").write_text("Textures from https://polyhaven.com, CC0 1.0 (public domain).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
