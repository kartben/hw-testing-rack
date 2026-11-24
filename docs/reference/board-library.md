# Board library

The board library, [mechanical/boards/boards.yaml](../../mechanical/boards/boards.yaml), lists the
development boards the rack knows. For each board it gives the size, the mounting holes, the debug USB, how
high the board sits above the plate, and the Zephyr defaults. A bay in `config/rack.yaml` names its board by
the id in the first column below. To add a board, see [Add a board to the library](../use/add-a-board.md).

## The boards

| `id` | Board | Outline, mm | Standoff, mm |
|---|---|---|---|
| `arduino-uno-r4` | Arduino UNO R4 Minima or WiFi | 68.58 × 53.34 | 6 |
| `giga-r1-display` | Arduino GIGA R1 WiFi with the GIGA Display Shield | 106.0 × 80.0 | 5 |
| `nucleo-64` | ST NUCLEO-64 (MB1136, MB1367) | 70.0 × 82.5 | 12 |
| `nucleo-144` | ST NUCLEO-144 (MB1137, MB1364, MB1404) | 70.0 × 133.34 | 12 |
| `rpi-pico2` | Raspberry Pi Pico, Pico 2 (W) | 21.0 × 51.0 | 9 |
| `esp32-s3-devkitc` | Espressif ESP32-S3-DevKitC-1 v1.1 | 25.4 × 62.74 | 10 |
| `esp32-c6-devkitc` | Espressif ESP32-C6-DevKitC-1 v1.2 | 25.4 × 51.8 | 10 |
| `xiao` | Seeed Studio XIAO, any | 17.78 × 20.96 | 6 |
| `arduino-nano-matter` | Arduino Nano Matter | 17.78 × 43.18 | 6 |
| `beagleplay` | BeagleBoard.org BeaglePlay | 80.0 × 80.0 | 6 |
| `wio-terminal` | Seeed Wio Terminal, the whole device | 72.0 × 57.0 | 11 |
| `microbit-v2` | BBC micro:bit v2 | 51.6 × 42.0 | 6 |
| `frdm-mcxn947` | NXP FRDM-MCXN947 | 118.0 × 55.0, approximate | 10 |
| `nrf54l15-dk` | Nordic nRF54L15 DK | 63.55 × 117.05, approximate | 10 |
| `nrf52840-dk` | Nordic nRF52840 DK | 63.55 × 136.58, approximate | 10 |
| `nrf5340-dk` | Nordic nRF5340 DK | 64.0 × 136.0, approximate | 10 |
| `frdm-k64f` | NXP FRDM-K64F | 81.0 × 53.0, approximate | 10 |
| `stm32f746g-disco` | ST STM32F746G-DISCO | 86.0 × 154.0, approximate | 10 |
| `mimxrt1060-evkb` | NXP MIMXRT1060-EVKB | 130.0 × 108.0, approximate | 10 |
| `mimxrt1170-evkb` | NXP MIMXRT1170-EVKB | 165.0 × 127.0, approximate | 12 |

The outline is width × length, as in the vendor's drawing. The standoff is the gap between the plate and the
underside of the board. It is also the height of the board's {term}`pegs <peg>`.

Eight outlines are approximate (`verified: false`). They come from a secondary source. The library has no
holes for those boards, so no pin can hold them, and their peg layouts are only a guide. If you own one of
these boards, measure it and set `verified: true` ([Add a board to the library](../use/add-a-board.md)).

## What fits in a bay

| Holder | What fits |
|---|---|
| The honeycomb plate | a board within the plate's 134.5 × 159.4 mm |
| The drawer's side wall, used as a stop | a board whose standoff is 6.4 mm or less |
| A lane of a {term}`slot bin` | a board up to 19.8 mm thick in all, 86.5 mm long from its USB edge and 82 mm tall on edge |

On the honeycomb plate, keep clear of the edges. The drawer's front overhangs both front corners of the
plate, the right one more. Only a peg's flange passes under it. A board whose USB faces the port wall needs
up to 26 mm behind it for the plug and the first bend of the cable.

A board on a plate must also fit under what hangs above it. In a 165 mm row, a camera pod comes down to
120 mm above the row. The cables of boards on plates arch up to about 105 mm.

