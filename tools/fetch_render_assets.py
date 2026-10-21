#!/usr/bin/env python3
"""Fetch the third-party assets the photo renders use into render/assets/ (not committed).

    python tools/fetch_render_assets.py

* CC0 textures from Poly Haven (oak desk, plaster wall);
* official 3D models of some dev boards, published by their makers without login
  (see docs/boards-3d.md for licences and for boards you have to fetch yourself): a STEP, or
  for a board published as a PCB design only (the Nordic DKs) its Altium PcbDoc, which
  tools/board_models.py turns into a populated model through KiCad (tools/vendor_pcb.py).

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
# board id (mechanical/boards/boards.yaml) → (zip or STEP URL, licence note[, the zip member to keep: by default
# its largest STEP])
BOARD_MODELS = {
    "rpi-pico2": ("https://pip.raspberrypi.com/documents/RP-009061-CA",
                  "Raspberry Pi Pico 2 3D STEP, Raspberry Pi Ltd, MIT licence"),
    "arduino-uno-r4": ("https://docs.arduino.cc/resources/models/ABX00087-step.zip",
                       "Arduino UNO R4 WiFi (ABX00087) STEP, Arduino, CC BY-SA 4.0"),
    "xiao": ("https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip",
             "Seeed Studio XIAO ESP32S3 3D model, Seeed Studio, CC BY-SA 4.0 (the Seeed wiki's licence for its resources)"),
    # the two halves of `giga-r1-display` (tools/board_models.py stacks them)
    "giga-r1-wifi": ("https://docs.arduino.cc/resources/models/ABX00063-step.zip",
                     "Arduino GIGA R1 WiFi (ABX00063) STEP, Arduino, CC BY-SA 4.0"),
    "giga-display-shield": ("https://docs.arduino.cc/resources/models/ASX00039-step.zip",
                            "Arduino GIGA Display Shield (ASX00039) STEP, Arduino, CC BY-SA 4.0"),
    "arduino-nano-matter": ("https://docs.arduino.cc/resources/models/ABX00112-step.zip",
                            "Arduino Nano Matter (ABX00112) STEP, Arduino, CC BY-SA 4.0"),
    # ST's board manufacturing specifications (the board's CAD resources): their STEP, under ST's Open
    # Platform License Agreement (published for this rack's testing of ST boards, see docs/boards-3d.md)
    "nucleo-64": ("https://www.st.com/resource/en/board_manufacturing_specification/mb1367_manufacturing.zip",
                  "ST NUCLEO-G474RE (MB1367 rev D) STEP, STMicroelectronics, Open Platform License Agreement",
                  "MB1367-G474RE-D01.step"),
    "nucleo-144": ("https://www.st.com/resource/en/board_manufacturing_specification/mb1549-manufacturing.zip",
                   "ST NUCLEO-U575ZI-Q (MB1549 rev C) STEP, STMicroelectronics, Open Platform License Agreement",
                   "MB1549-U575ZIQ-C05.step"),
    # Nordic's DK hardware files: the Altium PCB, its parts' models embedded (tools/vendor_pcb.py)
    "nrf52840-dk": ("https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/"
                    "nrf52840-dk/nrf52840-development-kit---hardware-files-3_0_3.zip",
                    "Nordic nRF52840 DK (PCA10056 3.0.3) hardware files, Nordic Semiconductor ASA, 5-clause Nordic "
                    "licence (BSD-style)", "400236.PcbDoc"),
    "nrf54l15-dk": ("https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/"
                    "nrf54l15-dk/pca10156-nrf54l15-dk-1_0_0.zip",
                    "Nordic nRF54L15 DK (PCA10156 1.0.0) hardware files, Nordic Semiconductor ASA, no licence "
                    "stated", "400708.PcbDoc"),
    # a STEP straight from the maker's repository (git.beagleboard.org's web pages ask a browser check: its API
    # serves the file)
    "beagleplay": ("https://git.beagleboard.org/api/v4/projects/beagleplay%2Fbeagleplay/repository/files/"
                   "Design%2Fbeagleplayv10_a2_board_3D_20221219.stp/raw?ref=main",
                   "BeaglePlay (rev A2) board STEP, Seeed Technology and BeagleBoard.org Foundation, CC BY 4.0"),
    # its PCB design (Altium, imported from the Allegro original): the STEP's PCB painted from it (board_models
    # model.paint: copper, mask, silkscreen through KiCad)
    "beagleplay-design": ("https://git.beagleboard.org/api/v4/projects/beagleplay%2Fbeagleplay/repository/files/"
                          "Design%2FAltium%20Export%2FBEAGLEPLAYV020_220915.PrjPcb%2FBEAGLEPLAYV020_220915.brd.PcbDoc"
                          "/raw?ref=main",
                          "BeaglePlay PCB design (Altium export), Seeed Technology and BeagleBoard.org Foundation, "
                          "CC BY 4.0", "beagleplay-design.PcbDoc"),
    "wio-terminal": ("https://raw.githubusercontent.com/Seeed-Studio/OSHW-WioTerminal/master/"
                     "Design%20Files%20in%20Wio%20Terminal%20Wiki/Wio-Terminal/Wio%20Terminal%203D.stp",
                     "Seeed Wio Terminal STEP (the whole device), Seeed Studio, Apache License 2.0"),
}
# st.com answers only a browser's request
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/141.0.0.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
           "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=BROWSER if "//www.st.com/" in url else {"User-Agent": "hw-testing-rack/1.0"})
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
    """Keep each download as-is under downloads/, extract only the STEP model (largest one, or the named
    member: a STEP or a PcbDoc) and any licence text, by base name, into boards/<board-id>.<its extension>."""
    dl, boards = ASSETS / "downloads", ASSETS / "boards"
    dl.mkdir(parents=True, exist_ok=True)
    boards.mkdir(parents=True, exist_ok=True)
    notes = []
    for bid, (url, note, *member) in BOARD_MODELS.items():
        dst = boards / f"{bid}{Path(member[0]).suffix if member else '.step'}"
        if dst.exists():
            print("have", dst.relative_to(REPO))
            notes.append(f"{bid}: {note} <{url}>")
            continue
        bare = Path(member[0]).suffix if member else ".step"           # a file that isn't a zip: the STEP itself
        raw = next((f for f in (dl / f"{bid}.zip", dl / f"{bid}{bare}") if f.exists()), None)
        if raw is None:
            data = get(url)
            raw = dl / f"{bid}{'.zip' if data[:2] == b'PK' else bare}"
            raw.write_bytes(data)
            print("got ", raw.relative_to(REPO), f"{raw.stat().st_size / 1e6:.1f} MB")
        if raw.suffix != ".zip":
            dst.write_bytes(raw.read_bytes())
            print("    ", raw.name, "→", dst.relative_to(REPO))
            notes.append(f"{bid}: {note} <{url}>")
            continue
        with zipfile.ZipFile(io.BytesIO(raw.read_bytes())) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            steps = [i for i in members if (Path(i.filename).name == member[0] if member else
                                            i.filename.lower().endswith((".step", ".stp")))]
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
