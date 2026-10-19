"""Grab the frames of dev_server.py's camera: B2's camera as the viewer (site/) renders it.

    pip install playwright
    python firmware/bay-node/web/grab_camera.py            # -> firmware/bay-node/web/camera/*.jpg

Serves site/ on a local port and opens it headless in the installed Chrome
(--channel msedge for Edge) with ?debug, which exposes window.__viewer.  For
each resolution it builds a CameraPreview (site/camera.js: the lens, the
sensor's noise and auto exposure, the JPEG) on its own canvas, lets the auto
exposure settle, then grabs frames 300 ms apart while the GIGA's LVGL screen
plays its music demo, with the LED light on, then off.  Nothing in site/ is
changed.  Writes camera/b2-<w>x<h>-<on|off>-<n>.jpg; the sensor noise is
most of their size, hence fewer frames and a lower quality at 1600x1200.
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parent
SITE = WEB.parents[2] / "site"

GRAB = """
async ({w, h, n, gap, warm, q}) => {
  const v = window.__viewer;
  const cam = await import('./camera.js');
  const rig = v.rigs.B2;
  const raw = document.createElement('canvas');
  raw.width = w; raw.height = h;
  const p = new cam.CameraPreview(v.renderer, raw, {size: [w, h]});
  p.setRig(rig);
  const out = document.createElement('canvas');
  out.width = w; out.height = h;
  const o = out.getContext('2d');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let now = performance.now();
  const shots = {};
  for (const light of [1, 0]) {
    rig.target = light;
    cam.setRigLight(rig, light);
    cam.refreshRigShadows(rig);
    for (let i = 0; i < warm; i++) { now += 250; p.update(v.scene, now); await sleep(30); }
    shots[light ? 'on' : 'off'] = [];
    for (let i = 0; i < n; i++) {
      await sleep(gap);
      now += gap;
      p.update(v.scene, now);
      o.setTransform(1, 0, 0, -1, 0, h);   // the preview's rows are bottom-up
      o.drawImage(raw, 0, 0);
      shots[light ? 'on' : 'off'].push(out.toDataURL('image/jpeg', q).split(',')[1]);
    }
  }
  for (const k of ['rtScene', 'rtSensor', 'rtYcc', 'rtDct', 'rtOut', 'rtProbe']) p[k].dispose();
  rig.target = 1;
  return shots;
}
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", default="chrome", help="browser: chrome, msedge or chromium")
    ap.add_argument("--out", type=Path, default=WEB / "camera")
    ap.add_argument("--frames", type=int, default=4, help="frames per light state at 640x480")
    ap.add_argument("--big-frames", type=int, default=1, help="frames per light state at 1600x1200")
    ap.add_argument("--quality", type=float, default=0.75)
    ap.add_argument("--big-quality", type=float, default=0.6)
    ap.add_argument("--settle", type=float, default=12, help="seconds after LVGL is up (past its intro)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                            functools.partial(QuietHandler, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?view=camera&camlight=1&debug&hideui"

    with sync_playwright() as pw:
        # WebGL without a GPU; one small page per resolution, the 1600x1200 targets need the memory
        browser = pw.chromium.launch(channel=args.channel,
                                     args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for (w, h), n, q in (((640, 480), args.frames, args.quality),
                             ((1600, 1200), args.big_frames, args.big_quality)):
            page = browser.new_page(viewport={"width": 480, "height": 360})
            page.goto(url)
            page.wait_for_function("window.__viewer && window.__viewer.rigs.B2", timeout=120000)
            page.wait_for_function("window.__viewer.lvgl()", timeout=120000)
            page.wait_for_timeout(args.settle * 1000)
            shots = page.evaluate(GRAB, {"w": w, "h": h, "n": n, "gap": 300, "warm": 24, "q": q})
            for light, frames in shots.items():
                for i, b64 in enumerate(frames):
                    path = args.out / f"b2-{w}x{h}-{light}-{i}.jpg"
                    path.write_bytes(base64.b64decode(b64))
                    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")
            page.close()
        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
