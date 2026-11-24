# Shopping list and tools

A rack is bought in three orders: the PCBs from a fab ([Order the PCBs](order-the-pcbs.md)), their loose
connectors from LCSC, and the rest from the sellers named line by line below.

:::{status} designed
Nothing on this list has been bought as one set and assembled. Listings and prices were read in October
and November 2026, and a part whose dimensions are assumed says so in its note.
[What exists today](status.md).
:::

`tools/bom.py` computes every count for the rack of `config/rack.yaml`: 12 bays in 4 × 3, with the boards
of its example population. Another size moves the counts: regenerate before you buy
([Choose a size, change the layout](choose-your-rack.md)). The price of each line is on
[the interactive bill](/viewer/bom.html); filament is under
[Printer, filament, settings](../print/printer-and-settings.md).

## Fasteners, drag chain and leads

```{bom-table}
:category: Fasteners
:exclude: front display
:columns: item, qty, source, notes
```

One M3 screw length serves everywhere, and one thread-forming screw, the PT 2.3 × 8, goes into the printed
pilot holes of every bay; a camera pod takes two PT 2.6 × 14 of its own. Which insert goes into which boss
is on [Inserts and square nuts](../print/inserts-and-nuts.md). The build pages draw each step's hardware
with these icons:

{.bb-kit}
[![](../img/notice/hw_insert.svg){.bb-kit-icon .bb-lineart} M3 insert]{.bb-kit-item}
[![](../img/notice/hw_m3x8.svg){.bb-kit-icon .bb-lineart} M3 × 8]{.bb-kit-item}
[![](../img/notice/hw_pt23x8.svg){.bb-kit-icon .bb-lineart} PT 2.3 × 8]{.bb-kit-item}
[![](../img/notice/hw_pt26x14.svg){.bb-kit-icon .bb-lineart} PT 2.6 × 14]{.bb-kit-item}
[![](../img/notice/hw_w25.svg){.bb-kit-icon .bb-lineart} M2.5 washer]{.bb-kit-item}
[![](../img/notice/hw_sp12.svg){.bb-kit-icon .bb-lineart} Spacer M3 × 12]{.bb-kit-item}
[![](../img/notice/hw_tie.svg){.bb-kit-icon .bb-lineart} Cable tie]{.bb-kit-item}
[![](../img/notice/hw_jumper.svg){.bb-kit-icon .bb-lineart} 6-pin jumper]{.bb-kit-item}
[![](../img/notice/hw_usbc.svg){.bb-kit-icon .bb-lineart} USB-C 5 A]{.bb-kit-item}

```{bom-table}
:category: Motion
:columns: item, qty, source, notes
```

The trays are drawn round the chain's outer size, bend radius and end pieces, all assumed: order it first
and measure it ([Measure before you print](../print/index.md)).

```{bom-table}
:category: Cables
:match: 8-pin lead
:columns: item, qty, notes
```

