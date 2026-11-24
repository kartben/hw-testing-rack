# Wires between boards

A DATA ×4 can connect the pins of its four headers to eight shared lines, the buses A to H. Wire each board
to its header once. After that, you join boards to each other from the bay's page, with the drawer closed.

This needs a DATA ×4 with its pin matrix (`x4: v2` in `config/rack.yaml`). A DATA ×6 has no pin matrix, and
neither has a DATA ×4 built without it (`x4: base`).

## Plug the jumper wires, once

```{figure} ../img/pcbs/data-port-x4-headers-front.jpg
:alt: The DATA ×4's four 2 × 6 headers, numbered 1 to 4, each labelled VREF 1 2 3 4 BOOT over GND 5 6 7 8 RST

KiCad render of the DATA ×4: one header behind each USB-C port, with the pin names printed above it.
```

Each port has a 2 × 6 header: VREF, P1 to P4 and BOOT on the upper row, GND, P5 to P8 and RST on the lower.
The P pins go to the buses. RST and BOOT are the port's reset and boot lines
([Reset and bootloader](power-and-reset.md#reset-and-bootloader)).

1. Tear a few female to female Dupont jumpers, 20 cm long (30 cm where 20 cm does not reach), off the strip.
   Keep them together as a small ribbon.
2. Peel the wires apart at their ends only, about 2 cm.
3. Plug one end of each wire onto a P pin of the header behind the board's port. Plug the other end onto the
   board's signal pin. Keep the wires in the same order at both ends.
4. Wire VREF too (see below). Do not wire GND: the USB cable carries it.

```{figure} ../img/viewer/b3-jumpers.jpg
:alt: Bay B3 pulled out: a XIAO, two Pico 2 and a XIAO on the plate, the DATA ×4 standing at the back, a three-wire ribbon from each of its first two headers to the first two boards

The 3D model: bay B3 open. A three-wire ribbon runs from the header of port 1 to the XIAO, and one from the
header of port 2 to the first Pico 2.
```

## Wire VREF to the board's I/O voltage

Each header has its own level shifter, set by its VREF pin. Wire VREF to the board's 3.3 V or 1.8 V pin.
Logic from 0.95 to 3.6 V works. A 5 V board with TTL inputs, such as most 5 V Arduinos, takes VREF from its
own 3.3 V pin. A 5 V board with strict CMOS inputs is not supported.

A header is one voltage domain. A board that needs more than eight pins takes two headers, with both VREF
pins wired.

Wire VREF before you put a port's pins on a bus. Without it, highs are clipped to about 0.4 V, and the node
cannot warn you: the Wires card shows `VREF ?` for every port.

## Example: a UART between B3.1 and B3.2

The XIAO in B3.1 has its UART on D6 (TX) and D7 (RX). The Pico 2 in B3.2 has its UART on GP0 (TX) and
GP1 (RX). The example rack is wired like this, in `population › B3 › jumpers` of
[config/rack.yaml](../../config/rack.yaml):

| Header pin | B3.1, a XIAO | B3.2, a Pico 2 |
|---|---|---|
| VREF | 3V3 | 3V3 |
| P1 | D7 (RX) | GP0 (TX) |
| P2 | D6 (TX) | GP1 (RX) |

Put both P1 pins on bus A and both P2 pins on bus B. Bus A then carries B3.2's TX to B3.1's RX, and bus B
carries the other direction. The buses are also channels 1 to 8 of the [logic analyzer](logic-analyzer.md), so
it can capture this UART.

## In the browser

```{figure} ../img/web-ui-wires.png
:class: bb-screenshot
:alt: The Wires card: four port headers with pins coloured by bus, the buses A to H named on the right with their pins, a 1.8 ↔ 3.3 V tag, one pin dashed, Discard, Apply and Open all, the bayctl wire line at the foot

A simulated node with a UART, I²C and SPI wired. The dashed pin is a change not applied yet.
```

The **Wires** card of `http://bay-b3.local/` draws each header as it is printed on the board. Tap a P pin to
put it on a bus. Give the bus a name, 23 characters at most: the logic analyzer labels its lane with it. Click **Apply** to send your
changes together. **Open all** takes every pin off the buses.

A tag on a bus warns you when the bus joins a 1.8 V board to a 3.3 V board, or has a single pin. At the foot
of the card is the `bayctl wire` command for the same wiring.

The node forgets the wires when it restarts. Apply them again, or keep the `bayctl wire` command in your
test script.

## With bayctl

```console
$ python tools/bayctl.py wire B3 A=1:P1,2:P1 B=1:P2,2:P2 --name A="UART B3.2 TX" --name B="UART B3.1 TX"
$ python tools/bayctl.py wire B3
$ python tools/bayctl.py wire B3 --open-all
```

A pin is `<port>:P<pin>`. The pins you name are the whole set: every other pin goes off the buses. With no
pins, the command prints the buses. Every option: [bayctl](../reference/bayctl.md#wire).

## Over HTTP

```console
$ curl -s bay-b3.local/api/wires
$ curl -s -X POST bay-b3.local/api/wires -d '{"pins": [{"port": 1, "pin": 1, "bus": "A"}, {"port": 2, "pin": 1, "bus": "A"}, {"port": 1, "pin": 2, "bus": "B"}, {"port": 2, "pin": 2, "bus": "B"}]}'
```

A `POST` with `pins` replaces the whole set, and `"pins": []` opens every pin. Every field:
[Bay node HTTP API](../reference/node-api.md). The node's shell has no command for the wires.

## How fast the buses go

| Signal | Speed to expect |
|---|---|
| SPI, SWD | up to about 5 MHz |
| UART | up to 3 Mbd |
| I²C, on the buses' own 10 kΩ pull-ups | 100 kHz |
| Any signal between a 1.8 V and a 3.3 V board | 1 to 2 MHz |

## What the buses cannot carry

| What | Why |
|---|---|
| CAN_H and CAN_L | The level shifter clips them. Logic-level CAN works up to 500 kbit/s if every board's CAN TX pin is open drain and all TX and RX pins share one bus. |
| Two outputs driving one bus | They fight. A 100 Ω resistor on each pin limits the current. |
| More than eight signals | There are eight buses. |

If a wire does not behave as you expect, see [Troubleshooting](troubleshooting.md).
