# Order the PCBs

A rack is built from five kinds of PCB. This page tells you how many your rack needs and how to order them
assembled. To choose the size of your rack and the DATA board of each bay, see
[Choose your rack's size](choose-your-rack.md).

## How many of each

<!-- site:pcbs-per-size -->

Each bay takes one bay node and one DATA board. A bay that holds several boards on its plate (`boards:` in
its entry of `config/rack.yaml`) takes a DATA ×4. Every other bay, a slot-bin bay included, takes a
DATA ×6. Each camera takes a camera pod. One power hub feeds up to four rows.

| Rack | Bay nodes | DATA boards | Power hub |
|---|---|---|---|
| One bay on a desk | 1 | 1 | None: a USB-C PD trigger module feeds the bay node |
| 2 × 2 | 4 | 4 | 1 |
| 4 × 2 | 8 | 8 | 1 |
| 4 × 3 | 12 | 12 | 1 |

JLCPCB makes PCBs in lots of five and assembles at least two of each kind. So even your single power hub is
an order of five PCBs, two of them assembled.

<!-- /site:pcbs-per-size -->

## The five PCBs

| PCB | Size, layers | Finish | Assembly at JLCPCB |
|---|---|---|---|
| Power hub | 76 × 100 mm, 4 layers | lead-free HASL | Standard |
| Bay node | 74 × 90 mm, 4 layers | lead-free HASL | Standard |
| Camera pod | 40 × 27 mm, 2 layers | lead-free HASL | Economic |
| DATA ×6 | 100 × 70 mm, 4 layers | ENIG | Economic |
| DATA ×4 | 100 × 70 mm, 4 layers | ENIG | Economic |

Read from `config/rack.yaml` › `pcb`, each PCB's `design.py` and the quotes in `tools/bom.py`.
[The five PCBs](../reference/pcbs/index.md) says what each one does.

The fab fits every part except a few through-hole connectors of the DATA boards. You buy those loose
([The connectors the fab leaves off](shopping-list.md#the-connectors-the-fab-leaves-off)) and solder them
yourself ([Solder the connectors](../build/solder-the-connectors.md)).

The DATA ×4 can be assembled in two ways. The full assembly, *with its logic*, adds a switch matrix behind
the pin headers and an RP2350B, which is the logic analyzer of the bay. The *base* assembly leaves those
parts off. It keeps the four switched and measured USB-C ports and the RESET and BOOT lines. In
`config/rack.yaml`, write `x4: v2` on a bay for the full assembly and `x4: base` for the base. JLCPCB can
make one of each on an order panel:

```{figure} ../../electronics/data-port-x4/docs/data-port-x4-panel-top.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×4 order panel, two PCBs joined by two tabs
:width: 360px

KiCad render of the order panel, 100 × 142 mm: the base at the top, the logic assembly below. Cut the two
tabs between them. Do not snap them ([Solder the connectors](../build/solder-the-connectors.md)).
```

## Download the fabrication files

| PCB | Fabrication files | Detailed bill |
|---|---|---|
| Power hub | [power-hub-fab.zip](/downloads/power-hub-fab.zip) | [power-hub-bom.csv](../../electronics/power-hub/power-hub-bom.csv) |
| Bay node | [bay-node-fab.zip](/downloads/bay-node-fab.zip) | [bay-node-bom.csv](../../electronics/bay-node/bay-node-bom.csv) |
| Camera pod | [camera-pod-fab.zip](/downloads/camera-pod-fab.zip) | [camera-pod-bom.csv](../../electronics/camera-pod/camera-pod-bom.csv) |
| DATA ×6 | [data-port-x6-fab.zip](/downloads/data-port-x6-fab.zip) | [data-port-x6-bom.csv](../../electronics/data-port-x6/data-port-x6-bom.csv) |
| DATA ×4 | [data-port-x4-fab.zip](/downloads/data-port-x4-fab.zip) | [data-port-x4-bom.csv](../../electronics/data-port-x4/data-port-x4-bom.csv), [data-port-x4-base-bom.csv](../../electronics/data-port-x4/data-port-x4-base-bom.csv) |

Each archive holds the v1.0 files of the PCB, in the form JLCPCB asks for:

- `<pcb>-gerbers.zip`: the Gerber and drill files;
- `<pcb>-bom-jlcpcb.csv`: the bill, one line per LCSC part;
- `<pcb>-cpl-jlcpcb.csv`: the placement file, with JLCPCB's rotations.

The DATA ×4 archive also holds the files of the base assembly (`-base-`) and of the order panel (`-panel-`).

The detailed bill is not in the archive. For every part, it gives the manufacturer's part number, the LCSC
number and a second source where there is one. Its `Assembly` column marks the parts you solder by hand.

## Order at JLCPCB

:::{warning}
Do not order the DATA ×6 with its placement file unchanged. The file places U2 a quarter turn wrong, and then
no port of the PCB switches on. Make the first correction below.
:::

1. Put each PCB in the cart as an order of its own. Keep them all in one cart, for one shipment.
2. Upload `<pcb>-gerbers.zip`. Choose the layers, the finish and the assembly service from the table above.
   Choose a green solder mask: Economic assembly takes four-layer PCBs in green only. JLCPCB adds two 5 mm
   rails to the bay node and the power hub, because their ESP32-S3 module needs Standard assembly.
3. Set the PCB quantity: 5 for up to five of this PCB, then 10, 15 and so on. Then set how many JLCPCB
   assembles:

   - Standard assembly (the bay node and the power hub): the number your rack needs, at least 2.
   - Economic assembly (the camera pod and the DATA boards): 2 or 5 of an order of 5. An order of 10 or more
     is assembled in full.

   For a plain 2 × 2 rack:

   | PCB | PCBs | Assembled |
   |---|---|---|
   | Bay node | 5 | 4 |
   | DATA ×6 | 5 | 5 |
   | Power hub | 5 | 2 |

4. At the assembly step, upload `<pcb>-bom-jlcpcb.csv` and `<pcb>-cpl-jlcpcb.csv`.
5. On the bay node and the power hub, tick the USB-C receptacle in the bill again. JLCPCB unticks this part,
   the GCT USB4105-GF-A-120 (C5184243), because its shell stakes are through-hole. If you leave it unticked,
   the PCB comes without its USB-C port.
6. Make the four corrections below, then check the placement preview.

### Four corrections before you pay

For these parts, JLCPCB's footprints differ from KiCad's, and the placement files do not correct for it.
Make the first three corrections in the *Component Placement* step, and the fourth in the bill.

1. On the DATA ×6, turn U2, the TCA9535 port expander (C129354), a quarter turn. Its pin-1 dot must sit at the
   top left of the part, on the arrow of the silkscreen. Placed as the file says, nothing answers on I²C and
   no port switches on. See [DATA ×6](../reference/pcbs/data-x6.md).
2. On the bay node, move D8, a DFLS260-7 diode (C209346), onto its pads. It lands 0.34 mm beside them, along
   its length.
3. On the power hub, move D41 to D44 onto their pads. They are the same diode, 0.34 mm off in the same way.
4. In the bill, replace the buck inductor C48009678 (Vishay IHLP2525CZEK4R7M01) with C553961, the same
   inductor on another reel. JLCPCB lists C48009678 without a footprint, so the preview cannot show it. It is
   L1 on the power hub and the bay node, and L2 and L3 on the DATA ×6. Keep C48009678 only if JLCPCB confirms
   that it can place it.

### Check the placement preview

On every part, check that:

- the body sits centred over its pads;
- pin 1, the cathode bar or the + side lines up with its mark on the silkscreen;
- a side-entry connector opens towards the edge of the PCB.

Look closely at these parts:

- U2 of the DATA ×6: its pin-1 dot;
- C60 of both DATA boards, the electrolytic capacitor on the 20 V input: its + side;
- the USB-C receptacles of every PCB: which way they face;
- L1 of the DATA ×4, the inductor of the RP2350B's regulator: its dot;
- the power hub's ten side LEDs (D3, D8, D11 to D14, D21 to D24) and its U1, the CH224A;
- SW3 of the bay node, the SERVICE switch: its two pegs in their holes.

## Order from another assembler

The placement files in the archives use JLCPCB's rotations. An assembler that expects rotations the way
KiCad writes them would turn up to 59 parts on a PCB the wrong way. Send it KiCad's own position file instead.
With KiCad 10, for the bay node:

```console
$ kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o bay-node-pos.csv electronics/bay-node/bay-node.kicad_pcb
```

- Send the detailed bill, `<pcb>-bom.csv`. It has a manufacturer's part number on every line. NextPCB, for
  example, matches the parts by that number, and takes the placement file zipped.
- Ask for the 3.5 / 3.5 mil tier for the two DATA boards: their finest tracks are 0.09 mm wide and 0.1 mm
  apart. The bay node and the power hub need 5 mil.
- The four corrections above apply to JLCPCB only. Check the preview all the same, and ask the assembler how
  it rotates the QFN and SOT-23-6 parts.

## Parts that run short

Check JLCPCB's stock on the day you order. These parts can run out:

| Part | On | What to do |
|---|---|---|
| TPS2553DBVR-1 (C111738), the port switch | every port of both DATA boards | Wait, or supply the part. The similar TPS2553DBVR and TPS2553DDBVR do not latch off on a fault, and the design needs the latch |
| AOTA-B201610S3R3-101-T (C42411119), the RP2350B's inductor | DATA ×4 with its logic | There is no second source: it is the one Raspberry Pi approves for the RP2350's regulator. JLCPCB sells it in fives |
| IHLP2525CZEK4R7M01 (C48009678), the buck inductor | power hub, bay node, DATA ×6 | Use C553961, as in the fourth correction |

The `Alternative` column of a detailed bill names a second source where there is one.
[bom/jlc-parts.md](../../bom/jlc-parts.md) lists the stock of every part against the needs of ten racks.

## When the PCBs arrive

You receive every PCB you ordered: the ones you had assembled, and the rest bare. Keep the bare ones. On the
bench, you can compare a doubtful reading with a PCB that has no parts on it.

The bay node, the power hub and the camera pod come complete. The DATA boards come without their through-hole
connectors: [Solder the connectors](../build/solder-the-connectors.md).

Check every PCB before it goes near a tray. Check the first one of a kind completely before you power the
second: [Check the PCBs](../build/check-the-pcbs/index.md).