The bill names [a listing on AliExpress](https://www.aliexpress.com/item/1005008045292937.html), with the
options "Same direction", 8P and 50 cm. "Same direction" is what matters: pin n at one end is pin 9 − n at
the other. A 1:1 lead swaps the signals and leaves the DATA board unpowered.

```{bom-table}
:category: Cables
:exclude: DUT cable|Micro-B 90|Dupont|Crimper|8-pin lead
:columns: item, qty, source, notes
```

A row carries up to 1.6 A, and JST rates a PH contact at 2 A on 24 AWG wire only. No ready-made 6-pin
cable states 24 AWG with this pinout, so each cable is six of JST's own single leads in two housings, and
the feeds that those leads do not reach are crimped
([Make the row cables](../build/row-cables.md)). Every pinout is under
[Cables and pinouts](../reference/cables.md).

## Charger and its cable

```{bom-table}
:category: Power
:columns: item, qty, source
```

The charger named is one example of the kind. What each kind of charger and cable gives the rows, from
[Specifications](../reference/specifications.md#chargers-and-what-each-feeds):

```{include} ../reference/specifications.md
:start-after: <!-- site:charger-table -->
:end-before: <!-- /site:charger-table -->
```

## Camera parts

A camera is optional, bay by bay. Each takes a camera pod PCB, one of the JST PH 8 leads above, a printed
pod and its diffuser, and these:

```{bom-table}
:category: Cameras
:columns: item, qty, source, notes
```

The bill counts cameras by a constant of `tools/bom.py`, whatever `cameras:` lists in `config/rack.yaml`.
The lens, from the sourcing notes:

```{include} ../../bom/sourcing.md
:start-after: <!-- site:camera-lens -->
:end-before: <!-- /site:camera-lens -->
```

## Jumper wires and an analyzer for a DATA ×4

```{bom-table}
:category: Analyzer, Cables
:match: Pico 2|Dupont
:exclude: DUT cable
:columns: item, qty, source
```

Only a bay with a DATA ×4 takes these. The 20 cm strip is torn into small ribbons that run from the
DATA ×4's pin headers to the pins of the boards ([Wires between boards](../use/wires.md)). The Pico 2 is a
stand-alone analyzer in the example's sub-slot B3.3, with gusmanb's LogicAnalyzer firmware, and the 10 cm
strip carries its channels. It was chosen before the DATA ×4's co-processor, which is the bay's own
analyzer: a bay with a DATA ×4 with its logic does not need it
([A Pico 2 on a port instead](../use/logic-analyzer.md#a-pico-2-on-a-port-instead)). If you buy one, buy
revision A4 of its RP2350, marked on the chip: on A2 an input released from high can stay near 2.1 V.

## USB cables for your boards

One cable for each board of the example population. Yours need others: the cable belongs to the board,
USB-C at the drawer's end and whatever the board takes at the other
([Put a board in a bay](../use/mount-a-board.md)).

```{bom-table}
:category: Cables
:match: DUT cable|Micro-B 90
:columns: item, qty, ext_eur, source
:total:
```

Whatever the board:

- The drawer's end is a straight USB-C plug, its overmold within the USB-IF's 12.35 × 6.5 mm: the
  receptacles stand 15.5 mm apart behind slots in the port wall. An angled plug fits only if its cable
  leaves upwards.
- The cable carries data (USB 2.0, 480 Mbit/s). Many short cables are charge-only.
- No listing gives the size of an overmold: measure the first cable when it arrives.

The listings were chosen on 2026-11-01; the alternatives and the ones rejected are in the
[sourcing notes](../reference/bill-of-materials.md#cables-to-a-board-at-the-standing-port-wall).

## The connectors the fab leaves off

The third order, at LCSC: the through-hole connectors of the two DATA boards, which the fab does not
fit.

| Part | LCSC | How many |
|---|---|---|
| JST PH 8-pin socket, vertical, through-hole (B8B-PH-K-S) | [C157974](https://www.lcsc.com/product-detail/C157974.html) | One on every DATA board: J1, the lead's socket |
| Pin header 2 × 6, 2.54 mm | [C32713279](https://www.lcsc.com/product-detail/C32713279.html) | Four on a DATA ×4: J102, J202, J302, J402 |
| Pin header 1 × 5, 2.54 mm | [C32713271](https://www.lcsc.com/product-detail/C32713271.html) | One on a DATA ×4 with its logic: J2, the SWD header |

Read from the `Assembly` column of the detailed bills, `electronics/<pcb>/<pcb>-bom.csv`, which marks these
parts "hand-solder, buy loose (LCSC)". The bill's own lines for them, with the quantities of its order, are
among [the PCBs' components](../reference/bill-of-materials.md#the-pcbs-components). Which face, which way
round, and what a base assembly takes: [Solder the connectors](../build/solder-the-connectors.md).

## Not in the bill

What the rack needs around it, which `tools/bom.py` does not count:

| What | Why | Where it is described |
|---|---|---|
| Wood screws 3.5 × 16, pan head, with M4 washers: two per column | An open drawer can tip a rack that is not screwed down | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |
| Or an 18 mm MDF base, 670 mm wide and at least 500 mm deep | Where the bench cannot be drilled | The same page |
| A 2.4 GHz access point you control | One fixed channel, 20 MHz wide, for the hub and every bay node | [Wi-Fi in the rack](../use/wifi.md) |
| A Linux machine | USB/IP attaches a board's USB device with the Linux `usbip` tool | [Set up bayctl and usbip](../use/set-up-your-machine.md) |
| An AUX lead: a JST PH 6 lead ending in flying wires | Only for a board without its own USB serial port | [Cables and pinouts](../reference/cables.md) |
| Your boards | The bill buys cables for the example's boards, not the boards | [Board library](../reference/board-library.md) |
| The bench equipment | Bought once, or already on your bench | [Tools and bench equipment](#tools-and-bench-equipment) |

## What not to buy

The bill still counts the screws of a front display, and bay node v1.0 has no connector for one:

```{bom-table}
:category: Fasteners
:match: front display
:columns: item, qty
```

| Do not buy | Why |
|---|---|
| These screws, and the display module itself (a Waveshare 1.9" touch LCD) | No connector on bay node v1.0. The module is not in the bill, but `config/rack.yaml` and older pages of the repository describe it |
| Magnets | The drawer's detent is printed. Two Ø 6 × 3 mm magnets a bay, and CA glue, only with `drawer.detent: magnet` in `config/rack.yaml` |
| A multi-port charger | It can withdraw its full offer when something else is plugged in |
| A 1:1 JST PH lead | Every ready-made lead of the rack is "Same direction" |
| A charge-only USB cable | The cable to a board carries its USB data |

## Tools and bench equipment

<!-- site:tools -->

<!-- site:hand-tools -->

| Tool | For |
|---|---|
| PH1 screwdriver, magnetic, shaft no thicker than 5 mm | The two left screws of a bay node, fed through holes in the tray's guide |
| A screwdriver with a shaft of 60 mm or more | The five screws of the strip over a DATA board, between the port wall and the PCB |
| An iron with a tip for heat-set inserts | Every M3 insert |
| A soldering iron | The through-hole connectors of the DATA boards |
| Kapton tape | A DATA ×4: over the parts beside the lead's socket while its 20 to 28 V pin is soldered |
| A ratchet crimper for open-barrel contacts, 28 to 18 AWG (IWISS SN-28B, or Engineer PA-09) | The row feeds longer than JST's ready-made leads |
| Pliers | The four hex spacers of the power hub: no room for a 5.5 mm socket beside the row connector |
| Side cutters, fine sandpaper | The two tabs of a DATA ×4 order panel |
| Callipers | The drag chain and the camera before the parts that hold them are printed; a strand of the 24 AWG wire |
| A stubby screwdriver | The bench screws, if they go in after row A |

<!-- /site:hand-tools -->

The crimper is the one tool that the bill of materials counts, in its Cables line.

<!-- site:bench-equipment -->

For the checks of the PCBs, before anything is screwed to a tray:

- a multimeter with a continuity beeper, and a magnifier;
- a bench supply, 0 to 30 V, with a current limit;
- a USB-C PD charger of 65 W or more, and USB-C cables: the rack's own charger does;
- the leads: a row cable (JST PH 6), a DATA lead and a camera lead (JST PH 8, both "Same direction");
- a 3.3 V USB-UART adapter with probe clips, for a bay node's shell before it is on Wi-Fi;
- a Linux machine with the firmware workspace;
- a USB device to plug into the DATA ports (a memory stick, a development board);
- a 47 Ω 10 W resistor, as the load of a row.

<!-- /site:bench-equipment -->

The hand tools are read from the assembly steps (the tray, the strip, the power box), from the review of
2026-11-09 and from `bom/rack-bom.csv`; the bench equipment from the PCB checklists. The callipers are
added here: the chain's figures in `config/rack.yaml` › `chain` are in tenths of a millimetre.

<!-- /site:tools -->

## When the parcels arrive

Check these before a part is printed round a bought one or a lead meets a PCB; ringing every cable out
with a meter comes later, on [Make the row cables](../build/row-cables.md).

- [ ] The drag chain measures 13.5 × 10.2 mm outside and bends to a radius of 18 mm; the two holes of an end
  piece are 8 mm apart, and an end piece is 26 mm long from its mouth to its pivot. Any difference goes into
  `config/rack.yaml` › `chain` before a tray is printed ([Measure before you print](../print/index.md)).
- [ ] One pair of the end pieces bought apart fits the opening links: their listing is for the chain that
  does not open. Try a pair before buying the lot.
- [ ] Both plugs of a JST PH 8 lead show the same face, and pin 1 rings to pin 8. The lead is 45 to 50 cm
  long.
- [ ] The wire for the crimped feeds is 24 AWG: strip one end, count the strands and measure one. 24 AWG is
  7 × 0.20 mm, 11 × 0.16 or 19 × 0.12 (about 0.21 mm²); 7 × 0.16 is 26 AWG.
- [ ] The camera's header reads VCC, GND, SCK, MISO, MOSI, CS. Its case is measured before the pod is
  printed: the pod is drawn round a placeholder of it (Arducam gives 33 × 33 mm).
- [ ] Each USB-C end of a board's cable is within 12.35 × 6.5 mm.
- [ ] Of the two micro-B adapters of a board, the one whose socket faces up once plugged in is kept.
- [ ] The charger's cable is rated 5 A (100 W or 240 W). Through a 3 A cable a charger offers 60 W.