In a slot bin, the 19.8 mm counts everything under and over the PCB, a plug in its USB included. The
library holds these two figures in `on_edge`. These boards fit a lane: `arduino-uno-r4`, `nucleo-64`,
`rpi-pico2`, `esp32-s3-devkitc`, `esp32-c6-devkitc`, `xiao`, `arduino-nano-matter`, `wio-terminal` and
`microbit-v2`. The others are too thick, too long or too tall. `python tools/build.py web` warns you when a
board is in a lane too small for it.

On the honeycomb plate, the layout tool (`tools/plate_layout.py`) finds pegs for every board alone in a bay,
with three exceptions:

- `stm32f746g-disco`: the tool reports `no peg fits`.
- `mimxrt1170-evkb`: the tool reports `no peg fits`. The board is wider than the drawer, so no bay can take it.
- `esp32-s3-devkitc` and `esp32-c6-devkitc`: the tool finds no stop and no cam, and reports
  `held along one axis by friction only` for both axes.

To run the tool for your own bay, see [Ask the tool where the pegs go](../use/mount-a-board.md#ask-the-tool-where-the-pegs-go).
[What the notes mean](../use/add-a-board.md#what-the-notes-mean) explains what it prints, and what to do when
pegs cannot hold a board. The example rack puts the GIGA R1 on its own plate (`plate: boards`), because
the display shield hides the GIGA's edges.

## The fields of boards.yaml

| Field | What it holds | When absent |
|---|---|---|
| `name`, `short` | the board's name, and the short one the 3D model and the bill of materials print | `short`: `name`, or the id in the bill of materials |
| `size` | `[width, length]` of the outline, in the vendor's drawing, origin at its bottom-left corner | required |
| `holes`, `hole_d` | the centres of the mounting holes, `[x, y]`, and their diameter | no holes; 3.2 |
| `usb` | the debug USB: `edge` (`top`, `bottom`, `left` or `right` of the drawing), `pos` (its centre along that edge: from the left for top and bottom, from the bottom for left and right), `type` (`usb-c`, `micro-b`, `mini-b`) | the middle of the top edge, `usb-c` |
| `second_usb` | a second USB connector, with the same keys | none |
| `orient` | `side` turns the debug USB towards the drawer's right wall. Use it for a small board on a straight cable, or for a board too long to leave room for a plug behind it | towards the port wall |
| `pegs.keepout` | `[edge, from, to]`: stretches of the outline no peg may touch, such as a header or a connector at the edge. The tool keeps the way for the USB plug clear without it | none |
| `standoff` | from the top of the plate to the underside of the PCB: the height of the board's pegs | 6 |
| `height` | the tallest part above the PCB | 10 |
| `pcb_t` | the PCB's thickness | 1.6 |
| `on_edge` | `[under, over]` the bottom face of the PCB, in a lane of a slot bin | `standoff`, and `pcb_t` + `height` |
| `fence` | `true`: corner fences on the board's own plate (`plate: boards`) instead of inserts. A board without holes gets them anyway | false |
| `headers` | 2.54 mm pin headers for Dupont jumpers: rows of `n` pins from `at` by `step`, with their `names` | none |
| `color`, `screen`, `model` | the colour the 3D model paints, a live screen on the board, and the vendor's 3D model with its credit ([Licences and credits](licences-and-credits.md)) | a plain green board |
| `source`, `verified` | where the outline comes from, and whether it was measured or taken from the vendor's own drawing | `verified`: false |
| `span` | `2`: the board needs a double-width bay. The rack has none | |
| `zephyr` | the board's Zephyr defaults, below | |

## Zephyr defaults

| `id` | Target (`platform`, or the `choices`) | `runner` |
|---|---|---|
| `arduino-uno-r4` | `arduino_uno_r4@minima`, `arduino_uno_r4@wifi` | `pyocd` |
| `giga-r1-display` | `arduino_giga_r1/stm32h747xx/m7` | `dfu-util` |
| `nucleo-64` | `nucleo_c031c6`, `nucleo_f401re`, `nucleo_f446re`, `nucleo_g071rb`, `nucleo_g474re`, `nucleo_l476rg` | `stm32cubeprogrammer` |
| `nucleo-144` | `nucleo_f429zi`, `nucleo_f767zi`, `nucleo_h563zi`, `nucleo_h743zi`, `nucleo_u575zi_q` | `stm32cubeprogrammer` |
| `rpi-pico2` | `rpi_pico2/rp2350a/m33_0` | `uf2` |
| `esp32-s3-devkitc` | `esp32s3_devkitc/esp32s3/procpu` | `esp32` |
| `esp32-c6-devkitc` | `esp32c6_devkitc/esp32c6/hpcore` | `esp32` |
| `xiao` | `xiao_ble`, `xiao_esp32c3`, `xiao_esp32c6/esp32c6/hpcore`, `xiao_esp32s3/esp32s3/procpu`, `xiao_rp2040` | `uf2` or `esp32`, by target |
| `arduino-nano-matter` | `arduino_nano_matter` | `openocd` |
| `beagleplay` | `beagleplay/cc1352p7`, `beagleplay/am6254/m4` | none: flashed from its own Linux, over SSH |
| `wio-terminal` | `wio_terminal` | `bossac` |
| `microbit-v2` | `bbc_microbit_v2` | `pyocd` |
| `frdm-mcxn947` | `frdm_mcxn947/mcxn947/cpu0` | `linkserver` |
| `nrf54l15-dk` | `nrf54l15dk/nrf54l15/cpuapp` | `nrfutil` |
| `nrf52840-dk` | `nrf52840dk/nrf52840` | `nrfutil` |
| `nrf5340-dk` | `nrf5340dk/nrf5340/cpuapp` | `nrfutil` |
| `frdm-k64f` | `frdm_k64f` | `pyocd` |
| `stm32f746g-disco` | `stm32f746g_disco` | `stm32cubeprogrammer` |
| `mimxrt1060-evkb` | `mimxrt1060_evk@B/mimxrt1062/qspi` | `linkserver` |
| `mimxrt1170-evkb` | `mimxrt1170_evk@B/mimxrt1176/cm7` | `linkserver` |

Each entry's `zephyr` field also lists the USB ids of its debug USB. When a device with one of those ids is on
a port, the bay's page offers these targets. The page reads them from a copy built into the node's firmware,
so a board you add shows there only after you update the firmware. For a family with several `choices`, pick
one for each port.
`bayctl` takes the runner from here when it writes twister's hardware map.
[Board targets](../use/board-targets.md) explains how a port gets its target.

## Boards that need a wire or a probe

Every board sits on a port of a DATA board. Its console must be a serial port on USB: the board's own, or a
probe's. Only a DATA ×4 port has a RESET and a BOOT pin, which you wire to the board with jumper wires
([Reset and bootloader](../use/power-and-reset.md#reset-and-bootloader)). A DATA ×6 port has USB only.

Most boards in the library need nothing more. These do.

### Arduino UNO R4 Minima (`arduino-uno-r4`)

The UNO R4 WiFi needs nothing: its ESP32-S3 is the probe and the USB console. The Minima has neither. Wire an
SWD probe that has a serial port, such as a Raspberry Pi Debug Probe, to the Minima's SWD pins and to D0 and
D1. Plug the probe into another port of the bay.

### Arduino GIGA R1 (`giga-r1-display`)

Build with `--shield arduino_giga_display_shield`. The console is on the GIGA's USB-C. `dfu-util` needs the
bootloader, which a double tap of RESET starts. Put the GIGA on a DATA ×4 port, and wire the port's RST pin
to the GIGA's RESET pin. Then reset the port twice in quick succession.

### Raspberry Pi Pico 2 (`rpi-pico2`)

The Pico 2 has no probe. Build with `-S cdc-acm-console` to put the console on its USB. `uf2` copies the
image onto the bootloader's drive, so the drive must be mounted on your machine.

A blank Pico 2 starts in its bootloader. To start the bootloader again later, put the board on a DATA ×4
port and wire the port's BOOT pin to TP6. Then run `bayctl boot <port> --power-cycle`. You can also add a
Raspberry Pi Debug Probe on another port and use `openocd`.

### Arduino Nano Matter (`arduino-nano-matter`)

The SAMD11 on the board is a CMSIS-DAP probe on the USB-C. `openocd` needs Arduino's fork to write the
MG24's flash. You can also use `jlink`.

### Seeed Wio Terminal (`wio-terminal`)

The Wio Terminal has no probe. Its console and its UF2 bootloader are on the USB-C, and a double reset starts
the bootloader. Put the Wio on a DATA ×4 port, and wire the port's RST pin to the Wio's RESET pad. Then reset
the port twice in quick succession.

### BeagleBoard.org BeaglePlay (`beagleplay`)

Flash it from the board's own Linux: the CC1352 with `cc1352_flasher --play`, the M4 through remoteproc.
