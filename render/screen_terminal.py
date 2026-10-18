#!/usr/bin/env python3
"""Paint the laptop screen for the photo renders: a terminal running a Zephyr session on the board
that sits in the bay the laptop is wired to (bay B4, classic mode).

    python render/screen_terminal.py            # → render/assets/laptop-screen.png

render/live_photo.py uses render/assets/laptop-screen.png when it exists (any image works,
e.g. a real screenshot), else the bay node's KiCad render.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "render" / "assets" / "laptop-screen.png"
W, H = 1920, 1200
BG, FG, DIM = (24, 25, 33), (214, 218, 228), (120, 126, 140)
GREEN, BLUE, YELLOW, CYAN, RED = (130, 214, 120), (122, 162, 247), (229, 192, 123), (102, 214, 222), (240, 113, 120)

PROMPT = [("dev@bench", GREEN), (":", FG), ("~/zephyrproject", BLUE), ("$ ", FG)]
SESSION = [
    PROMPT + [("west build -p -b nucleo_f411re samples/subsys/shell/shell_module", FG)],
    [("-- west build: generating a build system", DIM)],
    [("-- Zephyr version: 4.2.0 (~/zephyrproject/zephyr), build: v4.2.0", DIM)],
    [("-- Board: nucleo_f411re, qualifiers: stm32f411xe", DIM)],
    [("[187/187] Linking C executable zephyr/zephyr.elf", FG)],
    [("Memory region         Used Size  Region Size  %age Used", FG)],
    [("           FLASH:       58416 B       512 KB     11.14%", FG)],
    [("             RAM:       17032 B       128 KB     12.99%", FG)],
    PROMPT + [("west flash", FG)],
    [("-- west flash: using runner stm32cubeprogrammer", DIM)],
    [("  Download verified successfully", GREEN)],
    PROMPT + [("tio /dev/ttyACM0", FG)],
    [("[tio 14:32:07] tio v3.7", YELLOW)],
    [("[tio 14:32:07] Connected to /dev/ttyACM0", YELLOW)],
    [("*** Booting Zephyr OS build v4.2.0 ***", CYAN)],
    [("", FG)],
    [("uart:~$ ", GREEN), ("kernel version", FG)],
    [("Zephyr version 4.2.0", FG)],
    [("uart:~$ ", GREEN), ("kernel uptime", FG)],
    [("Uptime: 4211 ms", FG)],
    [("uart:~$ ", GREEN), ("device list", FG)],
    [("devices:", FG)],
    [("- rcc@40023800 (READY)", FG)],
    [("- gpio@40020000 (READY)", FG)],
    [("- serial@40004400 (READY)", FG)],
    [("- i2c@40005400 (READY)", FG)],
    [("uart:~$ ", GREEN), ("demo ping", FG)],
    [("pong", FG)],
    [("uart:~$ ", GREEN), ("\u2588", FG)],
]


def font(size, bold=False):
    names = (["consolab.ttf", "CascadiaMono.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc"] if bold else
             ["consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"])
    for n in names:
        for d in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts", ""):
            try:
                return ImageFont.truetype(str(Path(d) / n) if d else n, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def main():
    img = Image.new("RGB", (W, H), (38, 40, 52))           # desktop behind the window
    d = ImageDraw.Draw(img)
    # terminal window with a title bar
    x0, y0, x1, y1 = 40, 40, W - 40, H - 40
    d.rounded_rectangle([x0, y0, x1, y1], 14, fill=BG)
    d.rounded_rectangle([x0, y0, x1, y0 + 52], 14, fill=(36, 38, 48))
    d.rectangle([x0, y0 + 30, x1, y0 + 52], fill=(36, 38, 48))
    for i, c in enumerate(((237, 106, 94), (245, 191, 79), (98, 197, 84))):
        d.ellipse([x0 + 22 + 34 * i, y0 + 16, x0 + 42 + 34 * i, y0 + 36], fill=c)
    d.text(((x0 + x1) / 2, y0 + 26), "tio /dev/ttyACM0 \u2014 bay B4 \u2014 UNO R4 WIFI", font=font(24), fill=DIM,
           anchor="mm")
    f, fb = font(31), font(31, bold=True)
    lh = 37
    y = y0 + 76
    for line in SESSION:
        x = x0 + 28
        for text, col in line:
            fnt = fb if col in (GREEN, CYAN) else f
            d.text((x, y), text, font=fnt, fill=col)
            x += d.textlength(text, font=fnt)
        y += lh
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print("wrote", OUT.relative_to(REPO))


if __name__ == "__main__":
    main()
