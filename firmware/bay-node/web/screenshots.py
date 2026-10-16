"""Render the screenshots of the bay node web page used in the docs.

    pip install playwright
    python firmware/bay-node/web/screenshots.py            # -> docs/img/web-ui-*.png

Runs dev_server.py in-process (simulated node), opens the page in the
installed Chrome (--channel msedge for Edge, or --channel chromium after
`playwright install chromium`), lets it collect a minute of current samples
for the sparkline, then shoots each state.
"""

from __future__ import annotations

import argparse
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

import dev_server

OUT = Path(__file__).resolve().parents[3] / "docs" / "img"
DESKTOP = {"width": 1100, "height": 400}
POLL_S = 2.5   # the page polls /api/status every 2 s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", default="chrome", help="browser: chrome, msedge or chromium")
    ap.add_argument("--warmup", type=float, default=60, help="seconds of samples before shooting")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    server = dev_server.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    args.out.mkdir(parents=True, exist_ok=True)

    def poke(path: str) -> None:
        urllib.request.urlopen(base + path).read()
        time.sleep(POLL_S)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel)

        def open_page(scheme: str, viewport: dict):
            ctx = browser.new_context(color_scheme=scheme, viewport=viewport,
                                      device_scale_factor=2)
            page = ctx.new_page()
            page.goto(base + "/")
            return page

        dark = open_page("dark", DESKTOP)
        light = open_page("light", DESKTOP)
        print(f"collecting {args.warmup:.0f} s of samples...")
        time.sleep(args.warmup)

        def shoot(page, name: str) -> None:
            path = args.out / f"{name}.png"
            page.locator(".wrap").screenshot(path=path, animations="disabled")
            print(f"wrote {path}")

        poke("/dev/attach")             # a USB/IP client is attached: green
        shoot(dark, "web-ui-dark")
        poke("/dev/attach")             # detached again: device ready, blue
        shoot(light, "web-ui-light")
        poke("/dev/fault")              # over-current trip
        shoot(dark, "web-ui-fault")

        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
