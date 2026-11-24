# Logic analyzer

A DATA ×4 has a logic analyzer built in. It samples the eight buses A to H: the lines that you join to your
boards' pins on the Wires card ([Wires between boards](wires.md)). The bay's page shows what it captured and decodes it.

You need a DATA ×4 with its pin matrix (`x4: v2` in `config/rack.yaml`), and you need to load the analyzer's
firmware once.

## Load the analyzer image, once

The analyzer runs gusmanb's [LogicAnalyzer](https://github.com/gusmanb/logicanalyzer) firmware on the
DATA ×4's co-processor, an RP2350B. That firmware is GPL-3.0 and does not come with BitBunk, so you build it
yourself. The co-processor has no flash, so the image must run from RAM. The release's own UF2 for the Pico 2
runs from flash, and `bayctl coproc load` refuses it.

You need CMake, a C++ compiler for your machine, and the Arm GNU toolchain (`arm-none-eabi-gcc`).

1. Get pico-sdk 2.0.0 with its TinyUSB, and tell CMake where it is:

   ```console
   $ git clone --depth 1 --branch 2.0.0 https://github.com/raspberrypi/pico-sdk.git
   $ git -C pico-sdk submodule update --init --depth 1 lib/tinyusb
   $ export PICO_SDK_PATH=$PWD/pico-sdk
   ```

2. Get the analyzer's source at tag v6.0.0.0:

   ```console
   $ git clone --depth 1 --branch v6.0.0.0 https://github.com/gusmanb/logicanalyzer.git
   $ cd logicanalyzer/Firmware/LogicAnalyzer_V2
   ```

3. Change three lines. The first turns off the overclock. The second lets the build run without the files
   of the Pico VS Code extension. The third makes an image that runs from RAM:

   ```console
   $ sed -i 's/set(TURBO_MODE 1)/set(TURBO_MODE 0)/' LogicAnalyzer_Build_Settings.cmake
   $ sed -i 's|pico-vscode.cmake)|pico-vscode.cmake OPTIONAL)|' CMakeLists.txt
   $ sed -i 's/copy_to_ram/no_flash/' CMakeLists.txt
   ```

   On macOS, write `sed -i ''`. Leave `BOARD_TYPE` on `BOARD_PICO_2`.

4. If your machine's C++ compiler is g++ 15, run `export CXXFLAGS="-include cstdint"`. The SDK's `pioasm` does
   not build with it otherwise.

5. Build:

   ```console
   $ cmake -B build
   $ cmake --build build
   ```

   The first build also downloads and builds picotool. The image is `build/LogicAnalyzer.uf2`.

Then store the image on the node. Run `bayctl` from your BitBunk checkout, with the path of
`LogicAnalyzer.uf2`. This needs the admin key in `BAYCTL_KEY`:

```console
$ python tools/bayctl.py coproc load B3 LogicAnalyzer.uf2
$ python tools/bayctl.py coproc status B3
```

The node keeps the image, and loads it into the co-processor each time the DATA ×4 powers up. To start a new
image, power-cycle the DATA ×4 with `bay power cycle` in the node's shell. This restarts the bay's boards too.

## In the browser

```{figure} ../img/web-ui-analyzer.png
:class: bb-screenshot
:alt: The Logic analyzer card after Capture and reset on B3.2: This page selected, the settings folded to one line, lanes A to H named with their decoders, the Mark lane falling at the trigger, the decoded table with its search box

A simulated node: a UART each way on A and B, I²C on C and D, SPI on E to H.
```

The **Logic analyzer** card of `http://bay-b3.local/` appears on a bay with a DATA ×4.

1. Set the sample rate, the duration, the trigger's channel and edge, and the channels.
2. Add a decoder for each signal: UART, I²C, SPI, WS2812B, PWM, 1-Wire, CAN or SWD.
3. Click **Capture**.

For example, the UART of [Wires between boards](wires.md) has B3.2's TX on bus A. Trigger on A, falling
edge, at 10 MS/s, and add a UART decoder on A at 115200 Bd. The card warns you when the sample rate is too low
for a decoder.

A trigger fires at once if its line is already at the level the edge leads to. For example, `A:fall` on a
line that is already low does not wait.

The decoded data also appears as a table. Search it or click a row, and the viewer jumps to that point. With
the viewer focused, + and − zoom, ← and → pan, and 0 fits the whole capture.

Only one page at a time can use the analyzer. If the card says "No analyzer image on the node" or "the
analyzer does not answer", see [Troubleshooting](troubleshooting.md).

## With bayctl

`bayctl capture` needs Node.js 22 or later on your machine.

```console
$ python tools/bayctl.py capture B3 --ch A,B --trigger A:fall --decode uart:rx=A,baud=115200 -o run1
```

It prints `armed` and waits for the trigger. Then it writes two files: `run1.capture.json`, which the bay's
page can open, and `run1.decoded.json`, with the decoded data. It uses the same decoders as the page, so it
finds what the viewer shows.

Without options, it captures A to H at 10 MS/s. If the trigger does not come within 10 s, it exits with code 3,
so a test can tell "nothing was sent" from an error. Every option: [bayctl](../reference/bayctl.md#capture).

## Capture from a reset

**Capture and reset…** on the card triggers on the moment a board leaves reset, so its boot messages are in
the capture. The node resets the port you pick and marks the moment on the MARK line, channel 13.

```console
$ python tools/bayctl.py capture B3 --ch A --reset B3.2 --decode uart:rx=A,baud=115200 -o boot
```

The port's RST pin must be wired to the board's reset pin. In the example rack, B3's ribbons have no reset
wire: add one from RST to the Pico 2's RUN pin.

With MARK on, the buffer holds half as many samples: 196,608 instead of 393,216.

## Save and export a capture

**Save capture** writes a JSON file with the samples, the bus names and the decoders. **Open a capture…**
reads one back, on the bay's page or on [the standalone analyzer page](/analyzer/). **Download .vcd** writes
the capture for PulseView, GTKWave and `sigrok-cli`.

## Use the analyzer over USB/IP

The **USB/IP** button on the card hands the analyzer over to USB/IP. Attach it as busid `1-1.5`, then use it
from gusmanb's desktop app or PulseView:

```console
$ curl -s -X POST bay-b3.local/api/analyzer -d '{"owner": "usbip"}'
$ sudo usbip attach -r bay-b3.local -b 1-1.5
```

`{"owner": "page"}` gives it back to the page ([Bay node HTTP API](../reference/node-api.md)).

## Open a capture without a rack

[The analyzer page](/analyzer/) opens saved captures in any browser, and has a demo capture
([Try it without hardware](../plan/try-it-without-hardware.md#the-logic-analyzers-demo-capture)). In Chrome
or Edge, it can also drive a Pico 2 running gusmanb's firmware on your own USB. The analyzer firmware is
gusmanb's work ([Licences and credits](../reference/licences-and-credits.md)).

## Use a Pico 2 on a port as the analyzer

A DATA ×6 has no analyzer. In such a bay, or to watch a board's own pins, put a stock Pico 2 on a port. Flash
it with gusmanb's release firmware `logic-analyzer-firmware_v6.0.0_BOARD_PICO_2.zip`, not the `_Turbo` build.
The example rack has one in B3.3. Give it `role: analyzer` in the lab file to keep it out of twister's map,
and use it over USB/IP:

```console
$ python tools/bayctl.py attach B3.3 --show
```

Its channels 1 to 8 are GP2 to GP9. Join them to the boards' pins with Dupont jumpers, with a GND jumper
beside each group. It reads 3.3 V logic only, with no protection. Buy a Pico 2 whose RP2350 is revision A4.
