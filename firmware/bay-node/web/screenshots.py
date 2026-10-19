"""Render the screenshots of the bay node web page used in the docs.

    pip install playwright pillow
    python firmware/bay-node/web/screenshots.py            # -> docs/img/web-ui-*.png

Runs dev_server.py in-process (simulated node), opens the page in the
installed Chrome (--channel msedge for Edge, or --channel chromium after
`playwright install chromium`), lets it collect a minute of current samples
for the sparkline (and of the fake board's log for the console), then
shoots each state, access control last (web-ui-access*.png): the node
claimed with a key made up for the run, rules, a CI job holding the bay.
The browser and server plumbing is firmware/common/web/shots.py.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB.parents[1] / "common" / "web"))

import dev_server  # noqa: E402
from shots import DESKTOP, DOCS_IMG, POLL_S, Shots  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", default="chrome", help="browser: chrome, msedge or chromium")
    ap.add_argument("--warmup", type=float, default=60, help="seconds of samples before shooting")
    ap.add_argument("--out", type=Path, default=DOCS_IMG)
    args = ap.parse_args()

    # This machine plays the admin's laptop of the examples
    dev_server.PEER_OVERRIDE["127.0.0.1"] = "192.168.1.23"

    with Shots(dev_server.serve(0), args.out, args.channel) as s:
        poke, shoot, base = s.poke, s.shoot, s.base
        dark = s.page("dark", DESKTOP)
        light = s.page("light", DESKTOP)
        print(f"collecting {args.warmup:.0f} s of samples...")
        time.sleep(args.warmup)

        # Use the board's shell from the web console
        dark.click(".term")
        dark.keyboard.type("sensor get")
        dark.keyboard.press("Enter")
        time.sleep(1)
        shoot(dark, "web-ui-console", ".console")

        # The camera's live view (the simulated camera: B2 in the viewer, grab_camera.py)
        dark.click("#cam-live")
        time.sleep(3 * POLL_S)
        shoot(dark, "web-ui-camera", "#cam-card", palette=True)

        # Its settings, tuned a little (a cloudy-day white balance, brighter), then back to auto
        dev_server.camera.configure({"white_balance": "cloudy", "brightness": 1, "saturation": -1})
        dark.set_viewport_size({"width": DESKTOP["width"], "height": 1000})   # the whole popover
        dark.click("#cam-fmt")
        dark.wait_for_selector("#cam-settings:popover-open")
        time.sleep(1.5)
        shoot(dark, "web-ui-camera-settings", "#cam-settings")
        dark.click("#cam-settings [data-camset=reset]")
        dark.keyboard.press("Escape")
        dark.evaluate("document.activeElement.blur()")   # no focus ring left on the picture pill
        dark.set_viewport_size(DESKTOP)

        poke("/dev/attach")             # a USB/IP client is attached: green
        shoot(dark, "web-ui-dark", palette=True)
        dark.click("#cam-live")         # stopped: the next shots list no camera client
        time.sleep(5)                   # the Access card polls every 4 s
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
            s.shoot_span(page, name, ".wrap > header", ".cards")

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



if __name__ == "__main__":
    main()
