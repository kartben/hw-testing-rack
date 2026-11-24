# Specifications

The default rack is 671 × 225 × 619 mm, runs from one 100 W USB-C charger and grants a bay 5.4 W for its DATA
board and its boards, 2.9 W when the bay has a camera.

:::{status} designed
Every figure here is a design value, a computed one or the result of a simulation, and each table says which.
One is a measurement, taken on a bench stand-in. Nothing has been measured on a v1.0 PCB or on a printed frame:
the rows of [the frame](../plan/status.md#the-printed-frame) and of [the five PCBs](../plan/status.md#the-five-pcbs)
in What exists today.
:::

## Size and mass

<!-- site:size-and-mass -->
| | Value | Kind, and where it comes from |
|---|---|---|
| The default rack, 4 columns × 3 rows | 671 × 225 × 619 mm, width × depth × height | computed from [rack.yaml](../../config/rack.yaml): 670.6 × 225.3 × 618.7 |
| What stands on the bench | 671 × 201 mm | the floor contacts of the base, [study of 2026-10-25](../stability.md) |
| One column more | 165.8 mm: a 158 mm tray, a 7.4 mm ladder, two clearances | [rack.yaml](../../config/rack.yaml) |
| Height of a row | 165 mm for rows A and B, 120 mm for row C, over an 80 mm base | [rack.yaml](../../config/rack.yaml) |
| Tilt of the shelves | 20°, front edge lower | [rack.yaml](../../config/rack.yaml) |
| Drawer stroke | 140 mm | [rack.yaml](../../config/rack.yaml) |
| Mass with two rows, 8 bays | 3.7 kg with light boards, 4.7 kg with 160 g in every drawer | computed from the 3D model, [study of 2026-10-25](../stability.md) |
| Mass with four rows, 16 bays | 6.6 kg and 8.8 kg | the same study |
| Printed parts of the default rack | 243 parts; 4.3 kg of PETG by the bill's estimate, 4.7 kg by the slicer's figures: buy 5.1 kg | [Printer, filament, settings](../print/printer-and-settings.md#filament) |
<!-- /site:size-and-mass -->

The mass of the default three rows was not computed: it lies between the two. By the same study, a pull of 8
to 13 N at the top row tips a rack of two or four rows forwards (three were not computed):
[Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md).

## Chargers and what each feeds

The bill names an Anker Nano 100 W (A2679): an example of the kind, not a tested part.

<!-- site:charger-table -->
| Charger | Cable | What the rows get |
|---|---|---|
| **The default:** a dedicated, single-port USB PD charger, 100 W (20 V × 5 A) | USB-C to USB-C, 5 A e-marked (rated 100 W or 240 W), 1 to 2 m | 20 V; 4.5 A, 90 W |
| The same charger on a 3 A cable | no e-marker: above 3 A a charger only offers its full current through an e-marked 5 A cable | 20 V; 2.7 A, 54 W |
| A single-port 65 W charger (20 V × 3.25 A) | 5 A e-marked; on a 3 A cable, as the line above | 20 V; 2.9 A, 58 W: a light rack, the hub sheds rows when they ask for more |
| A single-port USB PD 3.1 EPR charger, 140 W (28 V × 5 A) | rated 240 W | today the same as the default: 28 V is locked out in the hub's default build |
| A multi-port charger | | avoid: it can withdraw its full offer when another device is plugged in, and the rack restarts or loses rows |
| A charger that offers no more than 12 V | | nothing: the rows need a contract of 15 V or more |

Design values: no charger has been tried on a hub. What the rows get is the contract less the 10 % the hub
keeps free.
<!-- /site:charger-table -->

The rule and its thresholds are on [Power budget and queued ports](../use/power-budget.md); the 65 W line is
that rule applied to 3.25 A. Why USB PD, and why this sink: [Power](../power.md#options-compared).

## Voltages

<!-- site:voltages -->
| Where | Value | Kind, and where it comes from |
|---|---|---|
| VRACK, on every row cable | 20 V: the charger's own output, with no switch at the hub's input | design, [power.md](../power.md) |
| 28 V (EPR) | locked out in the hub's default build, although the v1.0 bills of materials give every buck inductor on VRACK a 75 V rating | the switch is `HUB_EPR_ALLOWED`, off, in [the hub's Kconfig](../../firmware/power-hub/Kconfig); the inductors: [bom/sourcing.md](../../bom/sourcing.md) and each PCB's `design.py` |
| At plug-in, and on a hub with no firmware | 9 V, and every row off | design |
| A row is switched on | with a contract of 15 V or more that has held 500 ms; the rows follow 300 ms apart | [the hub's Kconfig](../../firmware/power-hub/Kconfig), tested on native_sim |
| What the hub never asks for | more than 28 V; it never accepts 36 V or 48 V | design |
| A row's eFuse and a DATA lead's eFuse cut out | under 15 V, and above 31 to 34 V | design: the TPS26600's lockouts |
| A bay node runs | from 13.5 to 30 V: its buck starts above 13.5 V and stops below 10.8 V | design |
| DATA lead, pin 1 | VRACK, switched by the node: 20 V, not 5 V | design |
| A node's rails | 5.24 V (5.1 to 5.4 V) and 3.3 V (3.2 to 3.4 V) | design |
| A DATA board's 5 V | 5.08 V (4.94 to 5.22 V) | design |
| VBUS at a DATA port | 4.94 to 5.08 V on a DATA ×6, 4.82 to 5.22 V on a DATA ×4 | design |
<!-- /site:voltages -->

"Design" rows are the values of each PCB's `design.py` under [electronics](../../electronics/); the
[checklists](../build/check-the-pcbs/index.md) measure them for the first time.

## Current per port, per bay, per row

<!-- site:current-limits -->
| Where | Limit | Kind, and where it comes from |
|---|---|---|
| One DATA port, 5 V to one board | 0.52 to 0.64 A; count on 0.5 A | design: the port's switch, on both DATA boards |
| One DATA lead, a whole bay at VRACK | ≈ 1.76 A (1.67 to 1.85 A): the node's eFuse | design, [the node's design.py](../../electronics/bay-node/design.py) |
| What the node can measure on that lead | 1.64 A full scale | design: an INA226 on a 50 mΩ shunt |
| The node's firmware, before its eFuse | a port is shed above 1.5 A on the lead; with no grant from the hub the bay is kept under 25 W | [the node's Kconfig](../../firmware/bay-node/Kconfig), tested on native_sim |
| One row | 1.6 A (1.52 to 1.68 A): the hub's eFuse, ≈ 32 W at 20 V | design, [the hub's design.py](../../electronics/power-hub/design.py) |
| A contact of a row cable | 2 A, on 24 AWG only | JST's rating of the PH series |
| The whole rack | the contract's 5 A, of which the hub leaves the rows 4.5 A | design, [power.md](../power.md#keeping-the-rows-inside-the-contract) |
| A camera and its light | ≤ 0.42 A at 5 V, behind a 0.75 A resettable fuse | design |
| A DATA board with every port at its limit | ≤ 1.3 A at 20 V for a DATA ×6, ≤ 0.92 A for a DATA ×4 | design |
<!-- /site:current-limits -->

