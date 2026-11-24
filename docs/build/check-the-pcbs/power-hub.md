# Power hub checklist

The hub turns a USB-C PD charger into the rack's supply (VRACK) and switches it to four rows
through eFuses.  Its connectors and pads are listed on [its PCB page](../../reference/pcbs/power-hub.md);
the pads below go by the names printed on the bottom face.

:::{status} designed
No power hub v1.0 has been powered or measured: the expected values are the design's.
[What exists today](../../plan/status.md#status-power-hub).
:::

## 1. Look

```{figure} ../../img/pcbs/power-hub-top.jpg
:alt: The top face of the power hub v1.0
:width: 70%

KiCad render of the power hub v1.0, top face.  J1, the PD input, is at the upper right and J6, the console,
at the lower right; the row sockets J2 to J5 are on the left edge, row A at the bottom.
```

- [ ] The pin-1 marks of U1 (CH224A, the PD controller), U2 (the 5 V buck), U3 (the 3.3 V regulator),
  U6 (the CAN transceiver) and U11–U14 (the row eFuses); the module's antenna at the PCB's edge.
- [ ] C8, the tall 100 µF can: its black mark is the minus side.
- [ ] The LEDs, the two USB-C receptacles (J1 the PD input, J6 the console) and the four row
  sockets: seated flat, no lifted pin.

## 2. No power

```{figure} ../../img/pcbs/power-hub-bottom.jpg
:alt: The bottom face of the power hub v1.0, with its named test pads
:width: 70%

KiCad render of the bottom face: the pads of this checklist, by the names printed beside them.
```

| Ohmmeter between GND and | Expect |
|---|---|
| VRACK, VHV, 5V BUCK, 5V, USB 5V, 3V3 | no short: the reading climbs, or stays above ≈ 100 Ω |
| ROW A, ROW B, ROW C, ROW D | no short |

Between CANH and CANL: ≈ 56 Ω (the bus's two terminations are both here).

## 3. First power

**a. The console USB-C alone** (J6, from a laptop; it powers the controller, not the rows).

| Pad | Expect |
|---|---|
| USB 5V | ≈ 5 V |
| 5V | 0.3–0.5 V under USB 5V (it comes through a Schottky diode) |
| 3V3 | 3.3 V (3.2–3.4 V) |
| VRACK, ROW A–D | 0 V |

The laptop sees a new serial port (the ESP32-S3's USB-Serial-JTAG), with a blank module too.

**b. A PD charger on J1**, console unplugged, nothing on the rows, no firmware yet.

| Pad | Expect |
|---|---|
| VRACK, VHV | 9 V: the CH224A asks for it by itself at plug-in |
| 5V BUCK | 5.24 V (5.1–5.4 V) |
| 3V3 | 3.3 V |
| ROW A–D | 0 V: the rows stay off without firmware |

The PD LED is on ([what each LED of the hub shows](../../reference/leds-and-buttons.md)).  If VRACK stays at
5 V, try another charger before suspecting the PCB.

## 4. Flash and ask

Console USB-C to the laptop, charger plugged.  The port and the image:
[Flash the hub](../flash.md#flash-the-hub).

```console
$ west flash -d build-hub
```

Then a terminal on the same port (115200).  The hub's shell is on this port only, and no image carries its
Wi-Fi network: type it here, now ([Wi-Fi in the rack](../../use/wifi.md) says which network).

```console
uart:~$ hub status
uart:~$ hub pd
uart:~$ wifi cred add -s <ssid> -k 1 -p <password>
uart:~$ wifi cred auto_connect
```

`hub pd` shows the contract and what the charger offers.  Once on the network the hub answers at
`http://rack.local/`.  Leave it unnamed: `hub id` is only for two racks on one network
([Bays, ports and addresses](../../use/names.md) says what it changes).  Every command of this shell:
[Power hub shell](../../reference/hub-shell.md).

| Check | Expect |
|---|---|
| `hub pd` | a 20 V contract |
| VRACK pad | 20 V; VSNS ≈ 1.8 V |
| Half a second later, one row after the other | ROW A–D at VRACK, EN A–D ≈ 1.65 V, FLT A–D ≈ 3.3 V, no red LED |
| `hub row A off`, then `on`, then `cycle` | ROW A follows; the other rows don't move |
| `west flash -d build-hub` again, rows on | the rows stay on through the flash (never tried: note the result) |

## 5. Load

A row lead in row A's socket (J2; rows B, C, D are J3, J4, J5).  The supply is on the socket's
pin 6, GND on pins 2 and 5; at the lead's free end that is pin 1 and pins 2 and 5.  Confirm it
with the meter (continuity to the ROW A pad), then put the 47 Ω 10 W resistor between the two
for a few seconds: it takes 0.43 A and gets hot.

| Check | Expect |
|---|---|
| IMON A pad | ≈ 0.6 V (1.4 V per ampere) |
| `hub status` | ≈ 0.43 A on row A |
| ROW A pad | still at VRACK |

The same on rows B, C and D.

## 6. Last

- [ ] The module's one-time fuse (`DIS_USB_OTG_DOWNLOAD_MODE`), once everything above passed, and only on
  a hub that goes into the rack.  It [cannot be undone](../index.md#fuse); the command is on
  [Flash the hub and the nodes](../flash.md#the-modules-one-time-fuse).
- [ ] On the first hub of a revision, the measurements the reviews left for it (several chargers, the VHV pin
  at plug-in, a shorted row): [More to measure](index.md#more-to-measure-on-the-first-pcbs-of-a-revision).

A hub that passed goes into [the power box](../power-box.md).  A reading that does not match:
[report it](../../reference/known-limitations.md#report-a-finding).
