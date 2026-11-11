# Bring-up: DATA ×4 v1.0

The board of a bay with wires: four switched and measured USB-C ports behind a USB hub, a pin
header per port, a switch matrix and a logic analyzer (the RP2350B co-processor).  Fed by the
node's DATA lead (20 V, USB and I²C).  Test pad names are the ones printed on the rear face.
Back to [bring-up.md](../bring-up.md).

## 0. Solder

The fab does not fit the through-hole parts.  By hand: J1 on the rear face (the lead's socket,
JST PH 8, B8B-PH-K-S), then the four 2 × 6 pin headers J102, J202, J302, J402 and the 1 × 5 SWD
header J2.  J1 is enough for stages 1 to 4.

## 1. Look

- U11, the RP2350B (the 80-pin chip, 0.4 mm pitch): its pin-1 dot, and no bridge between pins
  under the magnifier.  This is the part the fab was asked about.
- The pin-1 marks of U1 (the USB hub), U7 and U8 (the two crosspoint switches), U2, U6 and U10
  (the expanders), U9 (the −5 V inverter), U13 (the 5 V buck), and at each port n: Un01 (the power
  switch), Un02 (the INA226), Un03 (the ESD array) and Un07 (the level translator).
- L1, the small inductor beside U11: its dot on pad 1.  C60, the electrolytic can: its black mark
  is the minus side.
- The four USB-C receptacles standing straight, their two pegs in their holes.

## 2. No power

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, +5V, +3V3, 1V8 | no short: the reading climbs, or stays above ≈ 100 Ω |
| +5V_MX, −5V, +3V3_CP, +1V1 | no short |

## 3. First power, alone

Bench supply, limit 0.3 A, on the VIN and GND pads.  Raise the voltage from 0 to 20 V.

| Check | Expect |
|---|---|
| Under ≈ 13.5 V | +5V at 0 V |
| At 20 V: +5V | 5.08 V (4.94–5.22 V) |
| +3V3, +3V3_CP | 3.3 V (3.2–3.4 V) |
| 1V8 | 1.8 V |
| +5V_MX | as +5V |
| −5V | ≈ −5 V |
| +1V1 | 1.1 V |
| FLT1 … FLT4 | 3.3 V |
| The supply's current | well under the limit: write it down |

## 4. On a node

A DATA lead (JST PH 8, "Same direction") from the node's J7 (DATA) to J1.  Check the lead with
the meter first: pin n goes to pin 9 − n.

| Check | Expect |
|---|---|
| `bay power on` | DATA VIN at the row's voltage; the board answers; no fault |
| `bay usb` | the board's hub, and on its port 5 the co-processor in its USB bootloader |
| `bay port` | four ports, all off |
| `bay port 1 on`, a USB device in port 1 | `bay usb` shows the device; `bay port 1` its voltage (4.82–5.22 V) and current |
| `bay port 1 off` | the device gone |

The same on ports 2 to 4.  The chips the node finds on I²C: 0x20 and 0x21 (the port expanders),
0x38 (the matrix expander), 0x41, 0x43, 0x44, 0x45 (the four INA226).

## 5. The logic side

Not tried on hardware yet: write down what happens at each step.

| Check | Expect |
|---|---|
| `python tools/bayctl.py coproc load <bay> <analyzer>.uf2`, then `coproc status <bay>` | the image stored in the node |
| `bay power cycle`, `bay usb` | the co-processor is no longer a bootloader: the node loaded the analyzer into it |
| The bay's page | a Wires card and a Logic analyzer card |
| A board on port 1: its VREF and GND on the header, its UART TX on P1.  Wires card: port 1's P1 on bus A, Apply | the pin shows on bus A (a port's pins stay open without VREF) |
| Logic analyzer card, **Capture and reset** on that port | the capture shows the board's boot messages on A |

The co-processor, the matrix and the analyzer: [firmware/README.md › Wires](../../firmware/README.md#wires)
and [› Logic analyzer](../../firmware/README.md#logic-analyzer).

## 6. Later

VBUS at each receptacle against the total load, the ports off at power-up, no back-feed with the
lead off: [electronics.md › Bring-up measurements](../electronics.md#bring-up-measurements).
