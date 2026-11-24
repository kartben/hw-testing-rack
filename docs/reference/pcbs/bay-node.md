# Bay node

The bay node is the PCB on each bay's tray: an ESP32-S3 that runs from the row's 20 V, switches and meters
the supply of the drawer's DATA board, carries the boards' USB to the network or to the front port, and
drives the bay's camera.

:::{status} designed
v1.0 has been at the fab since 2026-11-11 and none is on a bench. Every value on this page is the design's, read
from `design.py` and the bill of materials; nothing has been measured.
[What exists today](../../plan/status.md#status-bay-node).
:::

```{figure} ../../img/pcbs/bay-node-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the bay node v1.0, seen from its front left
:width: 60%

KiCad render.
```

| | |
|---|---|
| Revision | v1.0, printed "BAY NODE v1.0 2026-11" on the bottom face |
| Size | 74 × 90 mm, 1.6 mm, 4 layers, lead-free HASL |
| One per | bay, on the tray's standoffs, four M3 holes |
| Module | ESP32-S3-WROOM-1-N8R8 (8 MB flash, 8 MB PSRAM), antenna on the rear edge, rated −40 to +65 °C |
| Supply | the row's VRACK on J1; never the USB port |
| Fitted by the fab | all 99 parts; R35's footprint stays empty on purpose; nothing to solder by hand |

## Connectors and pinouts

| Connector, as printed | Type | Where | Takes |
|---|---|---|---|
| J1, ROW IN | JST PH 6, side entry (S6B-PH-SM4-TB) | left edge, near the front | the row cable from the hub or from the node before |
| J2, ROW OUT | the same | right edge, facing J1 | the jumper to the next node |
| J3, PC | USB-C, GCT USB4105-GF-A-120 | front edge | a laptop, through the fascia |
| J5, AUX | JST PH 6, side entry (S6B-PH-SM4-TB) | right edge, behind ROW OUT | an AUX lead to a board with no USB serial |
| J6, CAM | JST PH 8, vertical (B8B-PH-SM4-TB) | rear right, plugged from above | the camera lead |
| J7, DATA | JST PH 8, side entry (S8B-PH-SM4-TB) | right edge, behind AUX | the DATA lead to the drawer's DATA board |

There is no J4: the node has no USB receptacle for a board, and every board's USB leaves on the DATA lead.
J3, the PC port, is a USB-C sink (5.1 kΩ on each CC line, VBUS only sensed, USB 2.0); the node never
draws its supply from it.

```{figure} ../../img/pcbs/bay-node-top.jpg
:class: bb-screenshot
:alt: KiCad render of the top face of the bay node, the names of its connectors printed beside them
:width: 55%

KiCad render of the top face, rear edge up. Down the right edge: CAM, DATA, AUX, ROW OUT. Along the front:
the status LED, the PC port, the SERVICE switch.
```

All the JST leads are "Same direction": pin n at one end meets pin 7 − n, or 9 − n, at the other. The
tables below come from [Cables and pinouts](../cables.md), with the leads' lengths and what a wrong one
does.

### J1 and J2, the row cable

```{include} ../../can.md
:start-after: <!-- site:row-pinout -->
:end-before: <!-- /site:row-pinout -->
```

J1's pin 1 is towards the rear; J2 is the same socket turned round, its pin 1 towards the front, so every
net crosses the PCB straight. A node carries no CAN termination.

### J7, the DATA lead

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

Pin 1, at the front end of the socket, is not 5 V: it is VIN behind the node's eFuse, off until the
firmware turns it on. The I²C pair is the node's own bus, with its 2.2 kΩ pull-ups to 3.3 V and its meter
at 0x40.

### J6, the camera lead

```{include} ../cables.md
:start-after: <!-- site:camera-lead-pinout -->
:end-before: <!-- /site:camera-lead-pinout -->
```

J6 and J7 take the same lead: plug by the printed names. The pinouts were chosen so that the wrong socket
harms nothing ([What a wrong cable does](../cables.md#what-a-wrong-cable-does)).

### J5, AUX

```{include} ../cables.md
:start-after: <!-- site:aux-pinout -->
:end-before: <!-- /site:aux-pinout -->
```

:::{warning}
AUX takes the same plug as ROW OUT, 22 mm away on the same edge. On the last node of a row ROW OUT is empty
and live: an AUX lead pushed into it puts VRACK on its BOOT wire, and into your board.
:::

## Buttons, switch and LED

| Part, as printed | What it is | Where |
|---|---|---|
| SW1, RESET | tactile button on the module's EN | top face, rear left |
| SW2, BOOT | tactile button on IO0 | beside RESET |
| SW3, SVC | SERVICE slide switch | front edge, right of the PC port |
| D4, no name | status LED, a WS2812B-2020 | front edge, left of the PC port, behind the fascia's window |

With SERVICE on, the PC port goes to the node's own ESP32, for its console and for
[flashing](../../build/flash.md), and the boards' USB is disconnected. With SERVICE off, a laptop plugged
into the PC port takes the boards' USB over by itself, in hardware; with nothing plugged, the ESP32 has it
([Front port and classic mode](../../use/front-port.md)). The LED's colours and what the buttons do, bay
closed or open, are on [LEDs, buttons and switches](../leds-and-buttons.md).

## Ratings

| | Design value |
|---|---|
| Row input, J1 | 20 V; built for 28 V as well (a TVS that stands off 33 V, capacitors rated 50 V). Reverse polarity blocked |
| Through the node, J1 to J2 | the whole row's current: JST PH, 2 A per contact; the hub limits a row to 1.6 A |
| 5 V buck | starts above 13.5 V, stops below 10.8 V; 5.24 V; the node and its camera take under 0.8 A of it |
| DATA lead supply, J7 pin 1 | VIN through a TPS26600 eFuse: limit 1.76 A (1.67 to 1.85 A), retried by itself; off under 15 V and over 31 to 34 V; off without firmware |
| DATA lead meter | INA226 on a 50 mΩ shunt: full scale 1.64 A |
| Camera supply, J6 pin 3 | the 5 V rail through a 0.75 A resettable fuse (it trips at 1.5 A); the camera takes up to 317 mA, its four LEDs up to 102 mA |
| Camera SPI | 3.3 V, mode 0, 4 MHz, 33 Ω in series at the node |
| AUX | 3.3 V levels, 1 kΩ in series on TX and RX; RESET and BOOT open drain; pin 2 is a level reference through 1 kΩ, not a supply |
| USB | USB 2.0. High-Speed from the PC port to the DATA lead in classic mode; Full-Speed to the ESP32 |
| POS | each way through 10 kΩ and a clamp: VRACK on it from a wrong cable costs about 2.5 mA at 28 V |

A rack's limits, port by port and row by row: [Specifications](../specifications.md).

## Test pads

Bare pads on the bottom face, each with its name printed beside it: 1.5 mm for the supplies, GND and the
module's TX and RX, 1.0 mm for the other signals. They are out of reach once the node is on its tray, which is why
[its checklist](../../build/check-the-pcbs/bay-node.md) comes before the assembly.

| Group | Names as printed |
|---|---|
| Supplies, in a row near the front edge | GND, VIN, 5V, 3V3, DATA VIN, CAM 5V |
| Under the module | TX, RX, 3V3, GND, EN, IO0, FLT, ALRT, SDA, SCL, GND |
| Camera SPI, beside them | SCK, MOSI, MISO, CS, GND |
| Rack bus | TXD, RXD, POS IN, GND |
| AUX | AUX TX, AUX RX, RST, BOOT, POS OUT, GND |

VIN is the row's voltage behind the reverse-polarity FET. VRACK itself has no pad: it is on J1's pin 1.
FLT is the eFuse's fault output, ALRT the meter's alert. In the KiCad render the names CS and SCL touch and
POS OUT is cut short: read those pads from the table.

```{figure} ../../img/pcbs/bay-node-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the bottom face of the bay node, with the names of its test pads
:width: 55%

KiCad render of the bottom face, the PCB turned over left to right, rear edge up.
```

## Pin map

The module's pins, from the firmware's README, where
[check_pinmap.py](../../../firmware/tools/check_pinmap.py) holds the table against
[design.py](../../../electronics/bay-node/design.py) and the devicetree, pin by pin and net by net.

```{include} ../../../firmware/README.md
:start-after: <!-- site:pin-map -->
:end-before: <!-- /site:pin-map -->
:relative-docs: ../docs/
```

IO5, IO6 and IO8 are free. IO35 to IO37 belong to the module's PSRAM, and the strapping pins IO3, IO45 and
IO46 are left alone. The map is the one an ESP32-S3-DevKitC-1 v1.1 (N8R8) takes as it is.

The check covers the pin and the net, not the Use column, and three of its cells are older than v1.0. The
divider of PC_DET (IO13) is 10 kΩ over 18 kΩ and the pull-down of POS_IN (IO16) is 150 kΩ in `design.py`;
the firmware's alert on the DATA lead (IO39) is set at 1.5 A on a node v1.0 (`CONFIG_BAY_PORTS_SHED_MA`).

## Files

| | |
|---|---|
| Schematic | [bay-node-schematic.pdf](../../../electronics/bay-node/docs/bay-node-schematic.pdf) |
| Source and KiCad project | [electronics/bay-node/](../../../electronics/bay-node/), generated from [design.py](../../../electronics/bay-node/design.py) |
| Bill of materials | [bay-node-bom.csv](../../../electronics/bay-node/bay-node-bom.csv) |
| Fabrication files | [bay-node-fab.zip](/downloads/bay-node-fab.zip): Gerbers, JLCPCB's BOM and placement file, the content of [electronics/bay-node/fab/](../../../electronics/bay-node/fab/) |
| Positions the tray is drawn around | `pcb.bay_node` in [config/rack.yaml](../../../config/rack.yaml) |
| Reasons | the design log, [electronics.md](../../electronics.md) |

## Known issues of v1.0

From the [design review of 2026-11-09](../../pcb-review-2026-11-09.md) (in French; its finding numbers are
in brackets) and the [schematic review of 2026-10-25](../../schematic-review-2026-10-25.md), calculated or
read from the layout, none measured. Margins that change nothing in use stay in the reviews. The design
review's one major finding on the node was fixed before fabrication (R43, 1 kΩ on the eFuse's fault line).

<!-- site:known-issues -->
- The DATA lead's limit, 1.76 A, sits above the row's 1.6 A and above the meter's 1.64 A full scale. A
  shorted or overloaded DATA lead meets the hub's limit first: the whole row sags until the node cuts its
  lead, and the row's other bays restart. The node cannot read the current at which it limits. [SYS-1]
- Classic mode needs firmware. The DATA lead is off until the firmware turns it on, so a blank or crashed
  node leaves the DATA board dark and a laptop on the PC port sees nothing; with the node unpowered its
  USB switches are open too. Older text promises classic mode "even with no firmware". [BN-07]
- No connector for the front display: the display is a study for a later revision of the node, and its
  window in the drawer's front stays empty.
- AUX and ROW OUT take the same plug, 22 mm apart. An AUX lead in the free ROW OUT of a row's last node
  puts VRACK on its BOOT wire and into your board; no blanking plug exists for that socket. AUX has no ESD
  or level protection either, and its levels are 3.3 V. [BN-08; S3 and S5 of the schematic review]
- Plugging a node into a live row sags the row. By calculation a 20 V row falls to about 10 V with one
  node already on it, 13.3 V with two, 15 V with three: the neighbours' DATA leads cut out, and a lone
  neighbour probably restarts. Switch the row off at the hub before you plug or unplug a row cable.
  [BN-04]
- Plugging or unplugging the DATA lead while it is powered can send its 20 to 28 V through the signal
  wires: the PH connector has no ground contact that mates first. It can destroy the node's I²C pins, its
  meter or the DATA board's upstream USB port. Switch the bay's power off first. [X6-04]
- A DATA lead shorted while powered can destroy the node's meter, whose inputs sit on the lead's supply
  with no series resistor. The firmware wants the meter's answer before it powers the lead: the bay is
  then out of service. [BN-02]
- With the lead off, the eFuse's output leaks up to 12 µA into the meter's 830 kΩ: the DATA VIN pad can
  read several volts with nothing plugged. [BN-13]
- Dimming the camera's light switches about 100 mA with fast edges in the lead that also carries the SPI:
  a corrupted picture now and then is expected while the light is dimmed, none with it fully on or off.
  [BN-09]
- At power-up the status LED may show any colour until the firmware writes it. [BN-11]
- At JLCPCB only: the committed placement file sets the diode D8 0.34 mm off its pads [BN-06], and JLCPCB
  lists the buck's inductor (C48009678) without a footprint: C553961 is the same part on another reel
  [BN-14]. Neither applies to an assembler that reads KiCad's own position file.
<!-- /site:known-issues -->
