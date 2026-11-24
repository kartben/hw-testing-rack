# Design notes, studies and reviews

Twenty-five dated notes record the studies, reviews and audits made while BitBunk was designed, from 2026-10-16
to 2026-11-09. Each stays at its path under `docs/` as it was written, and none is an instruction for building
or using the rack.

## How to read a dated note

A note says what was known, measured, decided or proposed on its date. Later changes are not carried back into
it, apart from a few status lines at the top of some notes. The banner above each note gives its date, its kind,
its standing today and the page that holds today's answer: follow that page.

| Kind | What it is |
|---|---|
| study | a calculation, a simulation or a model, made to answer one question |
| review | a pass over a design, or over every part of a kind, with numbered findings |
| audit | each part checked against its datasheet, or against its source and price |
| research | an option for a later revision; usually not built |

| Standing | What it means |
|---|---|
| applies | its result still holds, within the limits the banner names |
| applied | its decisions are in the design; its figures may be older than the design |
| superseded | it describes PCBs, parts or a rack that no longer exist |
| not built | an option that was studied and left for later |

Where a note and a page of this site disagree, the page wins, and the code and `config/rack.yaml` win over both.
Five things in the notes mean something else today:

- Nothing in them was measured on a v1.0 PCB or a printed part. A temperature, a speed or a margin in a note is
  calculated, simulated or read from a datasheet.
- "DATA ×4 v2" is today's DATA ×4 v1.0, and its "v1" is a first design that was never ordered. The single DATA
  port board they mention left the rack on 2026-10-31, and the co-processor they call RP2354B is an RP2350B since
  2026-11-03.
- Rack sizes, counts and prices are often those of an 8-bay rack of two rows, and of JLCPCB in October 2026. The
  v1.0 PCBs were made by NextPCB.
- They were written as reports of a working session: "the user" is the project's owner, and "the session",
  "Mechanics" or "Électronique" name who did a piece of work. Quotes in French are the owner's.
- Several studies name scripts or results that are not in the repository. Only the two Wi-Fi studies
  ([tools/ns3-wifi-capacity](../../tools/ns3-wifi-capacity/README.md),
  [tools/bsim-wifi-coex](../../tools/bsim-wifi-coex/README.md)) and the printed-parts prototypes
  ([mechanical/review](../../mechanical/review)) can be run again from a checkout.

The dated notes are left out of the site's search and reached from the tables below. The nine design documents
kept current (`mechanical.md`, `electronics.md`, `power.md`, `can.md`, `rack-protocol.md`, `firmware.md`,
`multi-dut-node.md`, `bench.md`, `boards-3d.md`) are in the search and are not listed here. The main choices, a
few lines each: [Why it is built this way](index.md).

## Printed parts and frame

Both reviews of 2026-10-21 count for a 2 × 4 rack, and the slicer's saw the 30 parts of that day; the drawer
front, the cradle widened for the DATA ×6 with its strip, and the slot bin came later.

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [Printed parts: design review](../printed-parts-review.md): snaps, overhangs, fasteners and looks of every part, 17 findings | 2026-10-21, review | Mostly applied; counts are for a 2 × 4 rack | [Inserts and square nuts](../print/inserts-and-nuts.md) |
| [Printed parts: what the slicer says](../printed-parts-fdm-review.md): every STL through Bambu Studio for an H2D, time and grams per part | 2026-10-21, review | Decisions applied; figures predate several parts | [Printer, filament, settings](../print/printer-and-settings.md) |
| [Can the rack tip over?](../stability.md): the forces that tip it, and eight screws into the bench | 2026-10-25, study | Applies; computed for 2 and 4 rows, not the default 3 | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |

