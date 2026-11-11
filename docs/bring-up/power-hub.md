# Bring-up: power hub v1.0

The hub turns a USB-C PD charger into the rack's supply (VRACK) and switches it to four rows
through eFuses.  Test pad names are the ones printed on the bottom face.  Back to
[bring-up.md](../bring-up.md).

## 1. Look

- The pin-1 marks of U1 (CH224A, the PD controller), U2 (the 5 V buck), U3 (the 3.3 V regulator),
  U6 (the CAN transceiver) and U11–U14 (the row eFuses); the module's antenna at the board's edge.
- C8, the tall 100 µF can: its black mark is the minus side.
- The LEDs, the two USB-C receptacles (J1 the PD input, J6 the console) and the four row
  sockets: seated flat, no lifted pin.

## 2. No power

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

The PD LED is on.  If VRACK stays at 5 V, try another charger before suspecting the board.

## 4. Flash and ask

Console USB-C to the laptop, charger plugged.

```bash
west flash -d build-hub            # MCUboot, then the application
```

Then a terminal on the same port (115200):

```console
uart:~$ hub status
uart:~$ hub pd                     # the contract, and what the charger offers
uart:~$ wifi cred add -s <ssid> -k 1 -p <password>
uart:~$ wifi cred auto_connect
uart:~$ hub id lab1                # then http://rack-lab1.local/
```

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

- The eFuse of [bring-up.md › One irreversible step](../bring-up.md#one-irreversible-step), once
  everything above passed.
- Then the measurements the reviews left for the first hub (several chargers, the VHV pin at
  plug-in, a shorted row): [assembly.md › Bring-up](../assembly.md#7-bring-up).
