# Why it is built this way

BitBunk takes its power from one USB-C charger, finds its bays over CAN, serves their boards over Wi-Fi and
stands on a printed frame. Each choice was weighed against others before the v1.0 PCBs were ordered on
2026-11-11.

:::{status} designed
Every reason below is argued from datasheets, calculations, simulations and the bench stand-ins. None has been
checked on a v1.0 PCB or on a printed frame: the rows of [the frame](../plan/status.md#the-printed-frame) and
of [the five PCBs](../plan/status.md#the-five-pcbs) in What exists today.
:::

| Choice | Weighed against | Evidence |
|---|---|---|
| A printed frame, rows tilted 20° | the aluminium frame of the versions before v0.2 | [mechanical.md](../mechanical.md#frame-the-panel-frame), [stability.md](../stability.md) |
| One USB-C PD charger at 20 V | a 24 V brick in the power box, a mains supply, PoE++ on each row | [power.md](../power.md#options-compared) |
| A TPS26600 eFuse on each row and each DATA lead | | [power.md](../power.md#protection-chain) |
| CAN and a position wire in the row cable | finding the bays over Wi-Fi, or by configuration | [can.md](../can.md#bus), [rack-protocol.md](../rack-protocol.md) |
| JST PH 6 row cables | Cat5e patch cords on RJ45 jacks | [rj45-row-cable-feasibility.md](../rj45-row-cable-feasibility.md), [rj45-row-cable-mechanical.md](../rj45-row-cable-mechanical.md) |
| Wi-Fi to every node | 10/100 Ethernet to every node | [wifi-capacity-ns3.md](../wifi-capacity-ns3.md), [wired-node-mcu.md](../wired-node-mcu.md) |
| An ESP32-S3, USB/IP at 12 Mbit/s | a BL616, an ESP32-S31 | [mcu-alternatives.md](../mcu-alternatives.md), [esp32-s31-research.md](../esp32-s31-research.md) |
| A DATA board in every drawer; a switch matrix and the stock analyzer on the DATA ×4 | one board per node; jumpers moved by hand; an analyzer firmware of the project's own | [multi-dut-node.md](../multi-dut-node.md), [data-x4-v2-research.md](../data-x4-v2-research.md), [coproc-firmware-research.md](../coproc-firmware-research.md) |

The nine design documents (`mechanical.md`, `power.md`, `can.md` and six more) are kept current. The 25 dated
notes record a study or a review as it stood on its day and are not instructions: the banner on each gives its
standing and the page that holds today's answer. They are listed on
[Design notes, studies and reviews](studies.md). The five PCBs' schematics, KiCad projects and fabrication files
are reached from [The five PCBs](../reference/pcbs/index.md); the OpenSCAD sources of the printed parts from
[Get the STL files](../print/stl-files.md).

## A printed frame, tilted 20°

Every part of the structure is printed: no aluminium, and no screws but the rear braces'. The side walls, the
ladders, stand between the bays and are shared by both neighbours, so the grid grows in both directions; trays
slide into the ladders' grooves. An X brace behind every bay keeps the grid square: in
`tools/panel_frame_fea.py` a 4 × 4 grid sways about 8 mm without braces and 0.16 mm under 2 N with taut ones,
so each diagonal is printed 0.25 mm short. The rows lean back 20°, a stadium:
every board, LED and label faces you. A printed rack is light: by calculation for two and four rows (three
were not computed), a pull of 8 to 13 N at the top row tips it forwards, hence
[the screws into the bench](../build/screw-the-rack-to-the-bench.md).

```{figure} ../img/viewer/rack.jpg
:alt: The default rack in the 3D model: four columns, three rows tilted back, the power box under A1

The 3D model of the default 4 × 3 rack: the ladders shared by neighbouring bays, the rows tilted 20°, the power
box under A1.
```

## One USB-C charger, at 20 V

The goal was a rack you plug in: one USB PD charger outside it, one cable, no mains anywhere in the printed
parts. A certified 24 V brick would have needed a bigger power box and a cut and crimped DC cord; an internal
mains supply, a mains enclosure with its own wiring and fusing; PoE++, four Ethernet runs and a PoE++ switch for
nodes that talk over Wi-Fi anyway. The sink on the hub is a WCH CH224A: it negotiates 9 V by itself at plug-in,
keeps the contract through a controller reset, and tells the controller over I²C what the charger offers. It
replaced an AP33772S that was out of stock at LCSC. The rack runs at 20 V from a 100 W charger. 28 V from a
140 W EPR charger is locked out in the firmware (`CONFIG_HUB_EPR_ALLOWED`), whose help still names a 30 V
inductor; the v1.0 PCBs fit 75 V parts, but the review of 2026-11-09 finds no margin at 28 V on the hub, and
the lock stays ([Open questions](../reference/known-limitations.md#open-questions)). The nodes run from 13.5 to
30 V, so a 24 V supply on J1 runs them too.

## An eFuse on each row and each DATA lead

Each of the hub's four row outputs goes through a TPS26600 eFuse limited to 1.6 A, about 32 W a row at 20 V. It
stays off until the controller turns it on, once the charger's contract is final, and soft-starts its row in 16
to 22 ms, so plugging a row in never browns out the others; a shorted bay trips its own row only. Its
back-to-back FETs block reverse current, so the hub needs no input switch, and its IMON pin gives the hub each
row's current, on which the [power budget](../use/power-budget.md) sheds rows. Each bay node has a second
TPS26600 on its DATA lead, limited to 1.76 A and off until the firmware turns it on
([firmware.md › The DATA lead's power-on rule](../firmware.md#the-data-leads-power-on-rule-node-v10)).

## CAN and a position wire in the row cable

A row cable's six wires carry VRACK, ground, a CAN pair and POS, a position line. POS is a token passed from
node to node along the row: it tells each node where it sits, so the hub finds every bay and gives it its place
without Wi-Fi or configuration. The same bus lets the hub power-cycle a hung row. It is a star centred on the
hub's transceiver, one branch per row of at most about 1.5 m, terminated in the hub only: at 250 kbit/s the
ringing of the open ends has died long before the sample point, 3.5 µs after the edge, and a row's end needs no
plug. Each tap is an NXP TJA1462AT, a CAN FD transceiver with signal improvement, passive while its row is off.

## JST PH, not RJ45

A row cable is six single leads of 24 AWG in two PHR-6 housings, pin n to pin 7 − n, so every cable is the same
and a node's J1 and J2 are one footprint turned 180°. A PH contact is rated 2 A on 24 AWG wire only, and no
ready-made 6-pin cable states 24 AWG with this pinout: hence the single leads.

Cat5e patch cords would carry the bus as well: 1.6 A is 0.8 A a conductor on VRACK's pair, and the CAN pair is a
real twisted pair. Misplugging rules them out. 20 to 28 V on an Ethernet port burns the port's termination
resistors within seconds, and the free OUT jack on the last node of every row is live. Making that safe takes
probing on the hub, a switched pass-through on every node and 12 mm of drawer stroke (128 mm instead of 140):
no-go for v1.0, go for a next revision.

## Wi-Fi, not a cable to every node

Wi-Fi in a rack was questioned in review and answered with a model: in ns-3, one channel carries 8 USB/IP
flashes at once at full speed and saturates between 8 and 12, at about 3.2 MB/s. The model is of 8 and 16 bays,
not today's 12; the access point it asks for is on [Wi-Fi in the rack](../use/wifi.md). The cheapest wired node
is the same ESP32-S3 with a W5500 on its SPI bus, $3.87 more a node, because no MCU under the S3's price has a
Zephyr USB host that works through a hub. Bluetooth tests beside the rack's Wi-Fi:
[wifi-coexistence.md](../wifi-coexistence.md).

## An ESP32-S3, and USB at full speed

A node is a USB host that exports its boards over Wi-Fi with Zephyr's USB/IP service, on the DWC2 host driver
that Zephyr has upstream for the ESP32-S3. The BL616 has a high-speed USB controller but no Zephyr USB host
driver. The ESP32-S31 has a high-speed host, an Ethernet MAC and CAN FD, but on 2026-10-22 its Zephyr support
was two draft pull requests with no Wi-Fi, and its modules were out of stock.

The S3 has one full-speed PHY, so through USB/IP every board enumerates at 12 Mbit/s. That carries CMSIS-DAP,
J-Link and ST-LINK probes, UARTs and DFU, and is more than Zephyr's Wi-Fi TCP path carries on the S3 today,
about 4 Mbit/s. A laptop on a bay's front port gets high speed, through an analog switch:
[Front port and classic mode](../use/front-port.md).

## A DATA board in every drawer

The node's one USB host serves a whole drawer through the DATA board at its back: a USB hub chip and four or six
USB-C ports, each switched and metered on the board, which the node drives over I²C on the same 8-wire DATA lead.
A DATA ×6 has six ports and power only. A DATA ×4 has four, and on its logic assembly each port's eight header
pins go through a level shifter (LSF0108) to two CH446Q crosspoints, eight buses in all, closed from the bay's
page: a UART or an I²C bus runs between two boards and nobody touches them again. The crosspoints run on ±5 V,
which halves their resistance and lets I²C pass at 400 kHz. The node, not the co-processor, drives the matrix
and the ports' power, so wires and power survive a co-processor reboot. The co-processor, an RP2350B with no
flash, runs gusmanb's stock LogicAnalyzer from RAM: an analyzer firmware of the project's own was estimated at 4
to 6 thousand lines and 8 to 12 weeks.
