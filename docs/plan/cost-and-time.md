# Cost and time

The parts of a 12-bay rack, 4 × 3, come to the total below: small quantities, euros before VAT, prices read
in October 2026, the PCBs at JLCPCB's.

:::{status} designed
Every figure on this page is a quote, an estimate or a slicer's output, and carries its date. Nobody has
paid this bill as a whole, printed the frame or timed an assembly: [What exists today](status.md).
:::

## What a 12-bay rack costs

```{include} ../../bom/README.md
:start-after: "import VAT is extra."
:end-before: "Full line-item list"
```

`tools/bom.py` computes this table from `config/rack.yaml`, the PCBs' own bills and the volume of each STL
file, at $1 = €0.92. Every line behind it, with its seller, is in the
[bill of materials](../reference/bill-of-materials.md), and [the interactive bill](/viewer/bom.html) filters
and sorts them. "All-in" is the generator's word: the figure leaves out what follows.

## What the figure leaves out

| Left out | What is known of it |
|---|---|
| Two bay nodes | The Electronics line prices the order chosen on 2026-10-19, when the rack had eight bays: ten bay nodes, all assembled. Twelve bays take twelve; the last table of [What the PCBs cost](#what-the-pcbs-cost-and-at-which-fab) counts them |
| The fab that was used | The prices are JLCPCB's. The one order placed so far went to NextPCB, at a cost the repository does not record |
| VAT and import | On a parcel from China to France, DHL bills the 20 % import VAT plus a clearance fee of roughly €15 to 20 (noted on 2026-10-20). JLCPCB's DDP option collects the VAT at checkout instead |
| Shipping | The bill has one line for it, JLCPCB's parcel. The loose connectors come from LCSC with its own shipping; Digi-Key, for the ready-made JST leads, delivers free in France from €75 |
| Tools and bench equipment | Only the crimper is in the bill. A bench supply, a multimeter, a USB-UART adapter and the rest: [Tools and bench equipment](shopping-list.md#tools-and-bench-equipment) |
| What stands around the rack | The screws into the bench, an access point, a Linux machine: [Not in the bill](shopping-list.md#not-in-the-bill) |
| Your boards | The bill buys a cable for each board of the example population, and no board but the Pico 2 that serves as its logic analyzer |

## Where the money goes

| Line | What it counts | It moves with |
|---|---|---|
| Electronics | The five PCBs assembled at JLCPCB: bare PCBs, assembly fees, components, one shipment | The number of bays, and the fab |
| Cables | The rack's own leads, housings and ties; a crimper, bought once; a short USB cable for each board of the example population, with its adapters and jumper wires | Your boards, for the USB cables |
| Printed parts | PETG by the kilogram ([Filament](#filament)) | The size of the rack |
| Cameras | Camera, lens, cable and pod hardware, for as many cameras as a constant of `tools/bom.py` says, whatever `cameras:` lists in `config/rack.yaml` | Nothing: cameras are optional |
| Power | One charger and its 5 A cable | Nothing: one per rack |
| Motion | The drag chain and its end pieces | The number of drawer bays |
| Fasteners | Inserts, square nuts, screws, washers, and the screws of a front display that bay node v1.0 has no connector for | The size of the rack |
| Analyzer | The Pico 2 and the jumper wires of the example's sub-slot B3.3 | The example only |

The shopping list cuts the Cables line in two:
[the rack's leads](shopping-list.md#fasteners-drag-chain-and-leads), and
[the cables to the example's boards](shopping-list.md#usb-cables-for-your-boards) with their total.

## What the PCBs cost, and at which fab

Every PCB price in the repository is JLCPCB's. Four are quotes taken on jlcpcb.com from the fabrication
files: the bay node, the power hub and the camera pod on 2026-10-23, the DATA ×4's order panel on
2026-11-01. The DATA ×6 is an estimate from JLCPCB's fees and catalogue prices. `tools/bom.py` holds them
(`JLC_QUOTE`) and adds what changed on each PCB after its quote.

The order actually placed, v1.0 of the five PCBs, five of each and two of them assembled, went to NextPCB on
2026-11-11, at a cost the repository does not record. Its one NextPCB figure is a quote of 2026-10-20 for an
earlier set of PCBs: 2.1 times JLCPCB's price, 1.5 times with a new-customer offer. AISLER, quoted the same
day, came to 5.2 times ([Parts, prices and three fabs compared](../jlc-parts-audit.md), a dated note).

At JLCPCB the fees of an order (set-up, stencil, a fee per type of part) are paid once, so a PCB costs less
the more of it are assembled together. The first table below gives one assembled PCB, in US dollars, when 2,
5, 10, 50 or 100 are assembled in one order; *Floor* is what remains once the fees no longer count. The
second gives the PCBs of one rack when one, five or ten racks are ordered at once. `data-port-x4-panel` is
the DATA ×4's order panel, one PCB of each of its two assemblies; what to correct on it and on the others
before paying is on [Order the PCBs](order-the-pcbs.md).

```{include} ../../bom/README.md
:start-after: "once the fees per order no longer count."
:end-before: "## Printed parts"
```

## Filament

The bill's filament is PETG ([Printer, filament, settings](../print/printer-and-settings.md#filament) says why,
and which). How much has two answers.

```{include} ../print/printer-and-settings.md
:start-after: "How much has two answers."
:end-before: "The tray's and the drawer's slicer figures are those"
```

(time-what-is-known)=
## Printing time and lead times

Bambu Studio sliced every part on 2026-10-21 for an H2D (0.4 mm nozzle, 0.2 mm layers, the project's
profile); [the note of that day](../printed-parts-fdm-review.md) gives the figures per assembly. Multiplied
out for the default rack:

| What was sliced | Slicer's figure | In the rack | Printer time |
|---|---|---|---|
| One drawer bay: tray, drawer, board plate, the chain's foot and anchor, label, eight pegs | 11 h 03 on 2 plates | × 12 bays | 132 h 36 |
| One column of frame, two rows high: 2 base ladders, 4 row ladders, 2 cap strips, a floor plate, a cap plate, 3 braces | 16 h 08 on 8 plates | × 4 columns | 64 h 32 |
| The power box, base and lid | 2 h 07 on 1 plate | × 1 | 2 h 07 |
| | | **Sum** | **199 h 15 on 57 plates** |

About 200 hours of printer time, never run: slicer figures, on the geometry of 2026-10-21. Today's rack
differs in three ways:

- Four columns side by side stand on five stacks of ladders, not eight, and the default rack has a third
  row. By the same note's times per part, that is about 7 hours less.
- Every bay now holds its DATA board in a printed cradle under a strip: 1 h 40 and 7 minutes a bay by the
  figures of [the mechanical design document](../mechanical.md), 21 hours more.
- The example's top row carries a slot bin in each drawer where the other bays carry a plate and pegs. No
  slicer figure is recorded for it.

Each part's own time is in [Parts and quantities](../print/parts-list.md). The assembly, the soldering and
the bench checks have no duration at all: nobody has built a rack.

The fabs quoted these lead times on 2026-10-20, for an earlier set of the PCBs:

| Fab | Lead time quoted |
|---|---|
| JLCPCB | About 1.5 to 2 weeks door to door |
| NextPCB | Assembly in 17 to 19 working days for the bay node, then shipping: 4 to 5 weeks door to door |
| AISLER | Dispatched after 18 working days, then 1 to 3 days within the EU |

The v1.0 order left for NextPCB on 2026-11-11; the repository records no arrival yet.
