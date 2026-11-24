# What exists today

Nobody has built a BitBunk yet. On 2026-11-24 the project stands here:

- The printed frame is at v0.2. No part of it has been printed.
- Five PCBs went to fabrication at v1.0 on 2026-11-11. None is on a bench.
- The firmware builds. Its tests run in simulation, and parts of it have run on bought ESP32-S3 boards that
  stand in for the PCBs. It has never run on a bay node or on a power hub.

So every size, mass and print time on this site comes from CAD or from a slicer, every voltage and current
from a schematic or a datasheet, and no picture is a photograph. The tables below say how far each thing has
been taken. What will not work whatever is tested, and what the v1.0 PCBs are already known to do wrong:
[Known issues, and what will not work](../reference/known-limitations.md).

## Who should start now

Anyone with a printer can print the frame today: the STL files are in the repository. Nobody sells a kit or
assembled PCBs: you order them from a fab, as the project did on 2026-11-11 (5 PCBs of each, 2 of them
assembled), and they arrive as PCBs that nobody has powered before. The checklists of
[Check each PCB](../build/check-the-pcbs/index.md) are first-article inspections, and whoever orders today
does them. What else the build asks of you: [The build, stage by stage](stages.md#what-it-asks-of-you).
With nothing on the desk, the 3D model, a simulated bay and `bayctl` already run:
[Try it without hardware](try-it-without-hardware.md).

## The six levels

Every page about something untested opens with a status line at one of six levels, and its text links to a
row below.

| Level | The status line reads | It means |
|---|---|---|
| hardware | Verified on the v1.0 boards | measured or run on the fabricated PCBs, or on printed parts. No row says it today |
| bench | Run on bench stand-ins | ran on a bought ESP32-S3 board with the project's firmware: a XIAO ESP32-S3, an M5Stack CoreS3 |
| simulated | Tested in simulation | tests on Zephyr's native_sim or on a PC, or a tool against the simulated node |
| written | Written, not tested yet | the code exists and builds |
| designed | Designed, not built yet | printed parts, and PCBs before their first power |
| planned | Planned | not designed, or not written |

The date that ends a row is that of the last review, test or measurement it rests on.

## The printed frame

| What | Level | What has been checked, and how |
|---|---|---|
| [Frame]{#status-frame}: ladders, plates, braces | designed | The 30 parts that existed then, sliced in Bambu Studio for an H2D, in PETG; what the slicer asked for is in, and every part is drawn to print without supports. Every snap by formula and by FEM. Nothing printed (2026-10-21) |
| [Tray and drawer]{#status-bay}, drag chain, DATA board cradle | designed | One assembled bay checked for interference on exact solids; the chain, the drawer and the bay node over the 140 mm stroke. The chain's outer size comes from a seller's listing and its bend radius is not published: [measure before you print](../print/index.md) (2026-11-01) |
| [Board plate and pegs]{#status-plate}, the layout tool | designed | `tools/plate_layout.py` places every board of the example rack, and its test runs in CI. No peg has been clipped into a plate. A board marked `verified: false` in the library has an approximate outline (2026-11-01) |
| [Slot bin]{#status-slot-bin} of a dense bay | designed | Fit checked in CAD with the drawer, the DATA ×6, six plugs and the largest board in every lane. Not in the slicer review, which is older (2026-11-01) |
| [Camera pod]{#status-pod}, power box | designed | In the reviews above. The pod's sleeve waits for the camera's real case (2026-10-21) |
| [Stability]{#status-stability} | designed | Computed for 2 and 4 rows, not for the default 3: a pull of 8 to 13 N at the top row tips the rack forwards, hence [the screws into the bench](../build/screw-the-rack-to-the-bench.md) (2026-10-25) |
| [One bay on a desk]{#status-standalone}: Quad, desk frame, Solo | designed | Fit checked in CAD, sliced without supports. The Solo is not to be built with a bay node v1.0: [open questions](../reference/known-limitations.md#open-questions) (2026-11-02) |

The two print reviews: [design](../printed-parts-review.md) and [slicer](../printed-parts-fdm-review.md).
The parts added since (the slot bin, the taller drawer front, the DATA ×6's place in the cradle) carry
their own figures in [mechanical.md](../mechanical.md).

## The five PCBs

v1.0 of all five went to NextPCB on 2026-11-11 and is frozen: a change now takes a new revision.

```{include} ../electronics.md
:start-after: <!-- site:revisions-at-the-fab -->
:end-before: <!-- /site:revisions-at-the-fab -->
```

What each went through before the order, on paper only:

| PCB | Level | Checked before the order |
|---|---|---|
| [Power hub]{#status-power-hub} | designed | ERC and DRC clean. Schematic review, datasheet audit, design review: no major finding (2026-11-09) |
| [Bay node]{#status-bay-node} | designed | The same three. One major finding, fixed before fabrication (a 1 kΩ resistor, R43). Its DATA lead's eFuse was audited as the chip of an earlier design (2026-11-09) |
| [Camera pod]{#status-camera-pod} | designed | The same three: no major finding (2026-11-09) |
| [DATA ×6]{#status-data-x6} | designed | Drawn on 2026-10-31, after the schematic review and the audit: the design review only. Two fixes before fabrication: copper under the 3.3 V regulator, and its 5 V set to 5.08 V (2026-11-09) |
| [DATA ×4]{#status-data-x4} | designed | Schematic review, its own datasheet audit, design review. One fix before fabrication: ground vias under the co-processor (2026-11-09) |

The design review of 2026-11-09 lists 65 findings and no error of pinout, polarity or connection. What it
left open is the list of known issues of [each PCB](../reference/pcbs/index.md). The expected values in the
checklists are the design's: the first PCB measured sets the reference for the second.

## Firmware, feature by feature

Firmware 0.5.0 for the bay node and the power hub. "The XIAO" is a Seeed XIAO ESP32-S3 running the bay
node's firmware on the bench; its measurements are in [bench.md](../bench.md), the open items in
[firmware.md](../firmware.md).

| Feature | Level | What ran, and on what |
|---|---|---|
| [USB/IP]{#status-usbip}: a board's USB on a Linux machine | bench | On the XIAO, with a bought USB hub in a DATA board's place: three sessions at once, a serial converter read without loss at 115200 Bd, a Pico 2 loaded with `picotool`. The rack's patch to Zephyr's USB/IP on native_sim. Never through a DATA board. A 15-minute soak with several boards did not complete (2026-11-03) |
| [Debugging over USB/IP]{#status-debug}: `west debug`, GDB, RTT | written | Not tried: nothing is recorded (2026-11-24) |
| [Power, reset, bootloader]{#status-power} of each port | simulated | The DATA ×4's and the DATA ×6's ports on native_sim against emulated PCBs, and the DATA lead's power-on rule. `bayctl` against the simulated node (2026-11-11) |
| [Power budget]{#status-budget}: grants, queued and shed ports, shed rows | simulated | The bay's side and the hub's side on native_sim, with made-up contracts. No charger, no real load (2026-11-11) |
| [The three modes]{#status-modes}: USB/IP, classic, SERVICE | written | No stand-in has the two USB switches: classic mode has never run. On the stand-ins SERVICE is a jumper wire (2026-11-09) |
| [Serial console]{#status-console} of the AUX UART | simulated | The RFC 2217 server against pyserial on a PC; the web console on native_sim with a Zephyr board. On the XIAO over Wi-Fi the web console connects. RFC 2217 and raw TCP over Wi-Fi: no result recorded (2026-11-01) |
| [Wires]{#status-wires}: the DATA ×4's pin matrix | simulated | On native_sim against two emulated crosspoint chips: each switch, break-before-make, a port off and on. No DATA ×4 exists to try it on (2026-11-03) |
| [Logic analyzer]{#status-analyzer} and its co-processor | bench | On the XIAO with a Pico 2 in the co-processor's place: the image loaded into RAM, captures from the bay's page and from `bayctl capture`, UART and I²C decoded. *Capture and reset* on the simulated node only (2026-11-04) |
| [Camera]{#status-camera} | simulated | The page against a simulated camera, the frame cutter against real JPEGs on a PC. No camera has been on a bay node's SPI (2026-10-19) |
| [Access rules]{#status-access} and [reservations]{#status-reserve} | simulated | The rules on a PC, claims, signed requests and reservations on native_sim and on the simulated node. A claim by a press on BOOT on the XIAO. The filter that drops refused connections is built and has never run (2026-11-11) |
| [Board targets]{#status-board-targets} | simulated | On native_sim and on the simulated node (2026-10-23) |
| [Update over the network]{#status-update} | bench | Update and rollback on the XIAO over Wi-Fi: 1053 KB sent in 21 to 23 s, the XIAO back 58 to 59 s after the start and confirmed 6 s later. Still to check on a bay node: its larger slots, the rack bus in the trial, a power cut during the swap (2026-11-03) |
| [Rack bus]{#status-rack-bus}: places, addresses, the hub's commands | simulated | Hub and nodes on a simulated rack: enumeration, restarts, dead and lost nodes. The CAN transceiver and the POS chain over real row cables are untested (2026-11-01) |
| [Names on the network]{#status-names}: mDNS, DNS-SD | simulated | DNS-SD on native_sim; the `.local` names in use on the stand-ins (2026-10-23) |
| [The bay's page]{#status-bay-page}, its API, shell and metrics | bench | Loads whole from the XIAO over Wi-Fi. The cards of a bay with a DATA board: on the simulated node only (2026-11-11) |
| [The rack's page]{#status-rack-page}, the hub's API and shell | simulated | The page and `bayctl` against the simulated hub. The page also loads whole from a XIAO that runs the hub's firmware (2026-11-01) |
| [USB-C PD and the rows]{#status-pd}: contract, eFuses, faults | written | Builds. The stand-ins have a bench plan with a real charger, and no result of it is recorded (2026-11-01) |
| [Wi-Fi with a full rack]{#status-wifi} | simulated | Two models, for 8 and 16 bays, not the default 12: one channel carries 8 boards flashed at once; a board's Bluetooth link loses throughput, never the connection (2026-10-24) |
| [Status LED]{#status-led}, buttons | written | The firmware drives them. The colours have not been seen on a bay node (2026-10-20) |

## Host tools and CI

| What | Level | What ran, and on what |
|---|---|---|
| [bayctl]{#status-bayctl} | simulated | Its tests run in CI against the simulated node. `update`, `access claim`, `capture` and `coproc load` also ran against the XIAO. Never against a rack (2026-11-04) |
| [Twister]{#status-twister}: the hardware map | simulated | CI builds a map from the example lab file at every push. `west twister --device-testing` has never run against a bay (2026-11-11) |
| [labgrid and LAVA]{#status-labgrid}: the generated files | written | The two exports are covered by `bayctl`'s tests. Neither file has been given to labgrid or to PDUDaemon (2026-11-11) |
| [A whole CI job]{#status-ci}, from checkout to results | written | Worked out from the tool and the documents: nobody has run one (2026-11-24) |

The tools that turn `config/rack.yaml` into printed parts, the bill of materials and the 3D model
(`build.py`, `plate_layout.py`, `bom.py`) need no rack. They run today and their tests run in CI.

## What the pictures on this site are

Each caption says which of these a picture is:

| The caption says | What it is |
|---|---|
| The 3D model | a still of the project's [3D viewer](/viewer/), which is generated from `config/rack.yaml` and shows the rack as it is designed today |
| Render | a Blender picture in `docs/img/`, rendered in October 2026. The large ones show the earlier layout of two rows and eight bays, and the power box picture shows hub v0.5 |
| KiCad render | one of the five PCBs at v1.0 |
| Simulated node, simulated hub | a screenshot of the bay's page or of the rack's page, served by the simulators. Most show a bay with one board at 5 V, a form that only the stand-ins and the simulator have |
| nothing, beside a build step | a line drawing of the assembly notice, drawn on 2026-10-20. A build page uses one only where the step still matches the design |

## What is not designed

Four things a reader may expect have no design at all:

- a double-width bay and a row taller than 165 mm ([what fits a bay](../reference/known-limitations.md#by-design-mechanics-and-power));
- a front display on each drawer: the firmware can drive one, the printed front has its window, and the
  bay node v1.0 has no connector for it;
- a blanking plug for the last ROW OUT of a row;
- a camera mast for a bay on a desk.

Four more are studies, with nothing built or written: an update sent to every node over the rack bus
([firmware.md](../firmware.md)), an SWD probe through the DATA ×4's pin matrix
([debug-probe-research.md](../debug-probe-research.md)), microamp power profiling
([power-profiling-research.md](../power-profiling-research.md)) and a wired node
([wired-node-mcu.md](../wired-node-mcu.md)).

When a bench finds something this page does not say, it goes to
[Report a finding](../reference/known-limitations.md#report-a-finding).
