# The node and the hub on an M5Stack CoreS3

The bay node and the power hub firmwares on an M5Stack CoreS3
(`m5stack_cores3/esp32s3/procpu`).  This is a bench stand-in until the boards arrive.  Same applications,
with one overlay each:
[`firmware/bay-node/boards/m5stack_cores3_procpu.overlay`](../firmware/bay-node/boards/m5stack_cores3_procpu.overlay)
and [`firmware/power-hub/boards/m5stack_cores3_procpu.overlay`](../firmware/power-hub/boards/m5stack_cores3_procpu.overlay).
Both are in the CI matrix (`cores3_node`, `cores3_hub`).

The CoreS3: ESP32-S3, 16 MB flash, 8 MB PSRAM (quad: GPIO35–37 are the display's SPI), a USB-C on the
S3's own PHY, an internal I²C bus (AXP2101, AW9523B, touch, sensors), Grove A (G1/G2, I²C), B (G8/G9)
and C (G17/G18, UART), and an internal battery.

## What each application can test

| | Bay node on a CoreS3 | Power hub on a CoreS3 |
|---|---|---|
| **Testable** | Wi-Fi, the web page, the shell (telnet), access control; **the USB host and USB/IP** to a real DUT on the CoreS3's USB-C (the DWC2 and USB/IP patches); `bay power on\|off` switches the DUT's VBUS (the CoreS3's boost, AW9523B `USB_OTG_EN`); the AUX console on Grove C; RESET/BOOT on Grove B; updates over Wi-Fi (MCUboot).  With a self-powered USB hub on the USB-C: several DUTs, the busid by port (`1-1.n`), the hidden hub, re-plugs, BOOTSEL round trips (the spike's step 8) | the CH224A driver and the PD policy with a real charger: 9 V at plug-in, then 28 V EPR (or 20 V), the fall-back, PG events, VBUS on the ADC; row A as logic levels (stagger, the FLT blanking, the pad hold across a reset); the web page, `/metrics`, the shell, updates over Wi-Fi |
| **Missing** | the muxes and classic mode, PC detect, the TPS2553 (a grounded G10 fakes a fault), the camera (the CoreS3's is a GC0308 on DVP, not an Arducam Mega), the status LED, the rack bus (no transceiver), V/I without an INA226 | the eFuses and IMON (so shedding by current and the adaptive policy), rows B–D, the CTL LED unless you add one; CAN without a transceiver |
| **Hardware** | a USB-C OTG cable or adapter and a DUT; for several DUTs a self-powered USB hub; jumpers for UART, RESET and BOOT; optional: an INA226 breakout in the DUT's VBUS | a CH224A or CH224Q board that breaks out CFG1–3 and PG; a USB PD charger (EPR 140 W for 28 V, any 20 V PD charger otherwise) and its cable; 100k + 10k for VBUS_SENSE; an LED + 330 Ω for row A; optional: an SN65HVD230 CAN module |

## Building and flashing

From a west workspace made from `firmware/west.yml` (firmware/README.md, Building):

```
west build --sysbuild -b m5stack_cores3/esp32s3/procpu -d build-node hw-testing-rack/firmware/bay-node
west build --sysbuild -b m5stack_cores3/esp32s3/procpu -d build-hub  hw-testing-rack/firmware/power-hub
```

Wi-Fi: `-- -DEXTRA_CONF_FILE=wifi.conf` with your `wifi.conf` (`wifi.conf.example`), or later
`wifi cred add -s <ssid> -k 1 -p <password>` in the shell.

Flash over the CoreS3's USB-C, the first time with `--erase` (MCUboot and the application):

```
west flash -d build-node --erase --esp-device COM5                       # Windows: the port in Device Manager
west flash -d build-node --erase --esp-device /dev/cu.usbmodem14101      # macOS: ls /dev/cu.usbmodem*
```

The hub keeps its USB-C as its console (USB-Serial-JTAG): `west flash` and a serial terminal work as on
any board.  **The node does not:** at boot its USB host takes the S3's only PHY and the PC loses the
port.  To reach it again:
- **Download mode:** hold the CoreS3's RESET button 2–3 s, until its green LED lights, then
  `west flash`.  Then press RESET.
- **SERVICE:** G7 (M-Bus) to 3.3 V gives the PHY back to the USB-Serial-JTAG (console, `west flash`)
  without reflashing; G7 back to GND and the USB host returns.
- **Over Wi-Fi:** `bayctl update build-node/bay-node/zephyr/zephyr.signed.bin <bay>`.
- **The shell over telnet:** `telnet bay-<id>.local`.  `bay access claim` is refused there; use
  SERVICE's local shell for it.

With a DUT on its USB-C the CoreS3 runs from its battery: charge it first (an hour on a PC), or feed
5 V on the M-Bus.

## Bay node: wiring

| CoreS3 | To |
|---|---|
| USB-C | the DUT, through a USB-C OTG cable or adapter (or a self-powered USB hub, then the DUTs) |
| Grove C: G17 TX, G18 RX, GND | the DUT's UART (3.3 V): AUX console |
| Grove B: G8, G9 | the DUT's RESET (EN) and BOOT (IO0): open drain, active low |
| Grove A: G2 SDA, G1 SCL, 5V, GND | optional: an INA226 breakout at 0x40 with its shunt in the DUT's VBUS |
| M-Bus G7 | SERVICE: GND or open = normal, 3.3 V = the USB-C back to the PC |
| M-Bus G10 | DUT_FLT_N: open = no fault, to GND = a fake current limit |

## Bay node: bench plan

| # | Do | Expect | Pass |
|---|---|---|---|
| 1 | Flash (`--erase`), unplug from the PC, plug it back | on the USB-Serial-JTAG, before the host starts: the boot log, `bay id`, Wi-Fi | the log reaches "web page and API on http port 80" |
| 2 | `wifi cred add …` if not built in; reboot | it joins the Wi-Fi, mDNS `bay-<id>.local` | `curl http://bay-<id>.local/api/status` answers |
| 3 | Open `http://bay-<id>.local/` | the node's page: DUT, USB, AUX, access | the page loads; `path` is `usbip` |
| 4 | Unplug the PC, plug a DUT (a Pico 2 or an ESP32-C3 on the OTG cable) | the DUT lights (VBUS from the boost) | `/api/status`: `usb.devices` 1 |
| 5 | On a Linux host: `python tools/bayctl.py attach <bay> --show` (lab.yaml: `host: bay-<id>.local`) | the DUT's `/dev/serial/by-id/…` | `usbip port` lists busid `1-1`; the DUT's console works |
| 6 | `bayctl power <bay> cycle` | the DUT goes dark 1 s and comes back; the session ends and `attach --follow` re-attaches | the same busid; no crash in `telnet` → `kernel stacks` |
| 7 | Flash the DUT over USB/IP (`west flash` or `picotool load -x` on the host) | it flashes at full speed | a flash of 1 MB in under 30 s, no error |
| 8 | Grove C to the DUT's UART; the page's console | the DUT's UART output; typing reaches it | `bayctl pty` or `esptool --port rfc2217://bay-<id>.local:4001 chip-id` works |
| 9 | Grove B to an ESP32 DUT's EN/IO0; `bayctl reset`, `bayctl boot` | it restarts, then waits in its ROM loader | its log shows `boot:0x…(DOWNLOAD…)` after `boot` |
| 10 | G10 to GND for 2 s | `DUT VBUS fault` in the log; after 1 s VBUS off and latched | `/api/status` `dut.latched` true; `bayctl power <bay> on` clears it |
| 11 | A self-powered USB hub on the USB-C, 2–4 DUTs behind it | `usbip list -r bay-<id>.local`: one line per DUT, `1-1.<hub port>`, no hub line | busids follow the hub ports and stay after a re-plug |
| 12 | The spike's step 8 with those DUTs: 4 consoles open, a command each, a re-plug, 20 `picotool reboot -u -f` round trips of a Pico | every console answers at once; the Pico comes back each time | no "No channel data slot", no stall (`firmware/spikes/usb-hub/README.md`) |
| 13 | `bayctl update build-node/bay-node/zephyr/zephyr.signed.bin <bay>` | the node restarts on trial and confirms itself | the page's firmware card shows the new version, confirmed |
| 14 | G7 to 3.3 V (SERVICE) | the PC sees the USB-Serial-JTAG again; G7 back to GND: the host returns | `west flash` works in SERVICE without the RESET button |

## Power hub: wiring

| CoreS3 | To |
|---|---|
| USB-C | the PC (power, console, flashing) |
| Grove A: G2 SDA, G1 SCL, GND | the CH224A board's CFG3 (SDA), CFG2 (SCL) and GND; CFG1 to GND through 6.8 kΩ (I²C on, 9 V at plug-in) |
| Grove B: G8 | the CH224A's PG (open drain; check the board does not pull it up to VBUS) |
| Grove B: G9 | the CH224A board's VBUS through 100 kΩ, with 10 kΩ from G9 to GND (2.5 V at 28 V).  **Never VBUS straight** |
| M-Bus G5 | ROW_EN_A: an LED + 330 Ω to GND shows the row |
| M-Bus G6 | FLT_A: open = no fault, to GND = an eFuse fault |
| M-Bus G43 | CTL LED: an LED + 330 Ω to GND, if you want it |
| Grove C: G17, G18 | optional: TX and RX of an SN65HVD230 CAN module |
| PD charger | into the CH224A board's USB-C |

## Power hub: bench plan

| # | Do | Expect | Pass |
|---|---|---|---|
| 1 | Flash (`--erase`), open the console (USB-Serial-JTAG, 115200) | the boot log, `hub` shell | `hub pd`: state "no VBUS" |
| 2 | Wi-Fi as for the node; open `http://rack.local/` | the hub's page | `/api/status` answers |
| 3 | Plug the charger into the CH224A board | "VBUS 9.0 V: PD sink up", then "contract: 9 V …, too low for the rows" | `hub pd`: status 0x08 (PD), PG low, VBUS ≈ 9 V on the ADC (± 5 %) |
| 4 | Wait | the hub asks for 28 V (EPR charger) or 20 V: "contract: 28 V / … EPR" | VBUS ≈ 28 V (or 20 V); `asked` matches; the page shows the PDOs |
| 5 | After 0.5 s | "row A on" | G5 high (its LED on); rows B–D stay off |
| 6 | `hub pd 20v`, then `hub pd epr` | the contract steps 28 → 20 → 28 V | each step reaches VBUS within 3 s; row A stays on (VBUS ≥ 15 V) |
| 7 | A charger without EPR, or a 3 A cable | 28 V asked, VBUS stays at 20 V: "asking for 20 V" | the fall-back within `CONFIG_HUB_PD_REQUEST_MS` (3 s); `epr_refused` in `/api/status` |
| 8 | Unplug the charger | "contract lost (PG high): rows off …", then "VBUS gone" | G5 low within 20 ms of PG high |
| 9 | Plug it back | the start again, row A back after the contract settles | as 3–5 |
| 10 | G6 to GND for 1 s with row A on | "row A: eFuse fault" | `/api/status` row A `faults` 1; with row A off (`hub row A off`), G6 to GND logs nothing |
| 11 | `hub row A cycle` | G5 off 2 s, then on | the LED follows |
| 12 | Row A on, press the CoreS3's RESET | the controller restarts, the row stays on (pad hold) | G5 stays high through the reset; "rows kept on across the controller reset" |
| 13 | `curl http://rack.local/metrics` | `hub_contract_volts`, `hub_vbus_volts`, `hub_row_on{row="A"}` | the values match `hub pd` |
| 14 | `bayctl update build-hub/power-hub/zephyr/zephyr.signed.bin --hub` | the hub restarts on trial, confirms | the new version, confirmed |

Not on a CoreS3: IMON and shedding by current (no eFuses), the adaptive 20 → 28 V switch (it needs
IMON), CAN without a transceiver (with an SN65HVD230 module the hub can talk to a node that has one too).
