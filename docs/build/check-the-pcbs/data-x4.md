# DATA ×4 checklist

The DATA board of a bay with wires: four switched and measured USB-C ports behind a USB hub, a pin
header per port, a switch matrix and a logic analyzer (the RP2350B co-processor), all fed by the
node's DATA lead (20 V, USB and I²C).  Test pad names are the ones printed on the rear face; the
ports, the pin header and the two assemblies are on [the DATA ×4's PCB page](../../reference/pcbs/data-x4.md).

:::{status} designed
No DATA ×4 v1.0 has been powered or measured: the expected values are the design's.  Stage 5, the
logic side, has never run on this PCB.  The node's code for it is tested on native_sim against
emulated chips, and the co-processor's loading ran on a Pico 2 behind a bench XIAO (2026-11-03).
[What exists today](../../plan/status.md#status-data-x4).
:::

## 0. Solder

The fab does not fit the through-hole parts.  By hand: J1 on the rear face (the lead's socket,
JST PH 8, B8B-PH-K-S), then the four 2 × 6 pin headers J102, J202, J302, J402 and the 1 × 5 SWD
header J2.  J1 is enough for stages 1 to 4.  Which face, which way round, and how the panel is
parted: [Solder the connectors](../solder-the-connectors.md).

## 1. Look

```{figure} ../../img/pcbs/data-port-x4-top.jpg
:alt: The front face of the DATA ×4 v1.0
:width: 80%

KiCad render of the DATA ×4 v1.0, front face, with its headers soldered: the four ports and, over each, its
2 × 6 header.  U11 is the square chip at the top centre, with L1 right under it; U1, the USB hub, is the one at
the upper right.
```

- [ ] U11, the RP2350B (the 80-pin chip, 0.4 mm pitch): its pin-1 dot, and no bridge between pins
  under the magnifier.  The project's own order asked the fab about this part.
- [ ] The pin-1 marks of U1 (the USB hub), U7 and U8 (the two crosspoint switches), U2, U6 and U10
  (the expanders), U9 (the −5 V inverter), U13 (the 5 V buck), and at each port n: Un01 (the power
  switch), Un02 (the INA226), Un03 (the ESD array) and Un07 (the level translator).
- [ ] L1, the small inductor beside U11: its dot on pad 1.  C60, the electrolytic can: its black mark
  is the minus side.
- [ ] The four USB-C receptacles standing straight, their two pegs in their holes.

## 2. No power

```{figure} ../../img/pcbs/data-port-x4-bottom.jpg
:alt: The rear face of the DATA ×4 v1.0, with its named test pads
:width: 80%

KiCad render of the rear face: J1 at the left with the names of its eight pins, and the pads of this
checklist.  The pads marked LOGIC ONLY belong to the assembly with the matrix and the co-processor.
```

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
| `bay power on` | DATA VIN at the row's voltage; the log says "DATA x4: 4 ports, every port off; switching on the wanted ones"; no fault |
| `bay usb` | the DATA board's hub, and on its port 5 the co-processor in its USB bootloader |
| `bay port` | "DATA x4, 4 ports": port n on busid 1-1.n; each on, one after the other (`CONFIG_BAY_PORTS_ON_AT_BOOT`) |
| `bay port 1 off`, then `on`, a USB device in port 1 | VBUS1 follows; `bay usb` shows the device; `bay port 1` its voltage (4.82–5.22 V) and current |
| `bay port 1 off` | the device gone |

The same on ports 2 to 4.  The chips the node finds on I²C: 0x20 and 0x21 (the port expanders),
0x38 (the matrix expander), 0x41, 0x43, 0x44, 0x45 (the four INA226).

## 5. The logic side

Not tried on hardware yet: write down what happens at each step.  The analyzer image is not shipped
with the project: [Logic analyzer](../../use/logic-analyzer.md) says where the UF2 comes from.

| Check | Expect |
|---|---|
| `python tools/bayctl.py coproc load <bay> <analyzer>.uf2`, then `coproc status <bay>` | the image stored in the node |
| `bay power cycle`, `bay usb` | the co-processor is no longer a bootloader: the node loaded the analyzer into it |
| The bay's page | a Wires card and a Logic analyzer card |
| A board on port 1: its VREF and GND on the header, its UART TX on P1.  Wires card: port 1's P1 on bus A, Apply | the pin shows on bus A (a port's pins stay open without VREF) |
| Logic analyzer card, **Capture and reset** on that port | the capture shows the board's boot messages on A |

The matrix in use: [Wires between boards](../../use/wires.md).

## 6. Later

On the first DATA ×4 of a revision: VBUS at each receptacle against the total load, the ports off at
power-up, no back-feed with the lead off.  [Bring-up measurements](../../electronics.md#bring-up-measurements)
gives the method; it was written for the earlier design, in which the node fed the DATA board 5 V, and its
current limits are not v1.0's.

A DATA ×4 that passed goes into its drawer on [Fit out a tray](../fit-out-a-tray.md).  A reading that does
not match: [report it](../../reference/known-limitations.md#report-a-finding).
