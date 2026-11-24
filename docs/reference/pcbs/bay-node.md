# Bay node

The bay node is the PCB on the tray of each bay. It runs from the row's 20 V. Its ESP32-S3 powers the DATA
board in the drawer, shares the boards' USB over the network and drives the bay's camera.

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
| Module | ESP32-S3-WROOM-1-N8R8 (8 MB flash, 8 MB PSRAM), rated −40 to +65 °C |
| Supply | the row's VRACK on J1, never the USB port |
| Fitted by the fab | all 99 parts: nothing to solder. The footprint of R35 stays empty |

## Connectors

| Connector, as printed | Type | Where | Takes |
|---|---|---|---|
| J1, ROW IN | JST PH 6, side entry (S6B-PH-SM4-TB) | left edge, near the front | the row cable from the hub or from the previous node |
| J2, ROW OUT | the same | right edge, facing J1 | the row cable to the next node |
| J3, PC | USB-C, GCT USB4105-GF-A-120 | front edge | a laptop, through the fascia |
| J5, AUX | JST PH 6, side entry (S6B-PH-SM4-TB) | right edge, behind ROW OUT | an AUX lead to a board with no USB serial |
| J6, CAM | JST PH 8, vertical (B8B-PH-SM4-TB) | rear right, plugged from above | the camera lead |
| J7, DATA | JST PH 8, side entry (S8B-PH-SM4-TB) | right edge, behind AUX | the DATA lead to the DATA board in the drawer |

The node has no USB socket for a board: the USB of every board comes in on the DATA lead. J3, the PC port, is
USB 2.0. A laptop plugged into it is the host, and the node never draws power from it.

```{figure} ../../img/pcbs/bay-node-top.jpg
:class: bb-screenshot
:alt: KiCad render of the top face of the bay node, the names of its connectors printed beside them
:width: 55%

KiCad render of the top face, rear edge up. Down the right edge: CAM, DATA, AUX, ROW OUT. Along the front:
the status LED, the PC port, the SERVICE switch.
```

Every JST lead is a "Same direction" lead ([Cables and pinouts](../cables.md)).

### J1 and J2, the row cable

```{include} ../../can.md
:start-after: <!-- site:row-pinout -->
:end-before: <!-- /site:row-pinout -->
```

J1 has its pin 1 towards the rear. J2 is the same socket turned round, with its pin 1 towards the front. A
node has no CAN termination.

### J7, the DATA lead

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

Pin 1 is not 5 V. It carries the row's voltage behind the node's eFuse, and stays off until the firmware
turns it on. The I²C pair is the node's own bus, with 2.2 kΩ pull-ups to 3.3 V. The node's meter sits on it
at 0x40.

### J6, the camera lead

```{include} ../cables.md
:start-after: <!-- site:camera-lead-pinout -->
:end-before: <!-- /site:camera-lead-pinout -->
```

