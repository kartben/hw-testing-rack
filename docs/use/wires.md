# Wires between boards

A DATA ×4 joins any of its 32 port pins to eight shared lines, the buses A to H, through two crosspoint
switches. Once each board's jumper wires are on its header, a UART between two boards is a change on the
bay's page, and nobody opens the drawer again.

:::{status} simulated
The node's side runs on native_sim against two emulated crosspoint chips: each switch, break-before-make, a
port switched off and on, the HTTP body. No DATA ×4 exists yet to try it on, and every speed below is an
estimate. See [What exists today](../plan/status.md#status-wires).
:::

Needs: a DATA ×4 assembled with its logic. The base assembly (DATA-4x) has no matrix, and a DATA ×6 bay shows
no Wires card.

## Plug the jumper wires, once

```{figure} ../img/pcbs/data-port-x4-headers-front.jpg
:alt: The DATA ×4's four 2 × 6 headers, numbered 1 to 4, each labelled VREF 1 2 3 4 BOOT over GND 5 6 7 8 RST

KiCad render of the DATA ×4 v1.0: one header behind each USB-C port, the names on the silkscreen above it.
```

Each port has a 2 × 6 header: VREF, P1 to P4 and BOOT on the upper row, GND, P5 to P8 and RST on the lower.
The P pins go to the matrix; RESET and BOOT are the port's own lines
([Power-cycle or reset a board](power-and-reset.md#reset-and-bootloader)). Wire a board to the header of its
own port with female to female Dupont jumpers, 20 cm (30 cm where that does not reach), torn off the strip as
a small ribbon, onto the board's own pin headers, soldered pins up. Wire only its signals, each to a P pin,
and VREF (below); no GND wire, the USB cable carries it.

The viewer colours VREF red, RESET brown, BOOT green and GND black (the bill names the same colours for GND,
RESET and BOOT). Take the strip's colours in the order its wires lie onto the pins at both ends, so that they
do not cross, and tie the ribbon down rather than let it pull on the header.

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: Bay B3 pulled out: a XIAO, two Pico 2 and a XIAO on the plate, the DATA ×4 standing at the back, two small ribbons from its headers to the first two boards

The 3D model: bay B3 open, its two three-wire ribbons from ports 1 and 2 to the XIAO and the Pico 2.
```

## VREF and the port's logic level

Each port's eight pins pass through that port's level shifter (an LSF0108), referenced to its VREF pin: wire
VREF to the board's I/O supply, its 3.3 V or 1.8 V pin. The eight pins of a port are one voltage domain, so a
1.8 V board and a 3.3 V board never share a header; a board that needs more than eight pins takes two headers,
both VREFs to its rail. A wired VREF draws VREF / 20 kΩ, 165 µA at 3.3 V.

Logic from 0.95 to 3.6 V is in specification. A 5 V board with TTL inputs (AVR, most 5 V Arduinos) takes VREF
from its own 3.3 V pin: it receives 3.3 V highs, which its inputs read, and the bus stays at 3.3 V. VREF at 5 V
lifts the bus to about 4.0 to 4.2 V, outside the chip maker's conditions but harmless. Strict-CMOS 5 V inputs
are not covered.

A board that is off isolates its pins; an unwired VREF does not. It sits near 0.4 V, where lows still pass
both ways and highs are clipped to about 0.4 V. The guard against it, keeping a port's switches open while its
VREF reads under 0.65 V, needs a reading that a bay node v1.0 does not get (the co-processor that would
measure VREF runs the analyzer, which does not report it). The page shows `VREF ?` and only the port's power
decides. Wire VREF before you put a port's pins on a bus ([Known issues](../reference/known-limitations.md)).

## A UART between B3.1 and B3.2

The XIAO in B3.1 has its UART on D6 (TX) and D7 (RX), the Pico 2 in B3.2 on GP0 (TX) and GP1 (RX). In the
example rack each board has a three-wire ribbon from its own header, red, orange and yellow off the strip, in
the order that lets it lie flat onto the board's pins:

| Header pin | B3.1, a XIAO | B3.2, a Pico 2 |
|---|---|---|
| VREF | 3V3 | 3V3 |
| P1 | D7 (RX) | GP0 (TX) |
| P2 | D6 (TX) | GP1 (RX) |

Read from `population › B3 › jumpers` in [config/rack.yaml](../../config/rack.yaml). Two buses join them:

| Bus | Pins | Carries |
|---|---|---|
| A | B3.1 P1, B3.2 P1 | B3.2's TX (GP0) to B3.1's RX (D7) |
| B | B3.1 P2, B3.2 P2 | B3.1's TX (D6) to B3.2's RX (GP1) |

Buses A to H are also the logic analyzer's channels 1 to 8, so [Logic analyzer](logic-analyzer.md) captures
this UART on the same two buses.

## In the browser

```{figure} ../img/web-ui-wires.png
:class: bb-screenshot
:alt: The Wires card: four port headers with pins coloured by bus, the buses A to H named on the right with their pins, a 1.8 ↔ 3.3 V tag, one pin dashed, Discard, Apply and Open all, the bayctl wire line at the foot

Simulated node, with the simulator's own wiring: a UART each way between B3.2 and B3.3, I²C to a 1.8 V board in
B3.4, SPI. The dashed pin is staged and not applied yet. The simulator reports a VREF for each port, which a
v1.0 node cannot read.
```

The **Wires** card of `http://bay-b3.local/` draws each header as it is printed on the board. Tap a P pin to
put it on a bus (one bus at most per pin), and give the bus a name of up to 23 characters; the node keeps the
names, and the Logic analyzer card names its lanes with them. Changes are staged: **Apply** sends them
together, **Discard** drops them, **Open all** stages every pin off the buses.

A port's pins stay open while the port is off (drawn striped). A tag on a bus marks a 1.8 V and a 3.3 V board
joined (good to about 1 to 2 MHz), a single pin (probe only: the analyzer listens, no other board is joined),
or two pins of one board. Under the card is the `bayctl wire` line that does the same.

## With bayctl

```console
$ python tools/bayctl.py wire B3 A=1:P1,2:P1 B=1:P2,2:P2 --name A="UART B3.2 TX" --name B="UART B3.1 TX"
$ python tools/bayctl.py wire B3
$ python tools/bayctl.py wire B3 --open-all
```

A pin is `<port>:P<pin>`, `<port>:<pin>` or `B3.2:P1`: ports 1 to 4, pins 1 to 8. The pins on the command
line are the whole set from then on: every pin not named goes off the buses. With no argument the command
prints each bus, its name and its pins, a pin held open marked `(held open)`. Every option:
[bayctl](../reference/bayctl.md#wire).

## Over HTTP

```console
$ curl -s bay-b3.local/api/wires
$ curl -s -X POST bay-b3.local/api/wires -d '{"pins": [{"port": 1, "pin": 1, "bus": "A"}, {"port": 2, "pin": 1, "bus": "A"}, {"port": 1, "pin": 2, "bus": "B"}, {"port": 2, "pin": 2, "bus": "B"}], "names": ["UART B3.2 TX", "UART B3.1 TX", "", "", "", "", "", ""]}'
```

A POST with `pins` replaces the whole set: every pin left out goes off the buses, and `"pins": []` opens them
all. The node opens every switch that moves before it closes any. It answers with the same document as the
GET, plus `changed`, the number of switches moved; 400 with the reason for a body it cannot read, 403 without
the control right, 423 when a port whose pins change is reserved by another address
([Reserve a bay](reserve-a-bay.md)). Every field: [Bay node HTTP API](../reference/node-api.md). The node's
shell has no command for the wires.

## What will not pass

The speeds are estimates, to be measured: SPI and SWD about 5 MHz, a UART 3 Mbd, I²C 400 kHz with a 2.2 kΩ
bus pull-up (not 1 MHz). Between a 1.8 V and a 3.3 V board, 1 to 2 MHz, and timing between the two is good to
about 0.5 µs, because the level shifter's pull-up finishes a 1.8 V board's rising edge.

| What | Why |
|---|---|
| I²C between 1.8 V boards with the 2.2 kΩ pull-ups on | Every bus rests at 3.3 V through 10 kΩ; the 2.2 kΩ pull-ups are switched by the co-processor, whose firmware for them is not written. With them on, the design review of 2026-11-09 computes a 1.8 V low of 0.55 to 0.65 V against a limit of 0.54 V; with the 10 kΩ alone, 0.25 to 0.30 V |
| CAN_H and CAN_L | The level shifter clips them to VREF. Logic-level CAN between controllers passes if every board sets its CAN TX pin open-drain (pinctrl `drive-open-drain`), TX and RX of each on one bus: 500 kbit/s, 1 Mbit/s marginal, no CAN FD data phase, two boards at least |
| Two push-pull outputs on one bus | They fight; the 100 Ω on each pin bounds the current to about 9 mA |
| A probe that leaves the line alone | The 10 kΩ pull-up and the bus load the pin; an undriven pin reads high |
| More than eight signals | Eight buses, and the analyzer sees only what is on one |

Why the matrix has these limits: [Why the DATA ×4 is built this way](../data-x4-v2-research.md). A wire that
does not behave: [Troubleshooting](troubleshooting.md).