## Power and row wiring

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [Row wiring and a shorter hub](../power-distribution-review.md): what a row cable carries, the hub in 100 mm | 2026-10-20/21, study and decision record | Applied; its load table is the old 5 V path | [Make the row cables](../build/row-cables.md) |
| [Row bus on RJ45: electrical](../rj45-row-cable-feasibility.md): the row bus on Cat5e patch cords | 2026-10-22, research | Not built: no-go for v1.0, go for a next revision | [JST PH, not RJ45](index.md#jst-ph-not-rj45) |
| [Row bus on RJ45: mechanical](../rj45-row-cable-mechanical.md): jacks in the tray, cords made to length | 2026-10-22, research | Not built | [JST PH, not RJ45](index.md#jst-ph-not-rj45) |
| [Microamp power profiling](../power-profiling-research.md): current traces for Zephyr low-power tests | 2026-10-21, research | A plan, untested | [Specifications](../reference/specifications.md) |

## DATA ×4: wires and analyzer

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [Why the DATA ×4 is built this way](../data-x4-v2-research.md): the matrix, the level shifters, the co-processor, two assemblies | 2026-10-19/20, research and decision record | Applied; its first half describes a board never built | [Wires between boards](../use/wires.md) |
| [A standing board: layout options](../data-x4-v2-layout-options.md): a deeper, standing or stacked board | 2026-10-20, study | Option B was built; prices and connector superseded | [DATA ×4](../reference/pcbs/data-x4.md) |
| [Pin headers: usability review](../data-x4-logic-usability-review.md): one header per port, the groups as voltage domains | 2026-10-20, review | Applied 2026-10-21 | [Wires between boards](../use/wires.md) |
| [The co-processor's firmware](../coproc-firmware-research.md): the stock analyzer first, a Zephyr firmware later | 2026-10-19, note of 2026-11-03; research and decision record | Day one implemented; the rest planned | [Logic analyzer](../use/logic-analyzer.md) |
| [An SWD probe through the matrix](../debug-probe-research.md): a CMSIS-DAP probe on the co-processor | 2026-10-21, research | Not built | [USB/IP and flashing](../use/usb-and-flashing.md) |

## Wi-Fi and the node's MCU

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [How much one Wi-Fi channel carries](../wifi-capacity-ns3.md): one rack's Wi-Fi in ns-3 | 2026-10-24, study (simulation) | Applies; models 8 and 16 bays | [Wi-Fi in the rack](../use/wifi.md) |
| [Rack Wi-Fi and the boards' Bluetooth](../wifi-coexistence.md): a BLE link beside the rack, in BabbleSim | 2026-10-24, study (simulation) | Applies; its proposals are not the firmware's defaults | [Wi-Fi in the rack](../use/wifi.md) |
| [Another MCU for the node?](../mcu-alternatives.md): the BL616 against the ESP32-S3 | 2026-10-16, research | Not built | [An ESP32-S3, and USB at full speed](index.md#an-esp32-s3-and-usb-at-full-speed) |
| [The ESP32-S31](../esp32-s31-research.md): a high-speed USB host for the node | 2026-10-22, research | Not built | [An ESP32-S3, and USB at full speed](index.md#an-esp32-s3-and-usb-at-full-speed) |
| [A wired node](../wired-node-mcu.md): Ethernet on every node, and its MCU | 2026-10-24, research | Not built | [Wi-Fi, not a cable to every node](index.md#wi-fi-not-a-cable-to-every-node) |

## PCB reviews before the order

Oldest first. Only the last one reviews the PCBs that were fabricated.

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [Node and hub, rev 0.2 to 0.5](../review-konnect.md): findings and fixes, then the change log of 18 and 19 October | 2026-10-16 to 10-19, review | Superseded: it reviews revisions that no longer exist | [The five PCBs](../reference/pcbs/index.md) |
| [Assembly review](../pcba-review.md): five boards checked before an order at JLCPCB | 2026-10-19, review | Superseded: another set of PCBs, JLCPCB only | [Order the PCBs](../plan/order-the-pcbs.md) |
| [Datasheet audit: node, hub, camera pod](../datasheet-audit.md): each main IC against its datasheet | 2026-10-24, audit | Fixes applied 2026-10-25; the node's U9 section no longer matches the PCB | [Check each PCB](../build/check-the-pcbs/index.md) |
| [Datasheet audit: DATA ×4](../datasheet-audit-data-x4-v2.md): the same for the DATA ×4 | 2026-10-24, audit | Fixes applied 2026-10-25 | [DATA ×4](../reference/pcbs/data-x4.md) |
| [Schematic review](../schematic-review-2026-10-25.md): every board and lead, six findings | 2026-10-25, review | Applied in part; six items open | [Known issues, and what will not work](../reference/known-limitations.md) |
| [Design review of the v1.0 PCBs](../pcb-review-2026-11-09.md), in French: 65 findings two days before fabrication, the cable pinouts verified | 2026-11-09, review | Current; four fixes went in before fabrication, the rest is open | [Known issues, and what will not work](../reference/known-limitations.md) |

## Fabs, parts and routing

| Note | Date, kind | Standing | Today's answer |
|---|---|---|---|
| [Parts, prices and three fabs compared](../jlc-parts-audit.md): stock, prices, quotes, HASL or ENIG | 2026-10-19 to 10-23, audit | Superseded: an 8-bay rack, other PCBs; the order went to NextPCB | [Cost and time](../plan/cost-and-time.md) |
| [Autorouting benchmark](../autorouting-benchmark.md): Freerouting runs as a portfolio, three routers compared | 2026-10-22/23, study | Applies; figures predate the DATA ×6 | [Change a PCB](change-a-pcb.md) |

## Spikes

Two throw-away programs, each written to answer one question, documented in READMEs of the repository rather
than on this site.

| Spike | Date | Standing |
|---|---|---|
| [firmware/spikes/usb-hub](../../firmware/spikes/usb-hub/README.md): an ESP32-S3, a hub off the shelf and several boards over USB/IP | 2026-10-16 | Its findings went into [multi-dut-node.md](../multi-dut-node.md) and into the patches of `zephyr/patches.yml` |
| [firmware/spikes/coproc](../../firmware/spikes/coproc/README.md): what Zephyr gives an RP2350, on a Pico 2 | 2026-10-19 | Built, never run; the firmware it sizes is not being written, the stock analyzer is used |
