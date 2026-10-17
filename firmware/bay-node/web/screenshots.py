"""Render the screenshots of the bay node web page used in the docs.

    pip install playwright
    python firmware/bay-node/web/screenshots.py            # -> docs/img/web-ui-*.png

Runs dev_server.py in-process (simulated node), opens the page in the
installed Chrome (--channel msedge for Edge, or --channel chromium after
`playwright install chromium`), lets it collect a minute of current samples
for the sparkline (and of the fake board's log for the console), then
shoots each state, access control last (web-ui-access*.png): the node
claimed with a key made up for the run, rules, a CI job holding the bay.
"""

from __future__ import annotations

import argparse
import os
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

    # This machine plays the admin's laptop of the examples
    dev_server.PEER_OVERRIDE["127.0.0.1"] = "192.168.1.23"
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

        def shoot(page, name: str, what: str = ".wrap") -> None:
            path = args.out / f"{name}.png"
            page.locator(what).screenshot(path=path, animations="disabled")
            print(f"wrote {path}")

        # Use the board's shell from the web console
        dark.click(".term")
        dark.keyboard.type("sensor get")
        dark.keyboard.press("Enter")
        time.sleep(1)
        shoot(dark, "web-ui-console", ".console")

        poke("/dev/attach")             # a USB/IP client is attached: green
        shoot(dark, "web-ui-dark")
        poke("/dev/attach")             # detached again: device ready, blue
        shoot(light, "web-ui-light")
        poke("/dev/fault")              # over-current trip
        shoot(dark, "web-ui-fault")
        urllib.request.urlopen(base + "/api/power", data=b'{"action": "on"}').read()

        # Access control: claimed, three sources, refused attempts, a CI job holds the bay
        acc, ip = dev_server.access, dev_server.ip_int
        acc.key = os.urandom(32)
        acc.set_rules({"enabled": True, "everyone": ["status"], "sources": [
            {"name": "ben-laptop", "cidr": "192.168.1.23", "allow": ["all"]},
            {"name": "ci-runners", "cidr": "192.168.1.40/30", "allow": ["status", "control", "console", "usbip"]},
            {"name": "prometheus", "cidr": "192.168.1.5", "allow": ["status"]}]})
        for addr, svc, n in (("192.168.1.90", "console", 2), ("192.168.1.77", "control", 5),
                             ("192.168.1.42", "control", 1)):
            for _ in range(n):
                acc.check(svc, ip(addr))
        acc.take(ip("192.168.1.41"), 3600, "twister job 8812")
        poke("/dev/attach")             # the job's USB/IP and RFC 2217 clients
        poke("/dev/rfc2217")
        for page in (dark, light):
            page.evaluate(f"localStorage.setItem('bay-admin-key', '{acc.key.hex()}')")
            page.reload()
        time.sleep(3 * POLL_S)

        def shoot_top(page, name: str) -> None:
            page.evaluate("scrollTo(0, 0)")     # boxes are relative to the viewport
            head, cards = page.locator("header").bounding_box(), page.locator(".cards").bounding_box()
            path = args.out / f"{name}.png"
            page.screenshot(path=path, animations="disabled", full_page=True, clip={
                "x": cards["x"] - 4, "y": head["y"] - 4, "width": cards["width"] + 8,
                "height": cards["y"] + cards["height"] - head["y"] + 8})
            print(f"wrote {path}")

        shoot_top(dark, "web-ui-access")
        dark.set_viewport_size({"width": DESKTOP["width"], "height": 760})
        dark.click("#btn-admin")
        dark.wait_for_selector("#dlg-access[open]")
        time.sleep(0.5)
        shoot(dark, "web-ui-access-rules", "#dlg-access")

        dev_server.PEER_OVERRIDE["127.0.0.1"] = "192.168.1.77"   # another host: read-only
        light.evaluate("localStorage.removeItem('bay-admin-key')")
        light.reload()
        time.sleep(3 * POLL_S)
        shoot_top(light, "web-ui-access-readonly")

        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