J6 and J7 take the same kind of lead. Plug each lead into the socket whose name matches. A lead in the wrong
socket harms nothing ([What a wrong cable does](../cables.md#what-a-wrong-cable-does)).

### J5, AUX

```{include} ../cables.md
:start-after: <!-- site:aux-pinout -->
:end-before: <!-- /site:aux-pinout -->
```

:::{warning}
AUX takes the same plug as ROW OUT, 22 mm away on the same edge. On the last node of a row, ROW OUT is
empty and live. An AUX lead pushed into it puts VRACK on its BOOT wire, and into your board.
:::

## Buttons, switch and LED

| Part, as printed | What it is | Where |
|---|---|---|
| SW1, RESET | button on the module's EN | top face, rear left |
| SW2, BOOT | button on IO0 | beside RESET |
| SW3, SVC | SERVICE slide switch | front edge, right of the PC port |
| D4 | status LED, a WS2812B-2020 | front edge, left of the PC port, behind the window in the fascia |

With SERVICE on, the PC port goes to the node's own ESP32, for its console and for
[flashing](../../build/flash.md). The boards' USB is then disconnected. With SERVICE off, a laptop plugged
into the PC port takes over the boards' USB, in hardware. With nothing plugged in, the ESP32 has them
([Front port and classic mode](../../use/front-port.md)). The colours of the LED and what the buttons do are
on [LEDs, buttons and switches](../leds-and-buttons.md).

## Ratings

| | Design value |
|---|---|
| Row input, J1 | 20 V, or 28 V with an EPR contract. Reverse polarity is blocked |
| Through the node, J1 to J2 | the whole row's current: 2 A per JST PH contact. The hub limits a row to 1.6 A |
| 5 V buck | 5.24 V. Starts above 13.5 V, stops below 10.8 V. The node and its camera take under 0.8 A |
| DATA lead supply, J7 pin 1 | the row's voltage through a TPS26600 eFuse, off without firmware |
| DATA lead current limit | 1.76 A (1.67 to 1.85 A). The eFuse retries by itself |
| DATA lead voltage range | off under 15 V and over 31 to 34 V |
| DATA lead meter | INA226 on a 50 mΩ shunt, full scale 1.64 A |
| Camera supply, J6 pin 3 | the 5 V rail through a 0.75 A resettable fuse, which trips at 1.5 A |
| Camera SPI | 3.3 V, mode 0, 4 MHz, 33 Ω in series. For a camera that drives MISO at 5 V, change R33 to 330 Ω and fit R35 (680 Ω) |
| AUX | 3.3 V levels, 1 kΩ in series on TX and RX; RESET and BOOT open drain |
| USB | USB 2.0: High-Speed from the PC port to the DATA lead in classic mode, Full-Speed to the ESP32 |
| POS | each way through 10 kΩ and a clamp: a wrong cable that puts VRACK on it does no harm |

The limits of a whole rack: [Specifications](../specifications.md).

## Test pads

The test pads are bare pads on the bottom face, each with its name printed beside it. The pads for the
supplies, GND and the module's TX and RX are 1.5 mm. The others are 1.0 mm. You cannot reach them once the
node is on its tray, so check the node before you assemble the bay
([Check a bay node](../../build/check-the-pcbs/bay-node.md)).

| Group | Names as printed |
|---|---|
| Supplies, in a row near the front edge | GND, VIN, 5V, 3V3, DATA VIN, CAM 5V |
| Under the module | TX, RX, 3V3, GND, EN, IO0, FLT, ALRT, SDA, SCL, GND |
| Camera SPI, beside them | SCK, MOSI, MISO, CS, GND |
| Rack bus | TXD, RXD, POS IN, GND |
| AUX | AUX TX, AUX RX, RST, BOOT, POS OUT, GND |

VIN is the row's voltage behind the reverse-polarity protection. VRACK itself has no pad: measure it on
pin 1 of J1. FLT is the eFuse's fault output, and ALRT is the meter's alert.

```{figure} ../../img/pcbs/bay-node-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the bottom face of the bay node, with the names of its test pads
:width: 55%

KiCad render of the bottom face, turned over left to right, rear edge up.
```

## Pin map

The pin map of the module, with the net, use and devicetree node of each pin, is in
[firmware/README.md](../../../firmware/README.md#pin-map). On the node v1.0, three values in its Use column
are different:

- the PC_DET divider is 10 kΩ over 18 kΩ
- the pull-down on POS_IN is 150 kΩ
- the alert of the DATA lead trips at 1.5 A (`CONFIG_BAY_PORTS_SHED_MA`)

IO5, IO6 and IO8 are free. IO35 to IO37 belong to the module's PSRAM. The strapping pins IO3, IO45 and IO46
are not used. An ESP32-S3-DevKitC-1 v1.1 (N8R8) takes the same pin map, unchanged.

## Files

| | |
|---|---|
| Schematic | [bay-node-schematic.pdf](../../../electronics/bay-node/docs/bay-node-schematic.pdf) |
| Source and KiCad project | [electronics/bay-node/](../../../electronics/bay-node/), generated from [design.py](../../../electronics/bay-node/design.py) |
| Bill of materials | [bay-node-bom.csv](../../../electronics/bay-node/bay-node-bom.csv) |
| Fabrication files | [bay-node-fab.zip](/downloads/bay-node-fab.zip): Gerbers, JLCPCB's BOM and placement file |
| Outline and positions for the tray | `pcb.bay_node` in [config/rack.yaml](../../../config/rack.yaml) |

At JLCPCB, the order needs two corrections before you pay: D8 in the placement file, and the buck inductor
in the bill. They are listed on
[Order the PCBs](../../plan/order-the-pcbs.md#four-corrections-before-you-pay).

## Known issues

<!-- site:known-issues -->
- A short or an overload on the DATA lead reaches the hub's row limit (1.6 A) before the node's own limit
  (1.76 A). The whole row sags until the node cuts its lead, and the other bays of the row restart.
- Classic mode needs the node's firmware. The DATA lead stays off until the firmware turns it on. With a
  blank or crashed node, the DATA board is dark and a laptop on the PC port sees nothing.
- AUX has no ESD protection, and its levels are 3.3 V. Keep its lead out of ROW OUT (see the warning under
  [J5, AUX](#j5-aux)).
- Plugging a node into a live row makes the row sag. The DATA leads of its neighbours cut out, and a
  neighbour can restart. Switch the row off at the hub before you plug or unplug a row cable.
- Do not plug or unplug the DATA lead while it is powered. Its 20 to 28 V can reach the signal wires first
  and destroy the node's I²C pins, its meter or the USB hub of the DATA board. Switch the bay off first.
- A DATA lead shorted while powered can destroy the node's meter. The node then refuses to power the lead,
  and the bay is out of service.
- With the DATA lead off, the DATA VIN pad can read several volts with nothing plugged in. The eFuse leaks a
  little current into the meter.
- While the camera's light is dimmed, a picture is corrupted now and then. With the light fully on or fully
  off, it is not.
- At power-up, the status LED can show any colour until the firmware sets it.
<!-- /site:known-issues -->