The hardware cuts at these. What a bay may draw day to day is smaller: the hub's grant, in the next section.

The three limits of a bay's supply are not in order, a known issue of v1.0 (finding SYS-1 of the
[review of 2026-11-09](../pcb-review-2026-11-09.md)). The DATA lead's 1.76 A sits above the row's 1.6 A and
above the 1.64 A the node can measure, so a shorted or overloaded DATA lead meets the hub's limit before its
own: the row sags until the node cuts the lead, and the other bays of the row restart. How a short plays
out is still to be measured ([Known issues](known-limitations.md)).

## A bay's share, by number of columns

The hub grants each bay an equal share of its row's 1.6 A, less the 10 % margin, at the contract's voltage,
less what the node draws itself: 1.8 W, and 2.5 W more with a camera. The grant is for the DATA lead: the DATA
board and its boards.

<!-- site:bay-share -->
| Columns | Share of the row | A bay's grant | With a camera |
|---|---|---|---|
| 2 | 14.4 W | 12.6 W | 10.1 W |
| 3 | 9.6 W | 7.8 W | 5.3 W |
| 4, the default | 7.2 W | 5.4 W | 2.9 W |
| 5 | 5.8 W | 4.0 W | 1.5 W |

Computed with the hub's own rule for the default 100 W charger (20 V × 5 A), a 10 % margin and one to three
rows. The rule is tested on native_sim; no hub has sent a grant yet.
<!-- /site:bay-share -->

