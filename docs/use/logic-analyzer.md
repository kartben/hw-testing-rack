# Logic analyzer

A DATA ×4's co-processor runs gusmanb's LogicAnalyzer from its RAM and reads the eight buses A to H, the
lines the Wires card joins to the boards' pins, and the node's MARK line on channel 13.

:::{status} bench
On a XIAO ESP32-S3 stand-in with a Pico 2 in the co-processor's place (2026-11-03 and 04): the image loaded
into RAM by the node, captures relayed to the bay's page and to `bayctl capture`, a UART and an I²C device
decoded. *Capture and reset* and `bayctl capture --reset` ran on the simulated node only; 1-Wire, CAN and a
real SWD target have had no real signal. No DATA ×4 has been on a bench. See
[What exists today](../plan/status.md#status-analyzer).
:::

Needs: a DATA ×4 assembled with its logic, and its buses wired ([Wires between boards](wires.md)); the node's
admin key, once, to load the image; Node 22 or later for `bayctl capture`.

## Load the analyzer image, once

The analyzer's firmware is GPL-3.0 and is not shipped with BitBunk: no download exists, and the lab builds it.
The co-processor (an RP2350B) has no flash, so the image is a RAM build: gusmanb's
[LogicAnalyzer](https://github.com/gusmanb/logicanalyzer) at tag v6.0.0.0, built with

- `BOARD_PICO_2` and `TURBO_MODE 0`,
- `pico_set_binary_type(LogicAnalyzer no_flash)` in place of the release's `copy_to_ram`,
- pico-sdk 2.0.0, the release's, with its VS Code include made `OPTIONAL`;
- with gcc 15, `pioasm` 2.0.0 also needs `-include cstdint`.

The UF2 loads 40,704 bytes from 0x20000000 and clears its 384 KB capture buffer at start. Nothing in the
repository runs this build for you, and the release's own UF2 for the Pico 2 is a flash build, which `bayctl
coproc load` refuses ("not in the RP2350's SRAM").

Store it on the node, with the admin key in `BAYCTL_KEY`
([Access rules and security](access.md)):

```console
$ python tools/bayctl.py coproc load B3 LogicAnalyzer.uf2
$ python tools/bayctl.py coproc status B3
```

The node keeps the image in its own flash and loads it into the co-processor each time the co-processor
shows up in its USB bootloader (2e8a:000f), at each power-up; on the stand-in a load took 60 ms. With
no image, or after two loads in a row that end back in the bootloader, the node leaves the device to USB/IP,
for `picotool` from your machine. `bay coproc` in the node's shell and `GET /api/coproc` say how the last
load went: `idle`, `loading`, `started`, `loaded`, `failed` or `left to USB/IP`.

A new image runs from the co-processor's next power-up, and the DATA ×4 powers it: today that means a power
cycle of the whole DATA ×4 and its boards (`bay power cycle` in the node's shell, as
[the DATA ×4 checklist](../build/check-the-pcbs/data-x4.md) does). `bay coproc reload`, to restart the
co-processor alone, is planned and not written.

## In the browser

```{figure} ../img/web-ui-analyzer.png
:class: bb-screenshot
:alt: The Logic analyzer card after Capture and reset on B3.2: This page selected, the settings folded to one line, lanes A to H named with their decoders, the Mark lane falling at the trigger, the decoded table with its search box

Simulated node, with the simulator's signals: a UART each way on A and B, I²C on C and D, SPI on E to H, and
the Mark lane falling as B3.2 leaves reset.
```

The **Logic analyzer** card appears on `http://bay-b3.local/` when the node reports an analyzer. Its line at
the top says whose it is (**This page** or **USB/IP**) and what runs: "gusmanb 6.0 in RAM · loaded in 59 ms".
Set the sample rate, the duration, the share before the trigger (10, 20 or 50 %), the trigger's channel and
edge, and the channels; each lane takes its bus's name from the Wires card. **Capture** arms it.

For the UART of [Wires between boards](wires.md), B3.2's TX on bus A: trigger on A, falling, at 10 MS/s, and
add a UART decoder on A at 115200 Bd. The card says what the buffer holds at the rate chosen, and warns, with
a button for a rate that does, when the duration does not fit or the rate is low for a decoder: under ten
samples a bit for a UART, under 10 MS/s for WS2812B, clock pulses 1 or 2 samples wide for I²C and SPI.

A trigger fires at once if its line already rests at the level the edge leads to: `A:fall` on a line that is
low does not wait for a fall (seen on the bench).

After a capture the settings fold to one line and the viewer takes the room; **Full screen** gives it the
window. The decoders are UART, I²C, SPI, WS2812B, PWM / clock (frequency and duty cycle), 1-Wire (standard
speed), CAN (classic frames on a controller's TX or RX pin, before its transceiver; an FD frame is named and
skipped) and SWD. The decoded data is also a table: search it, click a row or walk it with the arrows, and the
viewer jumps there. A UART's bytes make one row per line of text, or per burst of a binary protocol, so a
search finds a whole word. 1-Wire reads resets, presence, ROM commands and codes with their CRC, and bytes;
CAN, each frame's identifier, data, CRC and ACK; SWD, each request by name, its ACK and its data with their
parity, line resets and the switch from JTAG: what to look at when a flash fails. Over a box, a tooltip gives
its value. With the viewer focused, + and − zoom, ← and → pan, 0 fits and Esc clears the cursors.

The card holds the analyzer only while it captures, for one page at a time: the same address takes it over
(a reload), another is refused. Bus names, settings and decoders stay in the browser.

## With bayctl

```console
$ python tools/bayctl.py capture B3 --ch A,B --rate 10M --duration 20ms --trigger A:fall --decode uart:rx=A,baud=115200 --decode uart:rx=B,baud=115200 -o run1
```

It prints `armed` once the analyzer waits, then writes `run1.capture.json`, which either page opens, and
`run1.decoded.json`, with each decoded row's boxes, its `values` in order and, where the decoder groups them,
its `frames` (a UART's lines, with their `bytes`) and `stats` (PWM's `min`, `max`, `mean`). It runs the page's
own decoders on Node (`tools/analyzer_capture.mjs`), so its results are what the viewer shows; the rest of
`bayctl` needs only Python.

Without options it takes channels A to H at 10 MS/s, as long as the buffer holds, 20 % before a trigger on the
first channel's fall, and waits 10 s for it. A trigger that does not come in `--timeout` seconds exits with
code 3, so a test can tell "nothing was sent" from an error (exit 1). The decoder specs and every option:
[bayctl](../reference/bayctl.md#capture).

## Capture from a reset

**Capture and reset…** on the card turns the Mark lane on, arms the analyzer on MARK's fall and pulses the
RESET line of the port you pick. MARK is a line the node drives: high while it holds a board in reset or off,
falling as the board starts. The capture begins as the board leaves reset, so its boot messages are in it.

```console
$ python tools/bayctl.py capture B3 --ch A --reset B3.2 --decode uart:rx=A,baud=115200 -o boot
```

`--reset` takes one of the bay's ports and replaces `--trigger`. It needs the port's RST pin wired to the
board's reset: B3's ribbons in the example carry no RESET wire, so add one from RST to the Pico 2's RUN pin,
as `config/rack.yaml` does for B1.2. Neither the card's button nor `--reset` has run on hardware.

The sample width follows the highest channel asked for: with the Mark lane (channel 13) each sample takes two
bytes, and the 384 KB buffer holds half as many: 196,608 samples, as on the screenshot, against 393,216 on
eight channels.

## Save, reopen, export

**Save capture** writes a JSON file with the samples, the names and the decoders; **Open a capture…** reads
one back on the bay's page or on the standalone page, with no analyzer there. A script needs these fields:
`format`, `version`, `channels`, `names`, `rate`, `pre`, `post`, `decoders`, `bytesPerSample` and `samples`
(base64 of little-endian words, bit *i* = `channels[i]`, sample `pre` the trigger).

**Download .vcd** writes the capture for PulseView and GTKWave. For sigrok's other decoders, run
`sigrok-cli` on that file.

## Hand the analyzer to USB/IP

The analyzer belongs to the bay's page or to USB/IP, never both. **USB/IP** on the card, or the control right over HTTP,
hands it to your machine for gusmanb's desktop app or PulseView, without a re-plug; a page connected is
closed. On a DATA ×4 it is on offer as busid `1-1.5`, the co-processor's hub port:

```console
$ curl -s -X POST bay-b3.local/api/analyzer -d '{"owner": "usbip"}'
$ sudo usbip attach -r bay-b3.local -b 1-1.5
```

`{"owner": "page"}` gives it back. On the stand-in both hand-overs worked, and a capture relayed to the page
moved 384 KB in 1.05 s. Every field of `/api/analyzer`: [Bay node HTTP API](../reference/node-api.md).

## The standalone page and its demo capture

[The analyzer page](/analyzer/) is the same interface outside a bay. In Chrome or Edge on a computer it reaches
an analyzer on your machine's USB through Web Serial: a Pico 2 running gusmanb's firmware (1209:3020). It can
also load a `no_flash` build into a blank RP2350 in its bootloader over WebUSB, tested against a fake
bootloader only. In any browser it opens saved captures and a demo capture of made-up signals
([Try it without hardware](../plan/try-it-without-hardware.md#the-logic-analyzers-demo-capture)). The page
speaks gusmanb's protocol; the analyzer itself is his GPL-3.0 firmware
([Licences and credits](../engineering/licences-and-credits.md)).

## A Pico 2 on a port instead

A DATA ×6 has no co-processor and its bay's page shows no analyzer. There, or wherever a board's own pins
must be watched, a stock Pico 2 in a sub-slot runs gusmanb's release firmware, the one `config/rack.yaml`
pins (`logic-analyzer-firmware_v6.0.0_BOARD_PICO_2.zip` of v6.0.0.0, not the `_Turbo` build). The example
rack has one in B3.3, chosen on 2026-10-19 for the time before the DATA ×4's co-processor; `role: analyzer`
keeps it out of twister's map, and you use it over USB/IP with gusmanb's app (`bayctl lease B3.3 --for 2h`,
then `bayctl attach B3.3 --show`), one client at a time.

Its channels are Dupont jumpers to the boards' pins, GP2 to GP9 first (channels 1 to 8), with a GND jumper
beside each group and GP0 jumpered to GP1 for complex triggers. It reads 3.3 V logic with no level shifting
and no protection, and it takes a sub-slot. Buy its RP2350 at revision A4. Wiring, flashing and limits:
[A logic analyzer in a sub-slot](../multi-dut-node.md#a-logic-analyzer-in-a-sub-slot).

When the card says "No analyzer image on the node", "The analyzer is not on the bus" or "the analyzer does not
answer", see [Troubleshooting](troubleshooting.md).
