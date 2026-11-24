# Bill of materials

`python tools/bom.py` generates the whole bill from `config/rack.yaml`, the PCBs' own bills and the volume
of each STL file: no line of it is typed by hand, and none is retyped on this site.

| What | Where |
|---|---|
| Every line, to filter and sort | [The interactive bill](/viewer/bom.html) |
| Every line, as a file | [bom/rack-bom.csv](../../bom/rack-bom.csv) |
| Fasteners, drag chain, leads, charger, cameras, cables | [Shopping list and tools](../plan/shopping-list.md) |
| Printed parts and their grams | [Parts and quantities](../print/parts-list.md) |
| The orders of PCBs as JLCPCB quoted them | [Order the PCBs](../plan/order-the-pcbs.md#the-options-of-each-order) |
| Each component's stock, tier and price at volume | [bom/jlc-parts.md](../../bom/jlc-parts.md), generated too |

The bill is the default rack's: 12 bays in 4 × 3, with the boards of the example population. Its prices are
indicative: euros before VAT, small quantities, read in October 2026, the PCBs at JLCPCB's quotes and
estimates, converted at $1 = €0.92.

The interactive bill, served with the 3D model, reads the same data as the tables of this site. It shows the
total and each category's share, then every line; its filter searches by part, manufacturer's part number,
LCSC number or seller, and a click on a column's heading sorts by it.

## Cost summary

```{include} ../../bom/README.md
:start-after: "import VAT is extra."
:end-before: "Full line-item list"
```

What this total leaves out, and what each line holds: [Cost and time](../plan/cost-and-time.md).

## The PCBs' components

One table per PCB, in euros. A quantity is for the PCBs assembled in the bill's order, not for one PCB
(each order is on [Order the PCBs](../plan/order-the-pcbs.md#the-options-of-each-order)). The fab does not
fit a line whose source reads "hand-solder, buy loose". Under the components come the lines of the order
itself: the bare PCBs, the assembly fees, and a last line that brings the catalogue prices up to the
components figure of JLCPCB's quote. Each line's references (C1, U2) are in the CSV and on the interactive
bill.

### Power hub

```{bom-table}
:group: power-hub
:columns: item, qty, ext_eur, source
:total:
```

### Bay node

```{bom-table}
:group: bay-node
:columns: item, qty, ext_eur, source
:total:
```

### Camera pod

```{bom-table}
:group: camera-pod
:columns: item, qty, ext_eur, source
:total:
```

### DATA ×6

```{bom-table}
:group: data-port-x6
:columns: item, qty, ext_eur, source
:total:
```

### DATA ×4, with its logic

```{bom-table}
:group: data-port-x4
:columns: item, qty, ext_eur, source
:total:
```

### DATA ×4, base assembly

```{bom-table}
:group: data-port-x4-base
:columns: item, qty, ext_eur, source
:total:
```

### The DATA ×4's order panel, and the shipment

The bill orders the two assemblies of the DATA ×4 on one panel. Its PCB and assembly lines, then the one
shipment of the whole cart:

```{bom-table}
:group: data-port-x4-panel, jlc
:columns: item, qty, ext_eur, source, notes
:total:
```

## Sourcing notes

[bom/sourcing.md](../../bom/sourcing.md), the one hand-written file beside the bill, says why a part was
picked, what stood in for it and where a listing was found. It is a dated snapshot, begun on 2026-10-19 for
an order of eight bays: look at stock and prices again on the day of the order.

### The hub's PD controller

```{include} ../../bom/sourcing.md
:start-after: <!-- site:ch224a -->
:end-before: <!-- /site:ch224a -->
```

The CH224A took the place of the AP33772S on 2026-10-19, when LCSC had none of the latter.

### CAN transceiver

```{include} ../../bom/sourcing.md
:start-after: <!-- site:can-transceiver -->
:end-before: <!-- /site:can-transceiver -->
```

### USB-C receptacle of the bay node and the hub

```{include} ../../bom/sourcing.md
:start-after: <!-- site:usb4105 -->
:end-before: <!-- /site:usb4105 -->
```

### Buck inductors rated for 28 V

```{include} ../../bom/sourcing.md
:start-after: <!-- site:inductors-28v -->
:end-before: <!-- /site:inductors-28v -->
:relative-docs: ../
```

### Camera lens

```{include} ../../bom/sourcing.md
:start-after: <!-- site:camera-lens -->
:end-before: <!-- /site:camera-lens -->
```

### Cables to a board at the standing port wall

The USB-C receptacles of a DATA board stand 15.5 mm apart, so the drawer's end of a board's cable is a
straight USB-C plug, its overmold within the USB-IF's 12.35 × 6.5 mm. No listing gives the overmold: the
ends below were sized on the photos, on 2026-11-01. The first column names each cable as `config/rack.yaml`
does.

```{include} ../../bom/sourcing.md
:start-after: <!-- site:dut-cables -->
:end-before: <!-- /site:dut-cables -->
```

### Sellers outside AliExpress

```{include} ../../bom/sourcing.md
:start-after: <!-- site:outside-aliexpress -->
:end-before: <!-- /site:outside-aliexpress -->
```

## How it is generated

```console
$ python tools/bom.py
```

It takes no argument and writes four files:

| File | Holds |
|---|---|
| `bom/rack-bom.csv` | Every line: category, PCB, item, quantity, unit, unit price, total, seller, part number, reference, notes |
| `bom/README.md` | The summary that GitHub shows: totals, JLCPCB's orders, printed parts, line items |
| `bom/jlc-parts.md` | Per PCB, each part's tier, stock and price at JLCPCB for one, five and ten racks |
| `site/assets/bom.json` | The data of the interactive page |

Its inputs are `config/rack.yaml` (the size and the population), the detailed bill of each PCB
(`electronics/<pcb>/<pcb>-bom.csv`, written with the fabrication files), the quotes and fees it holds
itself (`JLC_QUOTE`), and the STL files, whose volumes give the grams. Change one of them, run it again and
commit what it writes: never edit a generated file. What the tool needs installed:
[build.py, plate_layout.py, bom.py](tools.md).
