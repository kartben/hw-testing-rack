# Board library

[mechanical/boards/boards.yaml](../../mechanical/boards/boards.yaml) describes 20 development boards: their
outlines, holes and debug USB, how high they stand over the plate, and their Zephyr defaults. Twelve outlines
are verified and eight are approximate. A bay's entry in `config/rack.yaml` names a board by its id, the first
column below.

## The boards

| `id` | Board | Outline, mm | Standoff, mm |
|---|---|---|---|
| `arduino-uno-r4` | Arduino UNO R4 Minima / WiFi | 68.58 × 53.34 | 6 |
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

Read from `mechanical/boards/boards.yaml`. The outline is as the vendor's drawing shows it, width first; the
standoff is the gap from the plate to the underside of the PCB, and the height of the board's pegs.

## How each is held

What `tools/plate_layout.py` returned on 2026-11-24 for each board alone in a bay on the default plate, and
whether the board fits a lane of a slot bin. The layouts change with `boards.yaml` and the plate: for your
bay, run the tool on it
([Ask the tool where the pegs go](../use/mount-a-board.md#ask-the-tool-where-the-pegs-go)).

| `id` | On the plate | In a slot bin |
|---|---|---|
| `arduino-uno-r4` | a pin, two cams | yes |
| `giga-r1-display` | four stops, four cams. The example's B2 gives it its own plate (`plate: boards`): the shield hides the GIGA's edges | no: 21.1 mm thick, 106 mm long |
| `nucleo-64` | three stops, three cams | yes |
| `nucleo-144` | a pin, two cams | no: 27.6 mm thick, 133 mm long |
| `rpi-pico2` | a pin and a cam: `one cam only` | yes |
| `esp32-s3-devkitc` | no stop and no cam: `held along one axis by friction only`, on both axes | yes |
| `esp32-c6-devkitc` | the same | yes |
| `xiao` | two stops, a cam: `no cam on its B edge` | yes |
| `arduino-nano-matter` | three stops, a cam: `no cam on its B edge` | yes |
| `beagleplay` | four stops, four cams | no: 21.6 mm thick |
| `wio-terminal` | four stops, three cams | yes |
| `microbit-v2` | four stops, a cam: `no cam on its F edge` | yes |
| `frdm-mcxn947` | three stops, three cams | no: 25.6 mm thick, 118 mm long |
| `nrf54l15-dk` | four stops, four cams | no: 23.6 mm thick, 117 mm long |
| `nrf52840-dk` | four stops, two cams: `no cam on its B edge` | no: 23.6 mm thick, 137 mm long |
| `nrf5340-dk` | the same | no: 23.6 mm thick, 136 mm long |
| `frdm-k64f` | three stops, three cams | no: 21.6 mm thick |
| `stm32f746g-disco` | `no peg fits` | no: 21.6 mm thick, 154 mm tall on edge |
| `mimxrt1060-evkb` | four stops, a cam: `no cam on its R edge` | no: 27.6 mm thick, 108 mm long, 130 mm tall on edge |
| `mimxrt1170-evkb` | `no peg fits`: it is wider than the drawer | no |

A note in code type is the tool's own words: what each one means for the board, and what to do when the
pegs cannot hold it, is on [A board that is not in the library](../use/add-a-board.md#what-the-notes-mean). A
slot bin's reasons are the warnings that `python tools/build.py web` prints for a board in a lane too small
for it. Layouts for the eight boards with an approximate outline are only indicative.

The example rack holds `esp32-s3-devkitc` and `esp32-c6-devkitc` in slot bins, and the GIGA on its own plate.

## What fits in a bay

| Holder | What it takes |
|---|---|
| The honeycomb plate | a board inside the plate's 134.5 × 159.4 mm, clear of what hangs over the plate's front: the display's frame over the front-right corner and the front's joints at both front corners, which only a peg's flange passes under. A board whose USB faces the port wall needs room behind it for its plug and the cable's first bend, up to 26 mm |
| The drawer's side wall, instead of stops | a board whose standoff is 6.4 mm or less |
| A lane of a slot bin | a board up to 19.8 mm thick in all (`on_edge`: what reaches under the PCB and over it, a plug in its USB included), 86.5 mm long from its USB edge and 82 mm tall on edge |
| No bay | a board wider than the drawer, such as the MIMXRT1170-EVKB: it would take a double-width bay, which is not designed |

No source states how tall a board on a plate may be. The cables of boards on plates arch up to about 105 mm
over the row, and a camera pod hangs down to 120 mm, its lens about 30 mm under the ceiling.
A slot bin's 82 mm are those of the 120 mm row C, 85 mm from the bin's floor to the ceiling.

Read from `config/rack.yaml` › `drawer.slot_bin`, `tools/rackcfg.py` and `tools/plate_layout.py`. The pegs,
the plate and the slot bin: [Put a board in a bay](../use/mount-a-board.md).

## Unverified outlines

`verified: false` marks an outline or holes taken from secondary sources. The eight, with the `source` each
entry gives:

| `id` | Source |
|---|---|
| `frdm-mcxn947` | NXP UM12018: outline only, holes not published |
| `nrf54l15-dk` | Nordic hardware files PCA10156 1.0.0: outline and USB, holes not taken over yet |
| `nrf52840-dk` | Nordic hardware files PCA10056 3.0.3: outline and USB, holes not taken over yet |
| `nrf5340-dk` | approximate: measure your board |
| `frdm-k64f` | a community measurement, outline only |
| `stm32f746g-disco` | approximate: measure your board; the position of its USB on the long edge is to confirm |
| `mimxrt1060-evkb` | approximate: measure your board |
| `mimxrt1170-evkb` | approximate: measure your board |

None of them has holes in the library, so none can be held by a pin. If you own one, measure it and set
`verified: true`: [A board that is not in the library](../use/add-a-board.md).

## The fields of boards.yaml

| Field | What it holds | When absent |
|---|---|---|
| `name`, `short` | the board's name, and the short one the 3D model and the bill of materials print | `short`: `name` (the bill of materials: the id) |
| `size` | `[width, length]` of the outline, in the vendor's drawing: origin at its bottom-left corner | required |
| `holes`, `hole_d` | the mounting holes' centres, `[x, y]`, and their diameter | no holes; 3.2 |
| `usb` | the debug USB: `edge` (`top`, `bottom`, `left`, `right` of the drawing), `pos` (its centre along that edge, from the left for top and bottom, from the bottom for left and right), `type` (`usb-c`, `micro-b`, `mini-b`) | the middle of the top edge, `usb-c` |
| `second_usb` | a second USB connector, the same keys | none |
| `orient` | `side`: the debug USB turned to the drawer's right wall, for a small board on a straight cable or one too long for a plug behind it | towards the port wall |
| `pegs.keepout` | `[edge, from, to]`: stretches of the outline no peg may touch (a header or a connector at the edge, pins under it). The USB plug's way is kept clear without it | none |
| `standoff` | the plate's top to the PCB's underside: the height `H` of the board's pegs | 6 |
| `height` | its tallest part over the PCB | 10 |
| `pcb_t` | the PCB's thickness | 1.6 |
| `on_edge` | `[under, over]` the PCB's bottom face, in a slot bin's lane | `standoff`, and `pcb_t` + `height` |
| `fence` | `true`: corner fences on the board's own plate (`plate: boards`) in place of inserts; a board without holes gets them anyway | false |
| `headers` | 2.54 mm pin headers where Dupont jumpers plug: rows of `n` pins from `at` by `step`, with their `names` | none |
| `color`, `screen`, `model` | what the 3D model paints, a live screen on the board, and the vendor's 3D model with its credit ([3D models of the dev boards](../boards-3d.md)) | a plain green board |
| `source`, `verified` | where the outline comes from, and whether it was measured or taken from the vendor's own drawing | `verified`: false |
| `span` | `2`: the board needs a double-width bay, which is not designed. No tool reads it today | |
| `zephyr` | the board's Zephyr defaults: below | |

Read from the header of `boards.yaml` and from `tools/rackcfg.py`, `tools/plate_layout.py` and
`tools/build.py`. Two lines of that header are older than the honeycomb plate: `verified: false` no longer
gives a board a fence plate, and `fence` acts only on a board's own plate.

## Zephyr defaults per family

| `id` | Target (`platform`, or the `choices`) | `runner` |
|---|---|---|
| `arduino-uno-r4` | `arduino_uno_r4@minima`, `arduino_uno_r4@wifi` | `pyocd` |
| `giga-r1-display` | `arduino_giga_r1/stm32h747xx/m7` | `dfu-util` |
| `nucleo-64` | `nucleo_c031c6`, `nucleo_f401re`, `nucleo_f446re`, `nucleo_g071rb`, `nucleo_g474re`, `nucleo_l476rg` | `stm32cubeprogrammer` |
| `nucleo-144` | `nucleo_f429zi`, `nucleo_f767zi`, `nucleo_h563zi`, `nucleo_h743zi`, `nucleo_u575zi_q` | `stm32cubeprogrammer` |
| `rpi-pico2` | `rpi_pico2/rp2350a/m33_0`, console on the bay's AUX UART | `uf2` |
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

Read from the `zephyr` field of each entry, which also lists the USB ids (`usb`) the board's debug USB shows.
The bay's page offers these targets when a device with one of those ids is on a port, from a table compiled
into the node's firmware (`firmware/bay-node/web/board_targets.py`); `bayctl` takes the runner from here when
it writes twister's hardware map. A family with `choices` needs one picked per port. How a port gets its
target: [Board targets](../use/board-targets.md).

From the entries' own notes:

- `arduino-uno-r4`: the WiFi's ESP32-S3 is its probe and USB console; the Minima has neither, so an SWD probe
  and the console on AUX.
- `giga-r1-display`: build with `--shield arduino_giga_display_shield`; `dfu-util` needs the bootloader, a
  double tap of RESET (the bay's AUX RESET).
- `rpi-pico2`: no probe on the board; `uf2` needs BOOTSEL (AUX BOOT to TP6, AUX RESET to RUN), or add a
  Raspberry Pi Debug Probe and use `openocd`.
- `arduino-nano-matter`: its SAMD11 is a CMSIS-DAP probe on the USB-C; `openocd` needs Arduino's fork for the
  MG24's flash, or use `jlink`.
- `wio-terminal`: its UF2 bootloader on the USB-C, entered by a double reset (the bay's AUX RESET); no probe.
- `beagleplay`: the CC1352 with `cc1352_flasher --play`, the M4 through remoteproc, from the board's own Linux.
