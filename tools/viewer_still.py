#!/usr/bin/env python3
"""A still of the 3D viewer (site/) for the documentation: the rack as config/rack.yaml has it today, on the
site's paper colour instead of the viewer's dark page.

    python tools/viewer_still.py docs/img/viewer/b3-drawer-out.jpg "?bay=B3&openbay=1&view=bay"
    python tools/viewer_still.py docs/_static/viewer-dark/rack.jpg "?view=iso" --dark --crop 290,200,1765,1040

The query string is the viewer's own (site/app.js): bay=B3 frames a bay, openbay=1 pulls its drawer out,
open=0..1 pulls every drawer, explode=0..1, xray hides the ladders, view=iso|front|side|rear|bay|dut|camera,
view=custom&eye=x,y,z&look=x,y,z places the camera (millimetres, the rack's frame), camlight=1, preview=B2.
`hideui`, `quality=low` and `debug` are added for you.

--no-display hides the display in the drawers' fronts (the bay node has no connector for one, so a built bay
has none); --bare also hides the development boards, their plates, cables and wires, and the laptop, to show a
bay as it is before a board goes in.

--dark takes the twin for the site's dark theme: save it as docs/_static/viewer-dark/<same name>.jpg and the
page swaps it in (docs/_static/bitbunk.js).  Look at the picture before you use it: the first framing is rarely
the right one.  The viewer's assets must be built (python tools/build.py web); it is served from site/ on a
port of its own for the time of the shot.

Needs Playwright with its Chromium (pip install playwright && playwright install chromium); it renders in
software, so that it runs on a machine without a display.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER, DARK = "#fcfbf8", "#15171b"       # docs/_static/bitbunk.css: --bb-paper in the light and the dark theme

RECOLOUR = """(bg) => {
  const v = window.__viewer;
  if (!v) return false;
  document.body.style.background = bg;
  document.documentElement.style.background = bg;
  v.setQuality('low');
  v.scene.background.set(bg);
  // the viewer's dark floor: only the rack's shadow is kept of it
  v.scene.traverse((o) => {
    if (o.isMesh && o.geometry && o.geometry.type === 'CircleGeometry' && o.geometry.parameters.radius > 1000) {
      o.material = new v.THREE.ShadowMaterial({ opacity: 0.16 });
    }
  });
  if (v.renderFrame) v.renderFrame();
  return true;
}"""


HIDE = """(bare) => {
  const v = window.__viewer;
  const near = (x, y) => Math.abs(x - y) < 0.01;
  v.scene.traverse((o) => {
    const u = o.userData || {};
    const p = (o.isMesh && o.geometry && o.geometry.parameters) || {};
    // the drawer front's display: its lit status screen, its glass, its PCB (tools/webscene.py, rack.json)
    if (near(p.width, 42.72) && near(p.height, 22.7)) o.visible = false;
    if (near(p.width, 52.36) || (near(p.width, 51.0) && near(p.depth, 26.6))) o.visible = false;
    if (bare && (['boards', 'dut', 'laptop', 'usb-pd', 'pc', 'jumper', 'dupont'].includes(u.zone) || u.layer === 'plates')) {
      o.visible = false;
    }
  });
  if (v.renderFrame) v.renderFrame();
}"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", help="the picture to write (.jpg or .png)")
    ap.add_argument("query", help='the viewer\'s query string, e.g. "?bay=B3&openbay=1&view=bay"')
    ap.add_argument("--w", type=int, default=1600)
    ap.add_argument("--h", type=int, default=1000)
    ap.add_argument("--wait", type=int, default=8000, help="milliseconds to let the scene load (default 8000)")
    ap.add_argument("--dark", action="store_true", help="on the dark theme's ground")
    ap.add_argument("--bg", help="another background colour")
    ap.add_argument("--crop", help="left,top,right,bottom in pixels of the shot")
    ap.add_argument("--chromium", help="path of a Chromium to use instead of Playwright's own")
    ap.add_argument("--no-display", action="store_true", help="no display in the drawers' fronts")
    ap.add_argument("--bare", action="store_true", help="no display, and no board, plate, board cable or laptop")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright      # noqa: PLC0415

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:        # one line per asset otherwise
            pass

    handler = functools.partial(Quiet, directory=str(REPO / "site"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    query = a.query if a.query.startswith("?") else "?" + a.query
    for flag in ("hideui", "quality=low", "debug"):
        if flag.split("=")[0] not in query:
            query += ("&" if len(query) > 1 else "") + flag
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=a.chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                          "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": a.w, "height": a.h}, device_scale_factor=1)
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/{query}")
        page.wait_for_timeout(a.wait)
        if not page.evaluate(RECOLOUR, a.bg or (DARK if a.dark else PAPER)):
            raise SystemExit("the viewer did not load: are its assets built? (python tools/build.py web)")
        if a.no_display or a.bare:
            page.evaluate(HIDE, bool(a.bare))
        page.wait_for_timeout(1500)
        clip = None
        if a.crop:
            left, top, right, bottom = (int(x) for x in a.crop.split(","))
            clip = {"x": left, "y": top, "width": right - left, "height": bottom - top}
        kind = {"type": "jpeg", "quality": 88} if out.suffix.lower() in (".jpg", ".jpeg") else {}
        page.screenshot(path=str(out), clip=clip, timeout=240000, **kind)
        browser.close()
    server.shutdown()
    print(out)


if __name__ == "__main__":
    main()
