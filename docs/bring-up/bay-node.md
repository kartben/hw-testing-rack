# Bring-up: bay node v1.0

One per bay: it runs from the row's 20 V, carries the ESP32-S3, the USB path to the DUT, the
DATA lead's supply and the camera's.  Test pad names are the ones printed on the bottom face.
Back to [bring-up.md](../bring-up.md).

## 1. Look

- The pin-1 marks of U1 (the 5 V buck), U5 and U6 (the USB muxes), U7 (the OR gate), U9 (the
  DATA lead's eFuse), U10 (the INA226 current monitor), U11 (the CAN transceiver) and the four
  USBLC6 (U4, U8, U12, U13).  U2 (the 3.3 V regulator) and Q1 (the reverse-polarity FET) only fit one way.
- C1, the tall 100 µF can: its black mark is the minus side.  D2, the big diode beside it: its
  bar is on the VIN side.
- R35 is not fitted: its footprint stays empty.
- The SERVICE switch (SW3) sits on its two pegs.

## 2. No power

| Ohmmeter between GND and | Expect |
|---|---|
| VIN, 5V, 3V3, DATA VIN, CAM 5V | no short: the reading climbs, or stays above ≈ 100 Ω |

## 3. First power

The node runs from its row socket, never from the USB port.  Bench supply at 20 V, limit 0.2 A,
on J1 (ROW IN): pin 1 is +, pins 2 and 5 are GND.  Raise the voltage from 0.

| Check | Expect |
|---|---|
| Under ≈ 13.5 V | 5V at 0 V: the buck waits for the row to be up |
| At 20 V: VIN | the supply's voltage, a few tens of millivolts lower |
| 5V | 5.24 V (5.1–5.4 V) |
| 3V3 | 3.3 V (3.2–3.4 V) |
| CAM 5V | as 5V (it comes through a resettable fuse) |
| DATA VIN | 0 V: the DATA lead's eFuse is off without firmware |
| The supply's current | well under the 0.2 A limit: write it down |

Optional: the supply reversed, limit 50 mA.  No current flows and VIN stays at 0 V.

## 4. Flash and ask

Node powered from J1.  Slide SERVICE on, laptop on the front PC port (J3).

```bash
west flash -d build-bay            # MCUboot, then the application
```

SERVICE off.  The node joins the Wi-Fi of `wifi.conf` and answers at `http://bay<MAC>.local/`
and over telnet.  Without Wi-Fi: a 3.3 V USB-UART on the TX, RX and GND pads, 115200.

| Check | Expect |
|---|---|
| `bay status` | an IP address, power off, 0 mA, no fault |
| SERVICE on | the status LED turns yellow; off again, it leaves yellow |
| RESET (SW1) | the node restarts and comes back on the network |
| `bay power on`, nothing on J7 | DATA VIN rises to VIN for under a second, then the node switches it off and says no board answered |
| J5 pins 3 and 4 joined with a wire, `bay aux send hello`, `bay aux` | the receive counter grows by what was sent |
| A laptop on the PC port, SERVICE off | `bay status` shows the classic data path |

## 5. On the hub

A row lead from one of the hub's rows to J1.  The node starts when the hub turns the row on,
takes its position from the hub and shows it in `bay status`.  The bus itself, with two nodes:
[rack.md](rack.md).

Then the boards that hang off the node: [camera-pod.md](camera-pod.md),
[data-port-x6.md](data-port-x6.md), [data-port-x4.md](data-port-x4.md).

## 6. Last

- The eFuse of [bring-up.md › One irreversible step](../bring-up.md#one-irreversible-step), once
  everything above passed.
- Then the measurements the reviews left for the first node (the fuse's margin, the 3.3 V load
  step, the I²C rise time): [assembly.md › Bring-up](../assembly.md#7-bring-up).
