# Camera pod

The camera pod's PCB joins an Arducam Mega and four white LEDs to the bay node's CAM socket with two
ready-made cables: nothing is crimped or soldered.

:::{status} designed
v1.0 has been at the fab since 2026-11-11 and none is on a bench. Every value on this page is the design's, read
from `design.py` and the bill of materials; nothing has been measured.
[What exists today](../../plan/status.md#status-camera-pod).
:::

```{figure} ../../img/pcbs/camera-pod-top.jpg
:class: bb-screenshot
:alt: KiCad render of the component face of the camera pod's PCB
:width: 55%

KiCad render of the component face. The four LEDs line the edge beside the camera; the lead plugs in on the
right, the camera's cable on the six pins below.
```

| | |
|---|---|
| Revision | v1.0, printed "CAM POD v1.0 2026-11" on the bare face |
| Size | 40 × 27 mm, 1.6 mm, 2 layers, lead-free HASL |
| One per | camera, in the printed pod under a bay's ceiling, components down, on two PT 2.6 screws |
| Regulator | AP2114H-3.3; never the AP2114HA, whose pinout differs |
| Fitted by the fab | all 14 parts; nothing to solder by hand |

## Connectors and pinouts

| Connector | Type | Where | Takes |
|---|---|---|---|
| J1, LEAD | JST PH 8, side entry (S8B-PH-SM4-TB) | a short edge, mouth outwards | the camera lead from the node's J6 |
| J2, MEGA | 1 × 6 pin header, 2.54 mm, surface-mount | along the long edge opposite the LEDs | the Arducam Mega's own 6-pin cable |

J1 is the node's J6 mirrored, so one "Same direction" JST PH 8 lead joins them, of the same type as the
DATA lead ([Cables and pinouts](../cables.md#camera-lead)):

```{include} ../cables.md
:start-after: <!-- site:camera-lead-pinout -->
:end-before: <!-- /site:camera-lead-pinout -->
```

J2 follows the Mega's own order, and the six names are printed under it, from pin 1:

```text
VCC  GND  SCK  MISO  MOSI  CS
```

VCC is the pod's 3.3 V, not the lead's 5 V.

The bare face carries nine test pads, named in print: GND, 5V and 3V3 in a row, a second GND at the far
end, and SCK, MOSI, MISO, CS and LED (the LEDs' switched cathodes) by J1. Their values at first power are in
[the pod's checklist](../../build/check-the-pcbs/camera-pod.md).

## The camera and the light

An Arducam Mega 3MP with the SPI interface, in its M12 version (B0434, 33 × 33 mm). Arducam gives it 69 mA
idle and up to 317 mA working. Fed 3.3 V by the pod, its MISO is a 3.3 V output, which is what the node
expects. The bill pairs it with the Arducam LN018, an M12 lens of 145°, the stock 90° being too narrow for a large
board ([Shopping list](../../plan/shopping-list.md#camera-parts)).

The camera's cable is a JST XH 2.54 with six pins at the camera and Dupont sockets at J2; the Mega's own
cable does if it ends in Dupont sockets. The pod goes together on
[Add a camera](../../build/camera.md), and its picture and light are worked from [Camera](../../use/camera.md).

The light is four white 2835 LEDs (XL-2835UWC-02), each fed from the lead's 5 V through its own 100 Ω.
Their cathodes share one line, LED_K, which the node pulls low to light them, steadily or by PWM: all four
or none. In the pod a thin PETG diffuser sits 5 to 10 mm in front of them.

## Ratings

| | Design value |
|---|---|
| Supply | the node's CAM_5V on J1 pin 6: its 5 V rail (5.24 V at the node) behind a 0.75 A resettable fuse |
| Camera supply | 3.3 V from the AP2114H; about 0.5 W in the regulator at the camera's 317 mA |
| LEDs | 18 to 26 mA each, 102 mA at most for the four |
| SPI | 3.3 V on both sides, 4 MHz, mode 0; the lead is about 50 cm |

## Files

| | |
|---|---|
| Schematic | [camera-pod-schematic.pdf](../../../electronics/camera-pod/docs/camera-pod-schematic.pdf) |
| Source and KiCad project | [electronics/camera-pod/](../../../electronics/camera-pod/), generated from [design.py](../../../electronics/camera-pod/design.py) |
| Bill of materials | [camera-pod-bom.csv](../../../electronics/camera-pod/camera-pod-bom.csv) |
| Fabrication files | [camera-pod-fab.zip](/downloads/camera-pod-fab.zip): Gerbers, JLCPCB's BOM and placement file, the content of [electronics/camera-pod/fab/](../../../electronics/camera-pod/fab/) |
| Positions the printed pod is drawn around | `pcb.camera_pod` in [config/rack.yaml](../../../config/rack.yaml) |

## Known issues of v1.0

From the [design review of 2026-11-09](../../pcb-review-2026-11-09.md) (in French; its finding numbers are
in brackets) and the design log, calculated or read from the layout, none measured.

<!-- site:known-issues -->
- A camera that hangs needs the bay's power cycled, and a bay's power is its row's: the Mega has no reset
  pin, and the node has no switch on the camera's 5 V, only a fuse.
- The six names printed under J2 do not line up with its pins: the text is 17.4 mm wide for pins that
  span 12.7 mm. The order is right, VCC at pin 1. With six separate Dupont wires, count the pins; a
  one-piece 6-pin housing cannot go wrong. [CP-1]
- The 3.3 V regulator has little copper to cool it. At the camera's full 317 mA, in a closed pod at 40 to
  45 °C, its junction is reckoned at 100 to 115 °C, for a limit of 125 °C; at the 180 mA or so of a
  stream the margin is wide. [CP-2]
- MISO has no series resistor at the camera's end of the 50 cm lead: overshoot is possible at the node.
  At 4 MHz it usually passes. [CP-3]
- What the Mega draws on 3.3 V while it captures is not known: Arducam's 317 mA is given at 5 V.
<!-- /site:known-issues -->
