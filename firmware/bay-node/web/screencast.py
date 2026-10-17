"""Record the screencast of the bay node's web serial console used in the docs.

    pip install playwright
    python firmware/bay-node/web/screencast.py --workspace <west workspace>

Runs the real console code on native_sim (tests/console_sim/run.py, in the
Zephyr build image, with a Zephyr shell as the DUT), drives the page in the
installed Chrome (or --channel msedge / chromium), captures it with Chrome's
screencast (crisp frames, unlike a video codec) and encodes an animated WebP
with ffmpeg: docs/img/web-console.webp.

Needs Docker, ffmpeg and a west workspace made from firmware/west.yml (the
repository's parent directory in the documented layout).
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
IMAGE = "ghcr.io/zephyrproject-rtos/zephyr-build:v0.29.4"
CONTAINER = "bay-console-sim"
# Just the Console card (scrolled to the top); the settings panel opens over it
VIEWPORT = {"width": 1100, "height": 520}


def start_simulation(workspace: Path, port: int, image: str) -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    subprocess.run([
        "docker", "run", "-d", "--name", CONTAINER, "--user", "root", "--entrypoint", "bash",
        "-p", f"{port}:80", "-v", f"{workspace.resolve()}:/ws", "-v", f"{REPO}:/repo",
        "-v", "bay-sim-build:/build", image, "-c",
        'git config --global --add safe.directory "*"; '
        "python3 -u /repo/firmware/bay-node/tests/console_sim/run.py",
    ], check=True, capture_output=True)


def wait_for_node(base: str, timeout: float) -> None:
    """The first run builds both programs: allow minutes."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            aux = json.load(urllib.request.urlopen(base + "/api/aux", timeout=2))
            if aux["rx"] > 0:   # the DUT has printed its prompt
                return
        except OSError:
            pass
        time.sleep(3)
    raise SystemExit("the simulated node did not come up (docker logs " + CONTAINER + ")")


def record(base: str, channel: str, frames_dir: Path) -> list[tuple[float, Path]]:
    frames: list[tuple[float, Path]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=channel)
        page = browser.new_page(viewport=VIEWPORT, color_scheme="dark")
        page.goto(base + "/")
        page.wait_for_function("document.getElementById('con-meta').textContent === 'connected'")
        page.evaluate("document.querySelector('.console').scrollIntoView({block: 'start'})")
        page.evaluate("window.scrollBy(0, -12)")
        page.wait_for_timeout(2500)   # next status poll: the client counts are right

        cdp = page.context.new_cdp_session(page)

        def on_frame(params: dict) -> None:
            path = frames_dir / f"{len(frames):05}.png"
            path.write_bytes(base64.b64decode(params["data"]))
            frames.append((params["metadata"]["timestamp"], path))
            cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "png", "everyNthFrame": 1})
        wait = page.wait_for_timeout   # keeps the screencast events flowing

        def type_slowly(text: str) -> None:
            page.keyboard.type(text, delay=90)

        wait(1500)
        page.click(".term")
        type_slowly("help")
        page.keyboard.press("Enter")
        wait(1800)
        type_slowly("kernel ve")       # tab completion by the DUT's shell
        wait(400)
        page.keyboard.press("Tab")
        wait(700)
        page.keyboard.press("Enter")
        wait(1800)

        page.click("button.chip")      # serial settings
        wait(900)
        page.select_option("#f-baud", "921600")
        wait(700)
        page.click("#con-form button[type=submit]")
        wait(1600)

        page.click("button[data-action=reset]")   # the DUT reboots
        wait(3000)
        page.click(".term")
        type_slowly("kernel uptime")
        page.keyboard.press("Enter")
        wait(2500)

        cdp.send("Page.stopScreencast")
        browser.close()
    return frames


def encode(frames: list[tuple[float, Path]], out: Path, width: int) -> None:
    """Variable-rate frames -> constant 12 fps animated WebP."""
    listing = frames[0][1].parent / "frames.txt"
    lines = []
    for (t, path), (t_next, _) in zip(frames, frames[1:] + [(frames[-1][0] + 1.5, None)]):
        lines += [f"file '{path.as_posix()}'", f"duration {max(t_next - t, 0.01):.3f}"]
    lines.append(f"file '{frames[-1][1].as_posix()}'")
    listing.write_text("\n".join(lines) + "\n")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-vf", f"fps=12,scale={width}:-1:flags=lanczos", "-c:v", "libwebp_anim",
        "-preset", "text", "-q:v", "75", "-loop", "0", str(out),
    ], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", type=Path, default=REPO.parent, help="west workspace")
    ap.add_argument("--channel", default="chrome", help="browser: chrome, msedge or chromium")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--width", type=int, default=VIEWPORT["width"], help="width of the WebP")
    ap.add_argument("--out", type=Path, default=REPO / "docs/img/web-console.webp")
    ap.add_argument("--keep", action="store_true", help="leave the simulation running")
    args = ap.parse_args()

    base = f"http://localhost:{args.port}"
    start_simulation(args.workspace, args.port, args.image)
    try:
        wait_for_node(base, timeout=1200)
        with tempfile.TemporaryDirectory() as tmp:
            frames = record(base, args.channel, Path(tmp))
            encode(frames, args.out, args.width)
        print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB, {len(frames)} frames)")
    finally:
        if not args.keep:
            subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)


if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found")
    main()