The rule is `budget_grant_mw()` in [budget.c](../../firmware/power-hub/src/budget.c), and the constants are in
[the hub's Kconfig](../../firmware/power-hub/Kconfig). The hub takes the smaller of two shares: the row's, above,
and the contract's, 90 W divided by the bays of the rows that are on. With one to three rows the row's share is
the smaller, so the width of the rack sets a bay's power, not its number of bays. Two cases turn it round:

- four rows of four on the 100 W charger: 90 W ÷ 16 bays, less 1.8 W, is 3.8 W a bay;
- twelve bays on a 3 A cable: 54 W ÷ 12, less 1.8 W, is 2.7 W a bay.

A DATA board's own draw comes out of its bay's grant: ≈ 2.1 to 2.6 W for a DATA ×6 with its converter, 2.3 to
3.0 W for a DATA ×4 (estimates of [power.md](../power.md#budget) and
[One node, several boards](../multi-dut-node.md#power-budget)). What is left for the boards is worked through on
[Choose a size, change the layout](../plan/choose-your-rack.md).

## USB

| | Value | Kind, and where it comes from |
|---|---|---|
| Ports of a bay | 6 USB-C on a DATA ×6, 4 on a DATA ×4 | design |
| Speed over USB/IP | 12 Mbit/s (full speed), shared by the boards of a bay: the node's ESP32-S3 has one full-speed host port | design |
| Speed in classic mode, a laptop on the front port | high speed: the path is a 480 Mbit/s analogue switch, and the laptop sees the DATA board's hub | design |
| One mass-storage read over USB/IP | 820 kB/s | bench: a XIAO ESP32-S3 stand-in on Wi-Fi, [the node's Kconfig](../../firmware/bay-node/Kconfig) |
| A port's supply | 5 V, 0.5 A to count on | design, above |

What USB will not do through the rack is on [Known issues, and what will not work](known-limitations.md).

## Sessions, clients and flashes at once

<!-- site:capacity -->
| What | How many at once | Kind, and where it comes from |
|---|---|---|
| Boards in a bay | 6 behind a DATA ×6, 4 behind a DATA ×4 | design |
| USB/IP sessions on one node | 6, one per device | [the node's Kconfig](../../firmware/bay-node/Kconfig), `USBIP_DEVICES_COUNT` |
| USB/IP flashes on one Wi-Fi channel | 8 at full speed; the channel saturates between 8 and 12 | simulated: [ns-3 study of 2026-10-24](../wifi-capacity-ns3.md), models of 8 and 16 bays; nothing enforces it |
| Connections to a bay's page and API | 6; an idle one is dropped after 3 s | [the node's prj.conf](../../firmware/bay-node/prj.conf) |
| Browsers on a bay's serial console | 2 | [the node's Kconfig](../../firmware/bay-node/Kconfig), `BAY_CONSOLE_WEB_CLIENTS` |
| Clients of the AUX UART over the network | 1 on RFC 2217 (TCP 4001) and 1 on raw TCP (TCP 4000) | [the node's Kconfig](../../firmware/bay-node/Kconfig) |
| Telnet shells on a node | 1 | Zephyr's telnet backend refuses a second client; the comment in [the node's Kconfig](../../firmware/bay-node/Kconfig) counts one |
| Clients of a bay's camera | 3, at 5 frames a second at most | [the node's Kconfig](../../firmware/bay-node/Kconfig), `BAY_CAMERA_CLIENTS` |
| Connections to the hub's page and API | 6 | [the hub's prj.conf](../../firmware/power-hub/prj.conf) |
| Events the hub keeps | the last 32, in RAM | [the hub's Kconfig](../../firmware/power-hub/Kconfig), `HUB_EVENTS` |
| Rows, and bays in a row, on the rack bus | 4 rows, 15 places in each | [rack_proto.h](../../firmware/common/include/hwtr/rack_proto.h) |
<!-- /site:capacity -->

The counts are build-time defaults. Eight flashes at once is a rule for whoever schedules the jobs: the reason,
and what halves it, are on [Wi-Fi in the rack](../use/wifi.md). Ports, names and metrics are on
[Network ports, names, metrics](network.md).

## Logic levels of a DATA ×4's pins

| | Value | Kind, and where it comes from |
|---|---|---|
| P1 to P8 of a port | the board's own logic level, 0.95 to 3.6 V, set by the port's VREF pin | design, [DATA ×4](pcbs/data-x4.md#the-pin-header-and-vref) |
| VREF | the board's I/O supply, 1.8 or 3.3 V; a 5 V board with TTL inputs gives its own 3.3 V pin | design |
| In series with each pin | 100 Ω | design |
| The buses A to H inside the DATA ×4, and its analyzer | 3.3 V, each bus pulled up by 10 kΩ | design |
| RESET and BOOT of a port | open drain through 1 kΩ, against the board's own pull-up of 4.7 kΩ or more | design |
| A 5 V board with strict CMOS inputs | not guaranteed | design |
| AUX, on the node's J5 | 3.3 V through 1 kΩ, no level shifting and no ESD protection | design, [schematic review](../schematic-review-2026-10-25.md), S5 |

A DATA ×6 has no pins. What passes through the pin matrix and what does not is on
[Wires between boards](../use/wires.md).

## The largest rack

| Limit | Value | Why |
|---|---|---|
| Rows | 4 | the hub has four row outputs, A to D; the default rack uses three |
| Bays in a row | 15 on the rack bus; power stops it well before | a fifth column leaves each bay 4.0 W, a DATA board alone takes 2.1 to 3.0 W |
| Height of a row | 165 mm | a 185 mm row takes a 258.8 mm ladder, too long for a 256 mm bed |
| Width of a bay | 158 mm, one size | a double-width bay is not designed |
| Charger | 100 W | the 140 W, 28 V option is locked out |

The Wi-Fi study models 8 and 16 bays and the stability study 2 and 4 rows; neither models the default 12 bays
in 3 rows. The sizes and what each changes are on [Choose a size, change the layout](../plan/choose-your-rack.md).
