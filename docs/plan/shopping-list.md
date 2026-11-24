# Shopping list and tools

This page lists what to buy besides [the PCBs](order-the-pcbs.md) and
[the filament](../print/printer-and-settings.md): screws, drag chains, cables, a charger, the connectors that
the fab leaves off the PCBs, and a few tools.

The counts below are for a plain 2 × 2 rack with two cameras: four bays, each with a drawer, a board plate and
a DATA ×6. For another size, see [Counts for your own rack](#counts-for-your-own-rack).
[The interactive bill](/viewer/bom.html) gives the counts and the prices of the 4 × 3 example.

## Screws and inserts

```{bom-table}
:category: Fasteners
:exclude: front display
:columns: item, qty, source
:size: 2x2
:plain:
```

Every M3 screw is the same length, M3 × 8. The PT 2.3 × 8 thread-forming screws go into the printed holes of
every bay. A camera pod takes two PT 2.6 × 14. Which insert goes where:
[Fit the inserts and nuts](../print/inserts-and-nuts.md).

The build pages show the hardware of each step with these icons:

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

## Drag chains

```{bom-table}
:category: Motion
:columns: item, qty, source
:size: 2x2
:plain:
```

Each drawer takes about 18 cm of chain and a pair of end pieces. Each metre of chain comes with one pair of end
pieces. Buy the other pairs separately. Try one pair on the chain before you buy the rest.

The trays are shaped around the drag chain: its outer size, its bend and its end pieces. Order the chain
first, and measure it before you print the trays:
[Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print).

## Leads and row cables

```{bom-table}
:category: Cables
:match: 8-pin lead
:columns: item, qty
:size: 2x2
:plain:
```

Each DATA board and each camera takes one lead. Order
[the 8-pin leads on AliExpress](https://www.aliexpress.com/item/1005008045292937.html) with the options
"Same direction", 8P and 50 cm. In a "Same direction" lead, pin n at one end goes to pin 9 − n at the other.
A 1:1 lead swaps the signals and leaves the DATA board unpowered.

```{bom-table}
:category: Cables
:exclude: DUT cable|Micro-B 90|Dupont|Crimper|8-pin lead
:columns: item, qty, source
:size: 2x2
:plain:
```

Each row cable is six of JST's single leads in two housings. You crimp the row feeds that are too long for the
ready-made leads: [Make the row cables](../build/row-cables.md). Every pinout is on
[Cables and pinouts](../reference/cables.md).

## Charger and its cable

```{bom-table}
:category: Power
:columns: item, qty, source
```

The charger in the bill is one example of the kind. This is what other chargers and cables give the rows:

```{include} ../reference/specifications.md
:start-after: <!-- site:charger-table -->
:end-before: <!-- /site:charger-table -->
```

## Camera parts

A camera is optional, bay by bay. Each one takes a camera pod PCB, an 8-pin lead like the DATA leads, a
printed pod with its diffuser, and these:

```{bom-table}
:category: Cameras
:columns: item, qty, source
```

These are the parts for two cameras. The LN018 lens replaces the camera's own lens, which is too narrow to see a large board. Focus it on the first camera you fit.

## Jumper wires and a Pico 2 for a DATA ×4

```{bom-table}
:category: Analyzer, Cables
:match: Pico 2|Dupont
:exclude: DUT cable
:columns: item, qty, source
```

Only a bay with a DATA ×4 needs these. Tear the 20 cm strip into small ribbons. They run from the DATA ×4's
pin headers to the pins of the boards: [Wires between boards](../use/wires.md).

In the example, the Pico 2 is a stand-alone logic analyzer on a port of bay B3, with the 10 cm strip for its
channels. A DATA ×4 with its logic has an analyzer of its own and does not need one
([Logic analyzer](../use/logic-analyzer.md)). If you buy a Pico 2, check that its RP2350 is revision A4. The
revision is marked on the chip. On revision A2, an input released from high can stay near 2.1 V.

## USB cables for your boards

Each board needs its own USB cable, with USB-C at the DATA board's end and whatever the board takes at
the other. The boards of the 4 × 3 example use these:

```{bom-table}
:category: Cables
:match: DUT cable|Micro-B 90
:columns: item, qty, source
```

When you choose cables for your own boards:

- Take a straight USB-C plug whose overmold fits within 12.35 × 6.5 mm, because the DATA board's
  receptacles stand 15.5 mm apart. An angled plug fits only if its cable leaves upwards.
- Take a cable that carries data (USB 2.0). Many short cables are charge-only.
- Measure the first cable when it arrives. Listings do not give the size of the overmold.

More on the cable and how it runs in the drawer: [Put a board in a bay](../use/mount-a-board.md).

## The connectors the fab leaves off

Buy these through-hole connectors of the DATA boards at LCSC, and solder them yourself
([Solder the connectors](../build/solder-the-connectors.md)):

| Part | LCSC | How many |
|---|---|---|
| JST PH 8-pin socket, vertical, through-hole (B8B-PH-K-S) | [C157974](https://www.lcsc.com/product-detail/C157974.html) | One on every DATA board: J1, the lead's socket |
| Pin header 2 × 6, 2.54 mm | [C32713279](https://www.lcsc.com/product-detail/C32713279.html) | Four on a DATA ×4: J102, J202, J302, J402 |
| Pin header 1 × 5, 2.54 mm | [C32713271](https://www.lcsc.com/product-detail/C32713271.html) | One on a DATA ×4 with its logic: J2, the SWD header |

Read from the `Assembly` column of the detailed bills, `electronics/<pcb>/<pcb>-bom.csv`.

## Counts for your own rack

Describe your rack in `config/rack.yaml`:
[Edit config/rack.yaml and regenerate](choose-your-rack.md#edit-config-rack-yaml-and-regenerate). Then run
`tools/bom.py` in a Python virtual environment. It needs no OpenSCAD:

```console
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install -r tools/requirements.txt
$ python tools/bom.py
```

`bom/README.md` then lists the printed parts, the screws and the cables of your rack, under "Line items".
Count the PCBs on [Order the PCBs](order-the-pcbs.md#how-many-of-each).

## Not in the bill

The bill of materials does not count these, but the rack needs them:

| What | Why | Where it is described |
|---|---|---|
| Wood screws 3.5 × 16, pan head, with M4 washers: two per column | An open drawer can tip a rack that is not screwed down | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |
| Or an 18 mm MDF base, as wide as the rack and at least 500 mm deep | Where you may not drill the bench | The same page |
| A 2.4 GHz access point you control | The hub and every bay node use one fixed channel, 20 MHz wide | [Wi-Fi for the rack](../use/wifi.md) |
| A Linux machine | It attaches a board's USB with the Linux `usbip` tool | [Set up your machine](../use/set-up-your-machine.md) |
| An AUX lead: a JST PH 6 lead ending in flying wires | Only for a board without its own USB serial port | [Cables and pinouts](../reference/cables.md) |
| Your boards | The bill buys cables for the boards of the example, not the boards | [Board library](../reference/board-library.md) |

## What not to buy

| Do not buy | Why |
|---|---|
| Magnets for the drawers | The drawer's catch is printed. Magnets are only for `drawer.detent: magnet` in `config/rack.yaml`: two Ø 6 × 3 mm per bay, with CA glue |
| A multi-port charger | It can withdraw its full power when something else is plugged in |
| A 1:1 JST PH lead | Every ready-made lead of the rack is "Same direction" |
| A charge-only USB cable | The cable to a board must carry its USB data |

## Tools and bench equipment

<!-- site:tools -->

<!-- site:hand-tools -->

| Tool | For |
|---|---|
| PH1 screwdriver, magnetic, shaft no thicker than 5 mm | The two left screws of a bay node, through holes in the tray's guide |
| A screwdriver with a shaft of 60 mm or more | The five screws of the strip over a DATA board, between the port wall and the PCB |
| An iron with a tip for heat-set inserts | Every M3 insert |
| A soldering iron | The through-hole connectors of the DATA boards |
| Kapton tape | A DATA ×4: over the parts beside the lead's socket while you solder it |
| A ratchet crimper for open-barrel contacts, 28 to 18 AWG (IWISS SN-28B, or Engineer PA-09) | The row feeds longer than JST's ready-made leads |
| Pliers | The four hex spacers of the power hub: there is no room for a 5.5 mm socket beside the row connector |
| Side cutters, fine sandpaper | The two tabs of a DATA ×4 order panel |
| Callipers | The drag chain and the camera, before you print the parts that hold them; a strand of the 24 AWG wire |
| A stubby screwdriver | The bench screws, if they go in after row A |

<!-- /site:hand-tools -->

The crimper is the only tool in the bill of materials.

<!-- site:bench-equipment -->

For the checks of the PCBs, before anything is screwed to a tray:

- a multimeter with a continuity beeper, and a magnifier;
- a bench supply, 0 to 30 V, with a current limit;
- a USB-C PD charger of 65 W or more, and USB-C cables (the rack's own charger will do);
- the leads: a row cable (JST PH 6), a DATA lead and a camera lead (JST PH 8, both "Same direction");
- a 3.3 V USB-UART adapter with probe clips, for a bay node's shell before it is on Wi-Fi;
- a Linux machine with the firmware workspace;
- a USB device to plug into the DATA ports (a memory stick, a development board);
- a 47 Ω 10 W resistor, as the load of a row.

<!-- /site:bench-equipment -->

<!-- /site:tools -->

## When the parcels arrive

Check these before you print the parts that hold a bought part, and before you plug a lead into a PCB. You
test the cables with a meter later, on [Make the row cables](../build/row-cables.md).

- [ ] The drag chain measures 13.5 × 10.2 mm outside and bends to a radius of 18 mm. The two holes of an end
  piece are 8 mm apart, and an end piece is 26 mm long from its mouth to its pivot. Enter any difference in
  `config/rack.yaml` › `chain` before you print a tray ([Print the parts](../print/index.md)).
- [ ] The end pieces fit the chain's links.
- [ ] Both plugs of a JST PH 8 lead show the same face, and pin 1 rings to pin 8. The lead is 45 to 50 cm
  long.
- [ ] The wire for the crimped feeds is 24 AWG. Strip one end, count the strands and measure one. 24 AWG is
  7 × 0.20 mm, 11 × 0.16 or 19 × 0.12 (about 0.21 mm²). 7 × 0.16 is 26 AWG.
- [ ] The camera's header reads VCC, GND, SCK, MISO, MOSI, CS. Measure its case before you print the pod:
  the pod is drawn for a case of 34 × 34 × 12 mm
  ([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)).
- [ ] Each USB-C end of a board's cable fits within 12.35 × 6.5 mm.
- [ ] Of the two micro-B adapters for a board, keep the one whose socket faces up once plugged in.
- [ ] The charger's cable is rated 5 A (100 W or 240 W). Through a 3 A cable, a charger offers 60 W.
