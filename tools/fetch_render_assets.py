#!/usr/bin/env python3
"""Fetch the third-party assets the photo renders use into render/assets/ (not committed).

    python tools/fetch_render_assets.py

* CC0 textures from Poly Haven (oak desk, plaster wall);
* official 3D models of some dev boards, published by their makers without login
  (see docs/boards-3d.md for licences and for boards you have to fetch yourself).

render/live_photo.py and tools/assembly_glb.py fall back to procedural materials and
stand-in boards when these are missing.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "render" / "assets"
TEXTURES = {"wood_table_001": ("Diffuse", "nor_gl", "Rough"), "painted_plaster_wall": ("Diffuse", "nor_gl", "Rough")}
RES = "2k"
# board id (mechanical/boards/boards.yaml) → (zip URL, licence note)
BOARD_MODELS = {
    "rpi-pico2": ("https://pip.raspberrypi.com/documents/RP-009061-CA",
                  "Raspberry Pi Pico 2 3D STEP, Raspberry Pi Ltd, MIT licence"),
    "arduino-uno-r4": ("https://docs.arduino.cc/resources/models/ABX00087-step.zip",
                       "Arduino UNO R4 WiFi (ABX00087) STEP, Arduino, CC BY-SA 4.0"),
    "xiao": ("https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-sense-3d_model.zip",
             "Seeed Studio XIAO ESP32S3 Sense 3D model, Seeed Studio (no licence stated: renders only)"),
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hw-testing-rack/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def textures():
    dest = ASSETS / "polyhaven"
    for asset, maps in TEXTURES.items():
        files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
        out = dest / asset
        out.mkdir(parents=True, exist_ok=True)
        for m in maps:
            info = files[m][RES]["jpg"]
            dst = out / Path(info["url"]).name
            if dst.exists() and dst.stat().st_size == info["size"]:
                print("have", dst.relative_to(REPO))
                continue
            dst.write_bytes(get(info["url"]))
            print("got ", dst.relative_to(REPO), f"{dst.stat().st_size / 1e6:.1f} MB")
    (dest / "LICENSE.txt").write_text("Textures from https://polyhaven.com, CC0 1.0 (public domain).\n")


def board_models():
    """Keep each download as-is under downloads/, extract only the STEP model (largest one) and any
    licence text, by base name, into boards/<board-id>.step."""
    dl, boards = ASSETS / "downloads", ASSETS / "boards"
    dl.mkdir(parents=True, exist_ok=True)
    boards.mkdir(parents=True, exist_ok=True)
    notes = []
    for bid, (url, note) in BOARD_MODELS.items():
        dst = boards / f"{bid}.step"
        if dst.exists():
            print("have", dst.relative_to(REPO))
            notes.append(f"{bid}: {note} <{url}>")
            continue
        raw = dl / f"{bid}.zip"
        if not raw.exists():
            raw.write_bytes(get(url))
            print("got ", raw.relative_to(REPO), f"{raw.stat().st_size / 1e6:.1f} MB")
        with zipfile.ZipFile(io.BytesIO(raw.read_bytes())) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            steps = [i for i in members if i.filename.lower().endswith((".step", ".stp"))]
            if not steps:
                print("!!  no STEP in", raw.name, [i.filename for i in members][:10])
                continue
            best = max(steps, key=lambda i: i.file_size)
            dst.write_bytes(z.read(best))
            print("    ", Path(best.filename).name, "→", dst.relative_to(REPO), f"{best.file_size / 1e6:.1f} MB")
            for lic in (i for i in members if Path(i.filename).name.lower().startswith(("license", "licence"))):
                (boards / f"{bid}.{Path(lic.filename).name}").write_bytes(z.read(lic))
        notes.append(f"{bid}: {note} <{url}>")
    (boards / "SOURCES.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")


def main() -> int:
    textures()
    board_models()
    return 0


if __name__ == "__main__":
    sys.exit(main())
