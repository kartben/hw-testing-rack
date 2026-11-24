# Solder the connectors

The fab fits every surface-mount part. You solder the through-hole connectors of the DATA boards yourself.
The bay node, the power hub and the camera pod need no soldering.

You need a soldering iron, a magnifier and a multimeter. For a DATA ×4, add Kapton tape. If your DATA ×4 PCBs
came as a panel, add side cutters and fine sandpaper. You [cannot remove a connector](index.md#solder) once it
is soldered, so check the face and which way round it goes before the first joint.

## What to solder

The DATA ×4 comes in two assemblies of the same PCB. *With its logic*, it carries the bay's logic analyzer.
The *base* leaves those parts off.

| PCB | Part | Fit on | Solder on |
|---|---|---|---|
| DATA ×6 and DATA ×4 | J1, the DATA lead's socket (JST B8B-PH-K-S) | rear face | front face |
| DATA ×4 | J102, J202, J302, J402, four 2 × 6 pin headers | front face | rear face |
| DATA ×4 with its logic | J2, a 1 × 5 pin header (SWD) | front face | rear face |

From the bills of materials of the [DATA ×6](../../electronics/data-port-x6/data-port-x6-bom.csv) and the
[DATA ×4](../../electronics/data-port-x4/data-port-x4-bom.csv).

The headers are 2.54 mm pitch. The front face is the one with the USB-C receptacles and the parts the fab
fitted. You order the loose connectors yourself:
[Shopping list](../plan/shopping-list.md#the-connectors-the-fab-leaves-off).

## Solder J1 on a DATA ×6

:::{build-step} 1
:image: ../img/pcbs/data-port-x6-j1-rear.jpg
:alt: KiCad render, rear face of a DATA ×6: J1 fitted, its pin names printed beside it
:parts: socket JST B8B-PH-K-S=1

**J1 goes on the rear face**, the bare one, at the end behind port 6. Its outline is printed there, with the
name of each pin beside it. Push the eight pins through from this face. The socket's mouth points away from
the PCB, so the DATA lead plugs in from behind.
:::

:::{build-step} 2

**Check which way round it is.** The socket fits on its pins both ways, but it is not centred on them. The
right way round, it sits over the printed outline, offset towards the middle of the PCB. The wrong way round,
it overhangs the outline. Pin 1 (NC), on the square pad, is the lowest pin. Pin 8 (VIN) is at the top.

Soldered the wrong way round, the socket powers nothing on the PCB. The node keeps the lead off and reports
`SCL or SDA held low: DATA lead reversed?`.
:::

:::{build-step} 3
:image: ../img/pcbs/data-port-x6-j1-front.jpg
:alt: KiCad render, front face of a DATA ×6: the eight pads of J1 in a column beside port 6

**Solder the eight pins on the front face**, where they come out in a column beside port 6. Pin 8 carries
20 V from the node, and a track passes 0.24 mm from its pad. Look for bridges under the magnifier before the
PCB sees a supply.
:::

Then go to the [DATA ×6 checklist](check-the-pcbs/data-x6.md). It measures the socket before any power goes
on.

## Part a DATA ×4 panel

Skip this if your DATA ×4 PCBs came single. The order panel holds one PCB with its logic and one base PCB,
top edge to top edge.

```{figure} ../img/pcbs/data-port-x4-panel-top.jpg
:alt: KiCad render of the DATA ×4 order panel, two PCBs joined by two tabs
:width: 35%

KiCad render. The two tabs sit on the joint, 9 mm in from each end. The base PCB, above, has empty footprints
where the logic's chips go.
```

Cut each tab with side cutters, through its two rows of small holes, then sand the stubs flush. Do not snap
the joint: bending it strains the small parts along both top edges.

## Solder J1 and the headers on a DATA ×4

:::{build-step} 1
:name: x4-step-1
:parts: socket JST B8B-PH-K-S=1

**J1** goes in as on the DATA ×6: same place, same outline, same way round. Push it in from the rear face, but
do not solder it yet.
:::

:::{build-step} 2
:name: x4-step-2
:image: ../img/pcbs/data-port-x4-j1-front.jpg
:alt: KiCad render, front face of a DATA ×4: the pads of J1 in a column, the array RN3 above the top one

**Cover RN3 with Kapton and solder pin 8 last.** Pin 8 (VIN, 20 V) is the top pad of the column on the front
face. It sits 0.58 mm from an open pad of the resistor array RN3 and 0.30 mm from a track of port 4. A bridge
there puts 20 V on the USB hub and on the board in port 4. Solder pins 1 to 7, then pin 8. Check under the
magnifier, then with the ohmmeter, that pin 8 does not touch RN3.
:::

:::{build-step} 3
:name: x4-step-3
:image: ../img/pcbs/data-port-x4-headers-front.jpg
:alt: KiCad render, front face of a DATA ×4: four 2 × 6 headers under their printed names, the SWD header on the top edge
:parts: 12-pin header (2 × 6)=4

**Fit the four 2 × 6 headers on the front face**, one over each port, under their printed pin names. Solder
them on the rear face, each header square to the PCB. Your boards' jumper wires plug in here
([Wires between boards](../use/wires.md)).
:::

:::{build-step} 4
:name: x4-step-4
:parts: 5-pin header (1 × 5)=1

**Fit the 1 × 5 header J2** on the top edge of the front face, on a DATA ×4 with its logic only. It is the
co-processor's SWD port, for a debug probe. The logic analyzer does not need it.
:::

The headers can wait: J1 alone is enough for steps 1 to 4 of the
[DATA ×4 checklist](check-the-pcbs/data-x4.md). On a base DATA ×4, only GND, RESET and BOOT of each header are
wired. What each pin carries is on the [DATA ×4 page](../reference/pcbs/data-x4.md).
