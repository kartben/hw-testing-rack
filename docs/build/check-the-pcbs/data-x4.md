# Check a DATA ×4

The DATA ×4 is the DATA board for a bay with wires. It has four USB-C ports behind a USB hub, with a pin
header over each port. The node switches each port on and off and measures its voltage
and current.

It comes in two versions. With its logic fitted, it also has a switch matrix for the pins, and an RP2350B
co-processor that runs the logic analyzer. The base version has neither: on a base board, skip the checks marked "logic only" and
step 5. [The DATA ×4's PCB page](../../reference/pcbs/data-x4.md) describes both.

The pads are named in print on the rear face.

## 0. Solder the connectors

The fab leaves the through-hole parts off. Solder them by hand, in this order:

1. J1, the socket for the DATA lead (JST PH 8, B8B-PH-K-S), on the rear face.
2. The four 2 × 6 pin headers, J102, J202, J302 and J402.
3. With the logic only, the 1 × 5 SWD header, J2.

J1 is enough for steps 1 to 4. [Solder the connectors](../solder-the-connectors.md) shows which face, which
way round and how to part the panel.

## 1. Look it over

```{figure} ../../img/pcbs/data-port-x4-top.jpg
:alt: The front face of the DATA ×4 v1.0
:width: 80%

KiCad render, front face, headers soldered. U11 is the square chip at the top centre, with L1 right under it.
U1, the USB hub, is at the upper right.
```

- [ ] The pin-1 marks of U1 (the USB hub), U2 and U6 (the port expanders) and U13 (the 5 V buck).
- [ ] At each port n, the pin-1 marks of Un01 (the power switch), Un02 (the INA226) and Un03 (the ESD array).
- [ ] C60, the electrolytic can: its black mark is the minus side.
- [ ] The four USB-C receptacles stand straight, their two pegs in their holes.

With the logic fitted:

- [ ] U11, the RP2350B, the 80-pin chip: its pin-1 dot. Under the magnifier, no bridge between its pins
  (0.4 mm pitch).
- [ ] The pin-1 marks of U7 and U8 (the two crosspoint switches), U10 (the matrix expander), U9 (the −5 V
  inverter) and, at each port n, Un07 (the level translator).
- [ ] L1, the small inductor beside U11: its dot is on pad 1, the pad nearer C33.

## 2. Measure for shorts

```{figure} ../../img/pcbs/data-port-x4-bottom.jpg
:alt: The rear face of the DATA ×4 v1.0, with its named test pads
:width: 80%

KiCad render, rear face, with J1 at the left.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, +5V, +3V3, 1V8 | no short: the reading climbs, or stays above about 100 Ω |
| +5V_MX, −5V, +3V3_CP, +1V1 (logic only) | no short |

## 3. Power it on its own

Connect a bench supply to the VIN and GND pads, with a limit of 0.3 A. The VIN pad is 1.45 mm from the SDA
pad: 20 V on SDA can destroy the meters and the port expanders, so keep the probe and the clip off it. Raise
the voltage from 0 to 20 V.

| Check | Expect |
|---|---|
| +5V, below about 13.5 V | 0 V |
| +5V, at 20 V | 5.08 V (4.94 to 5.22 V) |
| +3V3 | 3.3 V (3.2 to 3.4 V) |
| 1V8 | 1.8 V |
| +3V3_CP (logic only) | 3.3 V (3.2 to 3.4 V) |
| +5V_MX (logic only) | the same as +5V |
| −5V (logic only) | about −5 V |
| +1V1 (logic only) | 1.1 V (1.07 to 1.13 V) |
| FLT1 to FLT4 | 3.3 V |
| The supply's current | well under the limit: write it down |

## 4. Plug it into a node

Check the DATA lead (JST PH 8, "Same direction") with the meter first: pin n goes to pin 9 − n. Type
`bay power off`, then plug the lead into J7 (DATA) on the node and J1 on the DATA ×4. Never plug or unplug a
powered DATA lead: it can destroy the node's I²C pins or this PCB's USB hub.

| Check | Expect |
|---|---|
| `bay power on` | DATA VIN at the row's voltage; the log says "DATA x4: 4 ports, every port off; switching on the wanted ones"; no fault |
| `bay usb` | the DATA board's hub. With the logic, also the co-processor, in its USB bootloader, on port 5 of the hub |
| `bay port` | "DATA x4, 4 ports" and one line per port, every port on. Port n is on busid 1-1.n |
| A USB device in port 1, then `bay port 1 off` and `on` | VBUS1 follows; `bay usb` shows the device; `bay port 1` shows its voltage (4.82 to 5.22 V) and its current |
| `bay port 1 off` | the device gone |

Repeat on ports 2 to 4. On I²C, the node finds 0x20 and 0x21 (the port expanders), 0x38 (the matrix
expander, logic only), and 0x41, 0x43, 0x44 and 0x45 (the four INA226).

## 5. Check the matrix and the logic analyzer

You build the analyzer image yourself:
[Load the analyzer image](../../use/logic-analyzer.md#load-the-analyzer-image-once) gives the steps. Loading it
into the node needs the node's [admin key](../../use/access.md).

| Check | Expect |
|---|---|
| `python tools/bayctl.py coproc load <bay> LogicAnalyzer.uf2`, then `coproc status <bay>` | the image is stored in the node |
| `bay power cycle`, then `bay usb` | the co-processor is no longer in its bootloader: the node has loaded the analyzer into it |
| The bay's page | a Wires card and a Logic analyzer card |

Then plug a board into port 1. On the header of port 1, wire the board's I/O supply to VREF, its GND to GND
and its UART TX to P1. The pins of a port stay open without VREF. On the Wires card, put P1 of port 1 on
bus A and click Apply.

| Check | Expect |
|---|---|
| The Wires card | P1 shows on bus A |
| **Capture and reset** on port 1, in the Logic analyzer card | the capture shows the board's boot messages on bus A |

[Wires between boards](../../use/wires.md) explains how to use the matrix.
