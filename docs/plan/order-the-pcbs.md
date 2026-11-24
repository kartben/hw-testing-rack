# Order the PCBs

A rack is built from five PCBs: a bay node and a DATA board (DATA ×6 or DATA ×4) in every bay, one power
hub, and a camera pod for each bay that gets a camera.

:::{status} designed
v1.0 of the five PCBs has been at NextPCB since 2026-11-11; none has arrived. No source holds an ordering
procedure: this page is put together from the notes of that order and from the options of JLCPCB's quotes.
[What exists today](status.md#the-five-pcbs).
:::

The placement files in the repository are in JLCPCB's format and carry JLCPCB's corrections: sent as they
are to another assembler, they turn parts. Every price in the repository is a JLCPCB quote, yet the one
order placed went to NextPCB, with KiCad's raw position file, which is not committed.

## The five PCBs and how many you need

| PCB | Size, layers, finish | Soldered by hand after the fab |
|---|---|---|
| Power hub | 76 × 100 mm, 4 layers, lead-free HASL | Nothing |
| Bay node | 74 × 90 mm, 4 layers, lead-free HASL | Nothing |
| Camera pod | 40 × 27 mm, 2 layers, lead-free HASL | Nothing |
| DATA ×6 | 100 × 70 mm, 4 layers, ENIG | The lead's socket, on the rear face |
| DATA ×4 | 100 × 70 mm, 4 layers, ENIG | The lead's socket, the pin headers and, with its logic, the SWD header |

Sizes and layers are read from `config/rack.yaml` › `pcb`, finishes from each PCB's `design.py`. What each
PCB does, with its schematic and its renders: [The five PCBs](../reference/pcbs/index.md).

<!-- site:pcbs-per-size -->

| Rack | Bay nodes | DATA boards | Power hub |
|---|---|---|---|
| One bay on a desk | 1 | 1 | None: a USB-C PD trigger module feeds the node |
| 2 × 2 | 4 | 4 | 1 |
| 4 × 2 | 8 | 8 | 1 |
| 4 × 3, the default | 12 | 12 | 1 |

The rule is that of `electronics()` in `tools/bom.py`: one bay node per bay, one DATA board per bay, one
power hub per rack, which feeds up to four rows. A bay whose entry in `config/rack.yaml` › `population` has
`boards:` on a plate takes a DATA ×4; every other bay, a slot-bin bay included, takes a DATA ×6. A camera
pod goes with each camera.

A fab sells more than the rule asks: JLCPCB makes bare PCBs by five and assembles at least two of a kind,
and the NextPCB order was five of each, two assembled. One rack's single hub is therefore five PCBs, two of
them assembled.

<!-- /site:pcbs-per-size -->

Which size, and which DATA board in which bay: [Choose a size, change the layout](choose-your-rack.md).

The DATA ×4 is one PCB in two assemblies. With its logic it carries the switch matrix behind its pin
headers and the RP2350B co-processor that is the bay's logic analyzer. The base leaves those parts off and
keeps four switched and measured USB-C ports and the RESET and BOOT lines of its headers. The order of
2026-11-11 took it with its logic; JLCPCB's quote pairs one of each on an order panel:

```{figure} ../../electronics/data-port-x4/docs/data-port-x4-panel-top.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×4 order panel, two PCBs joined by two tabs
:width: 360px

KiCad render of the order panel, 100 × 142 mm: the base above, turned half a turn, the logic assembly below.
The two tabs of the joint are cut, never snapped
([Solder the connectors](../build/solder-the-connectors.md)).
```

## What was ordered on 2026-11-11, and how

v1.0 of the five PCBs left for NextPCB on 2026-11-11, from commit `125c4ece`: five PCBs of each, two of
them assembled, the DATA ×4 with its logic ([electronics/released.json](../../electronics/released.json)).
How it was sent was settled in the review of 2026-11-09, which is in French
([Design review of the v1.0 PCBs](../pcb-review-2026-11-09.md)):

- The placement file is KiCad's raw position file, one per PCB, never `fab/*-cpl-jlcpcb.csv`. Read by an
  assembler that takes KiCad's rotations, the JLCPCB files would turn 18 parts on the power hub, 21 on the
  bay node, 29 on the DATA ×6, 59 on the DATA ×4 and 2 on the camera pod, and shift others.
- The two DATA boards are quoted at the 3.5 / 3.5 mil tier: their finest tracks are 0.09 mm wide with
  0.1 mm between them. The bay node and the power hub stay at 5 mil.
- The assembler's placement preview is checked for four things: the pin-1 dot of U2 on the DATA ×6, the
  "+" of C60 (the electrolytic capacitor on the 20 to 28 V input of both DATA boards), the direction of the
  USB-C receptacles, and on a DATA ×4 the dot of L1, the inductor of the RP2350B's core regulator. The order
  also asked the fab about the rotation of the QFN and SOT-23-6 parts.
- The bill carries a manufacturer's part number on every line. For its quote of 2026-10-20 NextPCB took the
  Gerber archive, the placement file zipped (it takes zip or xls only) and such a bill, which it matches
  part number by part number. JLCPCB's bill is keyed on LCSC numbers; the detailed `<pcb>-bom.csv` has both.

`electronics/tools/build_board.py` writes the raw position file, derives JLCPCB's file from it and deletes
it. To get it back, run the command it runs, here for the bay node, with KiCad 10 installed:

```console
$ kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o bay-node-pos.csv electronics/bay-node/bay-node.kicad_pcb
```

The options ticked in NextPCB's form, the price paid and the lead time are not recorded. NextPCB's quote of
2026-10-20 for an earlier set of PCBs, and JLCPCB's prices, are under
[Cost and time](cost-and-time.md#what-the-pcbs-cost-and-at-which-fab).

## Where the fab files are

| PCB | Fabrication files | Detailed bill |
|---|---|---|
| Power hub | [power-hub-fab.zip](/downloads/power-hub-fab.zip) | [power-hub-bom.csv](../../electronics/power-hub/power-hub-bom.csv) |
| Bay node | [bay-node-fab.zip](/downloads/bay-node-fab.zip) | [bay-node-bom.csv](../../electronics/bay-node/bay-node-bom.csv) |
| Camera pod | [camera-pod-fab.zip](/downloads/camera-pod-fab.zip) | [camera-pod-bom.csv](../../electronics/camera-pod/camera-pod-bom.csv) |
| DATA ×6 | [data-port-x6-fab.zip](/downloads/data-port-x6-fab.zip) | [data-port-x6-bom.csv](../../electronics/data-port-x6/data-port-x6-bom.csv) |
| DATA ×4 | [data-port-x4-fab.zip](/downloads/data-port-x4-fab.zip) | [data-port-x4-bom.csv](../../electronics/data-port-x4/data-port-x4-bom.csv), [data-port-x4-base-bom.csv](../../electronics/data-port-x4/data-port-x4-base-bom.csv) |

An archive is the content of `electronics/<pcb>/fab/`:

- `<pcb>-gerbers.zip`: Gerber X2 and Excellon drill files;
- `<pcb>-bom-jlcpcb.csv`: JLCPCB's bill, one line per LCSC part;
- `<pcb>-cpl-jlcpcb.csv`: the placement file, in JLCPCB's columns and with JLCPCB's corrections.

The DATA ×4's archive also holds the files of its base assembly (`-base-`) and of its order panel
(`-panel-`). The detailed bill sits beside the `fab/` folder, not in the archive: manufacturer's part number
and LCSC number on every line, an alternative where one was checked, and an `Assembly` column that marks
what is soldered by hand.

These are v1.0's files, and they are frozen: `electronics/released.json` holds the SHA-256 of the Gerber
archive, of the detailed bill and of the placement file, and a test fails when they change. Do not
regenerate them, and never run `tools/kicad.sh <pcb> --route` on a released PCB: it routes the PCB anew,
and what comes out is not the PCB that was sent. Any change is a new revision:
[Change a PCB](../engineering/change-a-pcb.md).

## At JLCPCB, where nobody has ordered

Worked out from the options of the quotes in `tools/bom.py`, from the
[placement corrections](../electronics.md#placement-corrections) of the electronics design log and from the
review of 2026-11-09; nobody has done it yet.

:::{warning}
Do not order the DATA ×6 at JLCPCB with the committed placement file as it stands. It places U2 a quarter
turn off, and no port of an assembled DATA ×6 would switch on.
:::

### Four corrections before you pay

The review found four faults that come from JLCPCB's own footprints, so they hold at JLCPCB only. The
committed files, frozen with v1.0, carry none of the fixes. The first three are made by hand in the
*Component Placement* step of the order, the fourth in its bill.

1. U2 of the DATA ×6 (finding X6-01), the TCA9535 port expander (C129354). JLCPCB draws its footprint a
   quarter turn from KiCad's, and the table of corrections has no row for it. Placed as the file says,
   every pin lands six pads further on: nothing answers at I²C address 0x20 and every port's enable line
   stays low, on every assembled PCB, until U2 is lifted and turned with hot air (nothing is destroyed).
   Turn U2 until its pin-1 dot sits at the top left of the part, on the arrow of the silkscreen
   ([DATA ×6, known issues](../reference/pcbs/data-x6.md#known-issues-of-v10)).
2. D8 of the bay node (BN-06), the diode DFLS260-7 (C209346). It lands 0.34 mm along its length beside its
   pads: KiCad's footprint has its origin at the centre of the body, JLCPCB's midway between the pads.
   Reflow will probably pull it back, but nothing guarantees it. Move it onto its pads
   ([Bay node, known issues](../reference/pcbs/bay-node.md#known-issues-of-v10)).
3. D41 to D44 of the power hub (PH-01): the same part and the same 0.34 mm, on the four diodes of the row
   outputs, whose job is to take the cut of a shorted row
   ([Power hub, known issues](../reference/pcbs/power-hub.md#known-issues-of-v10)).
4. The buck inductor C48009678 (PH-10): L1 of the hub and of the bay node, L2 and L3 of the DATA ×6.
   JLCPCB lists this Vishay IHLP2525CZEK4R7M01 without a footprint, so the preview cannot show whether it
   sits right, and its stock fell from 5,690 to 690 in five days. C553961 is the same inductor on another
   reel, with a footprint and 4,222 in stock on 2026-11-09: order with it, unless JLCPCB confirms that it
   places C48009678.

Check the preview for the four things the NextPCB order looked at, too, and for three corrections of the
table: the power hub's ten side LEDs (D3, D8, D11 to D14, D21 to D24) and its U1, the CH224A; the bay node's
SERVICE switch SW3, with the drills shown, its two pegs in their holes. No row of the table of
corrections is marked confirmed: nobody has yet seen JLCPCB's preview show the v1.0 files right. The design
log's tests for a part there: the body sits over its pads, centred; pin 1, the cathode bar or the + side
lines up with the mark on the silkscreen; a side-entry connector opens towards the edge of the PCB.

### The options of each order

Each PCB is an order of its own, all in one cart: one shipment. Upload `<pcb>-gerbers.zip` for the PCB,
then `<pcb>-bom-jlcpcb.csv` and `<pcb>-cpl-jlcpcb.csv` at the assembly step. The table below is generated
from the quotes: the layers, size, stack-up, finish and assembly service quoted for each PCB, then what
JLCPCB asked, to hold against your own cart.

The solder mask is green on every PCB (*PCB Color*), because JLCPCB's Economic assembly takes four layers in
green only (jlcpcb.com, 2026-10-23). The bay node and the power hub go through Standard assembly: every
ESP32-S3 module is Standard-only at JLCPCB, which then adds two 5 mm rails to the PCB. The three others go
through Economic assembly. The quantities are the bill's, made for a smaller rack with ten bay nodes: order
what your size needs, by five PCBs, at least two of them assembled.

In the table `data-port-x4` is the DATA ×4 with its logic, `data-port-x4-base` its base assembly,
`data-port-x4-panel` the order panel that the bill prices, and "v2" an older name of the DATA ×4 v1.0.

```{include} ../../bom/README.md
:start-after: "(the full PCBA quote needs the user's JLC sign-in)."
:end-before: "## JLC cost"
```

### The line JLCPCB unticks

The USB-C receptacle of the bay node and of the power hub, as the sourcing notes record it:

```{include} ../../bom/sourcing.md
:start-after: <!-- site:usb4105 -->
:end-before: <!-- /site:usb4105 -->
```

## Parts that run out

Stock is JLCPCB's, on the days given; look again on the day of the order. An assembler that buys elsewhere
may not be short of the same parts: Mouser listed 8,334 of the first one on 2026-11-09.

| Part | Stock at JLCPCB | What to do |
|---|---|---|
| TPS2553DBVR-1 (C111738), the port switch that latches off on a fault: one per port of both DATA boards | 196 on 2026-11-04, 1 on 2026-11-09 | Wait, or supply the part. Its pin-compatible relatives TPS2553DBVR (C55266) and TPS2553DDBVR (C521201) do not latch, and the design counts on the latch |
| AOTA-B201610S3R3-101-T (C42411119), the inductor of the RP2350B's core regulator: DATA ×4 with its logic | 1 on 2026-11-04 | No second source: it is the one inductor Raspberry Pi approves for the RP2350's regulator. JLCPCB sells it by five |
| IHLP2525CZEK4R7M01 (C48009678), the buck inductor: power hub, bay node, DATA ×6 | 5,690 on 2026-11-04, 690 on 2026-11-09 | C553961, the fourth correction above |
| USB4145-03-0170-C (C5181332), the standing USB-C receptacle: one per port of both DATA boards | 2,991 on 2026-11-04 | Four times what ten racks take; `bom/jlc-parts.md` flags it all the same |
| TCAN1462VDRQ1 (C7399456), a CAN transceiver: power hub, bay node | None at LCSC on 2026-10-19 | Nothing: the bills carry the NXP TJA1462AT/0Z (C3234095) since. The TI TCAN1044AVDRQ1 (C3234993) has the same footprint and pinout |

The stock of every part, against ten racks' need, is in the generated
[bom/jlc-parts.md](../../bom/jlc-parts.md) (JLCPCB's catalogue of 2026-11-04). The `Alternative` column of
a detailed bill names a second source where one was checked, and the
[sourcing notes](../reference/bill-of-materials.md#sourcing-notes) say why each part was picked.

## What comes in the box

An order at the minimum brings five PCBs of a kind, two assembled and three bare. Keep the bare ones: on
the bench, a doubtful reading is compared with a PCB that has no parts.

The bay node, the power hub and the camera pod come complete. The two DATA boards come without the
through-hole parts of the first table: a third order, bought loose
([shopping list](shopping-list.md#the-connectors-the-fab-leaves-off)) and soldered by hand
([Solder the connectors](../build/solder-the-connectors.md)).

Every PCB then goes through its checklist before it goes near a tray, the first assembled one of a kind
entirely before the second is powered ([Check each PCB](../build/check-the-pcbs/index.md)). v1.0 is frozen:
what the bench finds is reported, and fixed in the next revision
([Report a finding](../reference/known-limitations.md#report-a-finding)).
