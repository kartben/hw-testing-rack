# Bill of materials

The bill of materials lists every part of a rack, with its quantity, price and seller. `tools/bom.py` writes
it from `config/rack.yaml`, so it matches the rack described there.

| What | Where |
|---|---|
| Every line, to filter and sort | [The interactive bill](/viewer/bom.html) |
| Every line, as a file | [bom/rack-bom.csv](../../bom/rack-bom.csv) |
| What to buy, part by part | [Shopping list and tools](../plan/shopping-list.md) |
| Printed parts and their mass | [Parts to print](../print/parts-list.md) |
| The PCB orders | [Order the PCBs](../plan/order-the-pcbs.md) |
| Each component's stock and price at JLCPCB | [bom/jlc-parts.md](../../bom/jlc-parts.md) |

The interactive bill shows the total and the share of each category, then every line. You can filter it by
part, manufacturer's part number, LCSC number or seller, and sort it by any column.

## Get the bill for your rack

The bill in the repository is for the example rack in `config/rack.yaml`: four columns and three rows, so
12 bays, with example boards in them. Your rack can have fewer bays or more. Describe it in
`config/rack.yaml` and regenerate
([Edit config/rack.yaml and regenerate](../plan/choose-your-rack.md#edit-config-rack-yaml-and-regenerate)).
To rewrite the bill alone:

```console
$ python tools/bom.py
```

The command takes no argument. It rewrites four files: `bom/rack-bom.csv`, `bom/README.md`,
`bom/jlc-parts.md` and `site/assets/bom.json`, the data of the interactive bill. Do not edit these files by
hand.

The PCB lines do not change with the size of your rack. Count your own PCBs on
[Order the PCBs](../plan/order-the-pcbs.md#how-many-of-each), and get their price from JLCPCB's quote.

## Cost summary

This is the cost of the 12-bay example rack, in euros before VAT. Prices change, so check them before you
order.

```{include} ../../bom/README.md
:start-after: "import VAT is extra."
:end-before: "Full line-item list"
```

What this total leaves out: [Cost and time](../plan/cost-and-time.md#what-the-price-leaves-out).

## Components of each PCB

Open a PCB below to see its components, with prices in euros. A quantity covers all the PCBs assembled in
the bill's order, not one PCB. The fab does not fit a line whose source reads "hand-solder, buy loose". The
last lines of each table are the order itself: the bare PCBs, the assembly fees, and a line that brings the
catalogue prices up to the JLCPCB quote. The references of each line (C1, U2) are in the CSV file and on the
interactive bill.

:::{dropdown} Power hub
```{bom-table}
:group: power-hub
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} Bay node
```{bom-table}
:group: bay-node
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} Camera pod
```{bom-table}
:group: camera-pod
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} DATA ×6
```{bom-table}
:group: data-port-x6
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} DATA ×4, with its logic
```{bom-table}
:group: data-port-x4
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} DATA ×4, base assembly
```{bom-table}
:group: data-port-x4-base
:columns: item, qty, ext_eur, source
:total:
```
:::

:::{dropdown} DATA ×4 panel, and shipping
The bill orders both assemblies of the DATA ×4 on one panel. This table holds the PCB and assembly lines of
the panel, then the shipping of the whole order.

```{bom-table}
:group: data-port-x4-panel, jlc
:columns: item, qty, ext_eur, source
:total:
```
:::
