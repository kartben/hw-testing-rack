# Bring-up: the first boards

What to check when the v1.0 boards arrive, and in which order.  One short
checklist per board; each takes the board from the bag to working in the
rack.  The expected values are the design's: no board has been measured yet,
so the first one sets the reference for the second.

| Order | Board | Checklist | Needs |
|---|---|---|---|
| 1 | Power hub | [bring-up/power-hub.md](bring-up/power-hub.md) | a USB-C PD charger |
| 2 | Bay node | [bring-up/bay-node.md](bring-up/bay-node.md) | a bench supply, then the hub |
| 3 | Camera pod | [bring-up/camera-pod.md](bring-up/camera-pod.md) | a working node, an Arducam Mega |
| 4 | DATA ×6 | [bring-up/data-port-x6.md](bring-up/data-port-x6.md) | a bench supply; a working node (its firmware drives the board since 2026-11-11, tested in simulation only) |
| 5 | DATA ×4 | [bring-up/data-port-x4.md](bring-up/data-port-x4.md) | a working node |
| 6 | The rack bus | [bring-up/rack.md](bring-up/rack.md) | the hub and two nodes |

The order adds one unknown at a time: the hub needs nothing else, the node
runs from a bench supply before it meets the hub, and the three other boards
hang off a node that already works.

## Every board, the same five stages

1. **Look.**  Compare the board with its render in `electronics/<board>/docs/<board>-top.jpg`.
   Check the pin-1 mark of every IC, the stripe of the electrolytic capacitor, the LEDs and the
   diodes.  The order asked the fab about the rotation of the QFN and SOT-23-6 parts: look at
   those first, and stop if one is turned.
2. **Measure with no power.**  Ohmmeter between each supply pad and GND, on the labelled test
   pads of the bottom face.  A reading that starts low and climbs is a capacitor charging: fine.
   A steady reading under 10 Ω is a short: stop.  Write the readings down.
3. **First power, current limited.**  Bench supply with the limit the checklist gives, or the
   source it names.  Check each rail on its pad before plugging anything else in.
4. **Flash, then ask the firmware.**  The shell and the status page report what the board sees.
5. **Load it.**  The checks that need a load, a DUT or a second board.

Do the whole checklist on the first assembled board before powering the second.  The three
bare PCBs of each order are for comparing a doubtful reading with a board that has no parts.

## What you need

- a multimeter with a continuity beeper, a magnifier;
- a bench supply, 0–30 V, with a current limit;
- a USB-C PD charger of 65 W or more, and USB-C cables;
- the leads: a row lead (JST PH 6), a DATA lead and a camera lead (JST PH 8, both "Same direction");
- a 3.3 V USB-UART adapter with probe clips (for the node's shell before it is on Wi-Fi);
- a Linux machine with the firmware workspace ([firmware/README.md › Building](../firmware/README.md#building));
- a USB device to plug into the DATA ports (a memory stick, a dev board), and a 47 Ω 10 W resistor as a row load.

## Firmware to build before the boards arrive

```bash
west build --sysbuild -b power_hub/esp32s3/procpu -d build-hub hw-testing-rack/firmware/power-hub
west build --sysbuild -b bay_node/esp32s3/procpu  -d build-bay hw-testing-rack/firmware/bay-node -- -DEXTRA_CONF_FILE=wifi.conf
```

`wifi.conf` (from `firmware/bay-node/wifi.conf.example`) puts the node on Wi-Fi at its first
boot, so its page and its telnet shell answer without the UART pads.

## One irreversible step

Each ESP32-S3 module gets one eFuse burnt (`DIS_USB_OTG_DOWNLOAD_MODE`,
[firmware.md › Programming](firmware.md#programming)).  It cannot be undone.  Do it last,
on a board that passed everything else, and only on boards that will go into the rack.

## What the bench finds

v1.0 is frozen ([electronics.md › Revisions at the fab](electronics.md#revisions-at-the-fab)).
A fault found here is written in the table below and fixed in the next revision of that
board.  A bodge on a v1.0 board is noted here too, with the board it was done on.

| Date | Board (which one of the two) | Step | Found | Done on the board | For the next revision |
|---|---|---|---|---|---|
| | | | | | |

More to measure on the first boards, once they work: [electronics.md › Bring-up measurements](electronics.md#bring-up-measurements)
and [assembly.md › Bring-up](assembly.md#7-bring-up).
