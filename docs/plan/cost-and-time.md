# Cost and time

This page tells you what a rack costs in parts, how long its parts take to print and how much PETG to buy.

## What a rack costs

| Rack | Parts | Print time | PETG to buy |
|---|---|---|---|
| One bay on a desk | €260, plus a charger | 9 h | 0.2 kg |
| One bay in its frame | €520 | 25 h | 0.7 kg |
| 2 × 2, 4 bays | €690 | 70 h | 1.9 kg |
| 4 × 2, 8 bays | €940 | 135 h | 3.6 kg |
| 4 × 3, 12 bays | €1,160 | 185 h | 4.9 kg |

The prices come from `tools/bom.py`. The print times are the sum of the slicer's times on
[Parts to print](../print/parts-list.md).

The prices are approximate. They include the PCBs, assembled by JLCPCB, and the charger with its cable. Each bay of these racks has a drawer, a board plate and a DATA ×6. The bay on a
desk has the base DATA ×4 ([One bay on a desk](../build/one-bay-on-a-desk.md)).

A small rack costs more for each bay, because JLCPCB assembles at least two of each PCB. A camera adds about
€60.

The 4 × 3 example in `config/rack.yaml` costs about €1,500. It has two cameras, two DATA ×4 bays and a USB
cable for each of its boards. [Cost summary](../reference/bill-of-materials.md#cost-summary) breaks its cost
down by category.

For another size, take the nearest row. To check the price of your PCBs, count them on
[Order the PCBs](order-the-pcbs.md) and get a quote on jlcpcb.com. If you build several racks, order their
PCBs together: each PCB then costs less.

## What the price leaves out

- VAT and import charges.
- Shipping from the sellers other than JLCPCB.
- Your boards, and the USB cable for each:
  [USB cables for your boards](shopping-list.md#usb-cables-for-your-boards).
- Tools and bench equipment, except the crimper:
  [Tools and bench equipment](shopping-list.md#tools-and-bench-equipment).
- The screws into the bench, a Wi-Fi access point and a Linux machine:
  [Not in the bill](shopping-list.md#not-in-the-bill).

## How long you wait

PCBs from JLCPCB take 1.5 to 2 weeks from order to delivery. You can print the frame while you wait:
[While you wait for the PCBs](stages.md#while-you-wait-for-the-pcbs).
