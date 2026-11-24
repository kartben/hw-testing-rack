# Solder the connectors the fab leaves off

The fab places every surface-mount part and leaves the through-hole ones to you: one lead socket on a
DATA ×6, and on a DATA ×4 the same socket and five pin headers. The bay node, the power hub and the camera
pod need nothing by hand.

:::{status} designed
No v1.0 PCB has arrived (they went to the fab on 2026-11-11), so nobody has soldered one. Faces, pins and
clearances are read from the design files; the pictures are KiCad renders, drawn with the hand-soldered
parts in place. [What exists today](../plan/status.md#the-five-pcbs).
:::

Tools: a soldering iron, a magnifier and a multimeter; for a DATA ×4, Kapton tape as well, and side
cutters and fine sandpaper if it came as a panel
([Tools and bench equipment](../plan/shopping-list.md#tools-and-bench-equipment)). A connector soldered on
the wrong face or the wrong way round stays there: [What cannot be undone](index.md#solder).

## What comes unsoldered

| PCB | Part | Sits on | Soldered on |
|---|---|---|---|
| DATA ×6 | J1, the lead's socket, JST PH 8 vertical (B8B-PH-K-S) | rear face | front face |
| DATA ×4 | J1, the same socket | rear face | front face |
| DATA ×4 | J102, J202, J302, J402: four 2 × 6 pin headers, 2.54 mm | front face | rear face |
| DATA ×4 with its logic | J2: a 1 × 5 pin header, 2.54 mm (SWD) | front face | rear face |

Read from the `Assembly` column ("hand-solder, buy loose (LCSC)") of
[data-port-x6-bom.csv](../../electronics/data-port-x6/data-port-x6-bom.csv) and
[data-port-x4-bom.csv](../../electronics/data-port-x4/data-port-x4-bom.csv). The front face is the one the
fab populates, with the USB-C receptacles; it faces the drawer's port wall. The loose parts are an order of
their own, listed on the [shopping list](../plan/shopping-list.md#the-connectors-the-fab-leaves-off).

A rack with a DATA ×6 in every drawer stops after the next section.

## The lead's socket on a DATA ×6

Worked out from [config/rack.yaml](../../config/rack.yaml) (`pcb.data_port_x6.lead`) and the footprint in
[data-port-x6.kicad_pcb](../../electronics/data-port-x6/data-port-x6.kicad_pcb); nobody has done it yet.

:::{build-step} 1
:image: ../img/pcbs/data-port-x6-j1-rear.jpg
:alt: KiCad render, rear face of a DATA ×6: J1 fitted, its pin names printed beside it
:parts: socket JST B8B-PH-K-S=1

**J1 goes on the rear face**, the bare one, at the end behind port 6. Its outline is printed there with
the name of each pin beside it: from the top VIN, GND, D+, D−, GND, SDA, SCL, NC, and "LEAD 20 V" under it.
Push the eight pins through from this face. The socket's mouth then points away from the PCB: the DATA
lead plugs in from behind and drops into the drawer's cable window.
:::

:::{build-step} 2

**Which way round.** Eight pins in a row fit both ways. The housing does not sit centred on them: 2.8 mm of
it lies on the side of the pin row towards the middle of the PCB, 1.7 mm on the side of the pin names, and
the printed outline shows it. A housing turned round overhangs that outline. Pin 1 is the lowest pin, the
one named NC, on the square pad with the corner mark; pin 8, VIN, is at the top.

A socket soldered the other way round acts as a 1:1 lead would: the node's 20 V lands on pin 1, which is
not connected, nothing on the PCB is powered, and the node keeps the lead off with
`SCL or SDA held low: DATA lead reversed?` ([What a wrong cable does](../reference/cables.md#what-a-wrong-cable-does)).
:::

:::{build-step} 3
:image: ../img/pcbs/data-port-x6-j1-front.jpg
:alt: KiCad render, front face of a DATA ×6: the eight pads of J1 in a column beside port 6

**Solder the eight pins on the front face**, where they come out in a column beside port 6, among the
fab's parts. Pin 8 carries the node's 20 to 28 V, and an SCL track passes 0.24 mm from its pad under the
solder mask: look for bridges under the magnifier before the PCB sees a supply.
:::

Stage 2 of [the DATA ×6's checklist](check-the-pcbs/data-x6.md) then measures VIN against GND with no
power, and stage 4 plugs the lead.

## Part a DATA ×4 panel

Only if your DATA ×4 PCBs came as the order panel: one PCB with its logic and one base PCB, turned 180°,
top edge to top edge, 2 mm apart, on a 100 × 142 mm panel. The order of 2026-11-11 is recorded as
DATA ×4 PCBs assembled with their logic, not as panels.

```{figure} ../img/pcbs/data-port-x4-panel-top.jpg
:alt: KiCad render of the DATA ×4 order panel, two PCBs joined by two tabs
:width: 55%

KiCad render. The two tabs sit on the joint, 9 mm in from each end. The base, above, is the PCB with the
empty footprints where the logic has its two crosspoint switches and its RP2350B.
```

Cut each tab with side cutters, through its two rows of small holes, then sand the stubs flush. Do not
snap the joint: bending it strains the 0402 parts that lie along both top edges
([electronics.md](../electronics.md), "Order panel").

## The socket and the headers of a DATA ×4

Worked out from [config/rack.yaml](../../config/rack.yaml) (`pcb.data_port_x4_v2`), the PCB file and the
[design review of 2026-11-09](../pcb-review-2026-11-09.md); nobody has done it yet.

:::{build-step} 1
:name: x4-step-1
:parts: socket JST B8B-PH-K-S=1

**J1** sits where it does on the DATA ×6, under the same outline and pin names, and goes in the same way
round. Push it in from the rear face; do not solder yet.
:::

:::{build-step} 2
:name: x4-step-2
:image: ../img/pcbs/data-port-x4-j1-front.jpg
:alt: KiCad render, front face of a DATA ×4: the pads of J1 in a column, the array RN3 above the top one

**Pin 8 last, and Kapton first.** On the front face, pin 8 (VIN, 20 to 28 V) is the top pad of the column.
It comes out 0.58 mm from an open pad of RN3, a small resistor array of the USB hub, and 0.30 mm from a
track of port 4's D+. A solder bridge there puts the lead's voltage on a pin of the hub and, through
port 4, on your board's D+; the node's current limit does not protect a 3.3 V pin. Cover RN3 with Kapton
tape, solder pins 1 to 7, then pin 8. Check under the
magnifier, and with the ohmmeter that pin 8 is not joined to RN3, before the first power.
:::

:::{build-step} 3
:name: x4-step-3
:image: ../img/pcbs/data-port-x4-headers-front.jpg
:alt: KiCad render, front face of a DATA ×4: four 2 × 6 headers under their printed names, the SWD header on the top edge
:parts: 12-pin header (2 × 6)=4

**The four 2 × 6 headers on the front face**, one over each port, under the names printed for its pins.
Their tails come 1.5 mm out of the rear face: solder them there, each header square to the PCB. Dupont
jumpers go from these pins to your boards ([Wires between boards](../use/wires.md)).
:::

:::{build-step} 4
:name: x4-step-4
:parts: 5-pin header (1 × 5)=1

**The 1 × 5 header J2** on the top edge of the front face, on a PCB with its logic only. It is the
co-processor's SWD port, for a debug probe: the logic analyzer is loaded over USB and does not need it.
:::

J1 is enough for stages 1 to 4 of [the DATA ×4's checklist](check-the-pcbs/data-x4.md): the headers can
wait until the PCB has passed them.

On a base DATA ×4 (no logic) only GND, RESET and BOOT of each header are live. The design log has it take
two 2 × 1 pieces per port in the header's end columns, 16 joints in all, while its bill of materials lists
the 2 × 6 headers; both fit the same holes, and the sources do not say which is meant. What each pin
carries is on the [DATA ×4's page](../reference/pcbs/data-x4.md), and the DATA ×6's lead socket on
[its own](../reference/pcbs/data-x6.md).

A step that does not match your PCBs: [Report a finding](../reference/known-limitations.md#report-a-finding).
