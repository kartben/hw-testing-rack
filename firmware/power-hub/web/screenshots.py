"""Render the screenshots of the power hub web page used in the docs.

    pip install playwright
    python firmware/power-hub/web/screenshots.py            # -> docs/img/hub-ui-*.png

Runs dev_server.py in-process (a simulated hub: 140 W EPR charger, nine
bays in three rows), opens the page in the installed Chrome (--channel
msedge for Edge), lets it collect samples for the input sparkline, then
shoots: the claim dialog, then as the admin the rack in dark and light, the
charger renegotiating down to 30 W with a row shed, an eFuse fault and a
silent node.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB.parents[1] / "common" / "web"))

import dev_server  # noqa: E402
from shots import DOCS_IMG, POLL_S, Shots  # noqa: E402

TALL = {"width": 1100, "height": 1200}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", default="chrome", help="browser: chrome, msedge or chromium")
    ap.add_argument("--warmup", type=float, default=30, help="seconds of samples before shooting")
    ap.add_argument("--out", type=Path, default=DOCS_IMG)
    args = ap.parse_args()

    with Shots(dev_server.serve(0), args.out, args.channel) as s:
        # The claim: an unclaimed hub, its dialog waiting for a press on BOOT
        claim = s.page("dark", {"width": 1100, "height": 700})
        time.sleep(POLL_S)
        claim.click("#access-pill")
        claim.wait_for_selector("#dlg-claim[open]")
        claim.click("#claim-go")
        claim.wait_for_selector("#claim-wait:not([hidden])")
        time.sleep(1.2)
        s.shoot(claim, "hub-ui-claim", "#dlg-claim")
        s.poke("/dev/boot", wait=2)
        key = claim.inner_text("#claim-new-key")

        # The rest as the admin
        dark, light = s.page("dark", TALL), s.page("light", TALL)
        for page in (dark, light):
            page.evaluate(f"localStorage.setItem('bay-admin-key', '{key}')")
            page.reload()
        print(f"collecting {args.warmup:.0f} s of samples...")
        time.sleep(args.warmup)

        s.shoot(dark, "hub-ui-dark")
        s.shoot(light, "hub-ui-light")

        s.poke("/dev/drop", wait=3 * POLL_S)    # the charger renegotiates to 30 W: row C shed
        s.shoot(dark, "hub-ui-shed")
        s.poke("/dev/restore")

        s.poke("/dev/fault?row=B")              # an eFuse in current limit
        s.poke("/dev/lose?node=0x22")           # C2 goes silent
        s.shoot(light, "hub-ui-fault")


if __name__ == "__main__":
    main()
