# Camera pod

The camera pod's PCB connects an Arducam Mega camera and four white LEDs to the CAM socket of the bay node.
It takes two ready-made cables, so there is nothing to crimp or solder.

```{figure} ../../img/pcbs/camera-pod-top.jpg
:class: bb-screenshot
:alt: KiCad render of the component face of the camera pod's PCB
:width: 55%

KiCad render of the component face. The four LEDs line the edge beside the camera. The lead plugs in on the
right, the camera's cable on the six pins below.
```

| | |
|---|---|
| Revision | v1.0, printed "CAM POD v1.0 2026-11" on the bare face |
| Size | 40 × 27 mm, 1.6 mm, 2 layers, lead-free HASL |
| One per | camera. It sits components down in the printed pod under the bay's ceiling, on two PT 2.6 screws |
| Regulator | AP2114H-3.3. Do not use the AP2114HA instead: its pinout is different |
| Fitted by the fab | all 14 parts: nothing to solder |

## Connectors

| Connector | Type | Where | Takes |
|---|---|---|---|
| J1, LEAD | JST PH 8, side entry (S8B-PH-SM4-TB) | a short edge | the camera lead from the node's J6 |
| J2, MEGA | 1 × 6 pin header, 2.54 mm, surface-mount | the long edge opposite the LEDs | the camera's 6-pin cable |

J1 is a mirror of the node's J6, so one "Same direction" JST PH 8 lead joins them
([Camera lead](../cables.md#camera-lead)):

```{include} ../cables.md
:start-after: <!-- site:camera-lead-pinout -->
:end-before: <!-- /site:camera-lead-pinout -->
```

J2 follows the Mega's own pin order. The names are printed under it, from pin 1:

```text
VCC  GND  SCK  MISO  MOSI  CS
```

VCC is the pod's 3.3 V, not the lead's 5 V.

## Test pads

The bare face has nine test pads, each with its name printed beside it. What they should read:
[Check a camera pod](../../build/check-the-pcbs/camera-pod.md).

| Where | Names as printed |
|---|---|
| In a row | GND, 5V, 3V3 |
| At the far end | GND |
| By J1 | SCK, MOSI, MISO, CS, LED (the switched cathodes of the LEDs) |

## The camera and the light

The camera is an Arducam Mega 3MP with the SPI interface, in its M12 version (B0434, 33 × 33 mm). Arducam
rates it at 69 mA idle and up to 317 mA in use. The pod feeds it 3.3 V, so it drives MISO at 3.3 V, as the
node expects. Fit it with the Arducam LN018 lens (145°). The stock 90° lens is too narrow for a large board
([Shopping list and tools](../../plan/shopping-list.md#camera-parts)).

The camera's cable has a 6-pin JST XH plug (2.54 mm) at the camera end and Dupont sockets at the J2 end. The
cable that comes with the Mega works if it ends in Dupont sockets.

The light is four white 2835 LEDs (XL-2835UWC-02). Each one is fed from the lead's 5 V through its own
100 Ω. Their cathodes share one line, LED_K. The node pulls it low to light them, steadily or by PWM. The four
LEDs always light together. In the printed pod, a thin PETG diffuser sits 5 to 10 mm in front of them.

To assemble the pod, see [Add a camera](../../build/camera.md). To use the picture and the light, see
[Camera](../../use/camera.md).

## Ratings

| | Design value |
|---|---|
| Supply | the node's CAM_5V on J1 pin 6: its 5 V rail (5.24 V) behind a 0.75 A resettable fuse |
| Camera supply | 3.3 V from the AP2114H; about 0.5 W in the regulator at the camera's 317 mA |
| LEDs | 18 to 26 mA each, 102 mA at most for the four |
| SPI | 3.3 V on both sides, 4 MHz, mode 0, over a lead of about 50 cm |

## Files

| | |
|---|---|
| Schematic | [camera-pod-schematic.pdf](../../../electronics/camera-pod/docs/camera-pod-schematic.pdf) |
| Source and KiCad project | [electronics/camera-pod/](../../../electronics/camera-pod/), generated from [design.py](../../../electronics/camera-pod/design.py) |
| Bill of materials | [camera-pod-bom.csv](../../../electronics/camera-pod/camera-pod-bom.csv) |
| Fabrication files | [camera-pod-fab.zip](/downloads/camera-pod-fab.zip): Gerbers, JLCPCB's BOM and placement file |
| Outline and positions for the printed pod | `pcb.camera_pod` in [config/rack.yaml](../../../config/rack.yaml) |

## Known issues

<!-- site:known-issues -->
- If the camera hangs, switch its row off and on at the hub. Only a power cut of its node brings it back:
  the Mega has no reset pin, and the node cannot switch the camera's 5 V.
- The six names printed under J2 do not line up with its pins, because the text is wider than the header.
  The order is right, with VCC at pin 1. With six separate Dupont wires, count the pins. A one-piece 6-pin
  housing cannot go on wrong.
<!-- /site:known-issues -->
