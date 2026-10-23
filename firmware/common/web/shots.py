"""Screenshot plumbing shared by the web pages' screenshots.py scripts.

    with Shots(dev_server.serve(0), out_dir, channel="chrome") as s:
        dark = s.page("dark")
        s.poke("/dev/fault")
        s.shoot(dark, "web-ui-fault")

Runs the page's development server (a simulated board) in this process,
opens the page in the installed Chrome or Edge through Playwright, and
writes element screenshots at 2x.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS_IMG = Path(__file__).resolve().parents[3] / "docs" / "img"
DESKTOP = {"width": 1100, "height": 400}
POLL_S = 2.5   # the pages poll their status every 2 s


def quantise(path: Path, dither: bool = False) -> None:
    """A screenshot cut to 256 colours, in place: every committed shot stays a third of an RGB PNG."""
    from PIL import Image

    Image.open(path).convert("RGB").quantize(
        256, method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE,
    ).save(path, optimize=True)


class Shots:
    def __init__(self, server, out: Path = DOCS_IMG, channel: str = "chrome"):
        self.server = server
        self.out = out
        self.channel = channel
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def __enter__(self) -> "Shots":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.out.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(channel=self.channel)
        return self

    def __exit__(self, *exc) -> None:
        self.browser.close()
        self._pw.stop()
        self.server.shutdown()

    def page(self, scheme: str, viewport: dict | None = None):
        ctx = self.browser.new_context(color_scheme=scheme, viewport=viewport or DESKTOP,
                                       device_scale_factor=2)
        page = ctx.new_page()
        page.goto(self.base + "/")
        return page

    def poke(self, path: str, body: bytes | None = None, wait: float = POLL_S) -> None:
        """GET (or POST body to) a URL of the simulated board, then let the page poll."""
        urllib.request.urlopen(self.base + path, data=body).read()
        time.sleep(wait)

    def shoot(self, page, name: str, what: str = ".wrap", palette: bool = False) -> Path:
        """Every shot is cut to 256 colours (Pillow): a UI's flat colours and text survive it at
        about a third of the size.  palette: dithered as well, for a shot with a camera frame in
        it, whose noise would make a PNG of several MB."""
        path = self.out / f"{name}.png"
        page.locator(what).screenshot(path=path, animations="disabled")
        quantise(path, dither=palette)
        print(f"wrote {path}")
        return path

    def shoot_span(self, page, name: str, top: str, bottom: str) -> Path:
        """From the top of one element to the bottom of another, page coordinates."""
        page.evaluate("scrollTo(0, 0)")     # boxes are relative to the viewport
        head, foot = page.locator(top).bounding_box(), page.locator(bottom).bounding_box()
        path = self.out / f"{name}.png"
        page.screenshot(path=path, animations="disabled", full_page=True, clip={
            "x": foot["x"] - 4, "y": head["y"] - 4, "width": foot["width"] + 8,
            "height": foot["y"] + foot["height"] - head["y"] + 8})
        quantise(path)
        print(f"wrote {path}")
        return path
