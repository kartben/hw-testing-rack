# Bench stand-ins: the node and the hub on a CoreS3 or a XIAO ESP32-S3

The bay node and the power hub firmwares on two off-the-shelf ESP32-S3 boards, until the boards
arrive: an **M5Stack CoreS3** (`m5stack_cores3/esp32s3/procpu`) and a **Seeed XIAO ESP32-S3**
(`xiao_esp32s3/esp32s3/procpu`, the Sense too).  Same applications, with one overlay and one conf per
board in each application's `boards/`.  All four builds are in the CI matrix (`cores3_node`,
`cores3_hub`, `xiao_node`, `xiao_hub`).

## Which board for which test

| Test | XIAO ESP32-S3 | CoreS3 |
|---|---|---|
| The node's PSRAM configuration (8 MB **octal**, as the WROOM-1-N8R8) | **yes** (ESP32-S3R8) | no: quad |
| USB host and USB/IP to a real DUT on the board's USB-C | yes | yes |
| DUT power switched by `bay power` | only with a LiPo and an external switch: the DUT's 5 V is the XIAO's 5V pin | **yes** (its boost, AW9523B `USB_OTG_EN`) |
| Several DUTs behind a self-powered USB hub (busid `1-1.n`, re-plugs, BOOTSEL trips) | yes | yes |
| AUX console, RESET/BOOT | yes (D6/D7, D0/D1) | yes (Grove C, Grove B) |
| INA226, a DATA ×4 on I²C | yes (D4/D5) | yes (Grove A) |
| Reflash with the node running | **BOOT + RESET buttons** | RESET held 2–3 s |
| Hub: CH224A, the PD policy, PG, VBUS_SENSE, row A | yes | yes |
| Hub: IMON, so shedding and the adaptive 20/28 V switch | **yes** (a potentiometer on D10) | no |
| Hub: CAN | with a transceiver module | with a transceiver module |
| Self-contained (battery, plugs, no soldering) | no: header pins | **yes** (Grove cables) |

The XIAO is closer to the node (the chip, the PSRAM, the buttons); the CoreS3 switches the DUT's
power and needs no soldering.  Neither tests the camera (the DevKitC with an Arducam Mega on jumpers
does), the muxes or the eFuses.

## Building and flashing

From a west workspace made from `firmware/west.yml` (firmware/README.md, Building), `<board>` being
`m5stack_cores3/esp32s3/procpu` or `xiao_esp32s3/esp32s3/procpu`:

```
west build --sysbuild -b <board> -d build-node hw-testing-rack/firmware/bay-node
west build --sysbuild -b <board> -d build-hub  hw-testing-rack/firmware/power-hub
```

Wi-Fi: `-- -DEXTRA_CONF_FILE=wifi.conf` with your `wifi.conf` (`wifi.conf.example`), or later
`wifi cred add -s <ssid> -k 1 -p <password>` in the shell.

Flash over the board's USB-C, the first time with `--erase` (MCUboot and the application):

```
west flash -d build-node --erase --esp-device COM5                       # Windows: the port in Device Manager
west flash -d build-node --erase --esp-device /dev/cu.usbmodem14101      # macOS: ls /dev/cu.usbmodem*
```

The hub keeps its USB-C as its console (USB-Serial-JTAG): `west flash` and a serial terminal work as on
any board.  **The node does not:** at boot its USB host takes the S3's only PHY and the PC loses the
port; each board's section says how to get it back.

## M5Stack CoreS3

ESP32-S3, 16 MB flash, 8 MB PSRAM (quad: GPIO35–37 are the display's SPI), a USB-C on the
S3's own PHY, an internal I²C bus (AXP2101, AW9523B, touch, sensors), Grove A (G1/G2, I²C), B (G8/G9)
and C (G17/G18, UART), and an internal battery.

### What it can test

| | Bay node on a CoreS3 | Power hub on a CoreS3 |
|---|---|---|
| **Testable** | Wi-Fi, the web page, the shell (telnet), access control; **the USB host and USB/IP** to a real DUT on the CoreS3's USB-C (the DWC2 and USB/IP patches); `bay power on\|off` switches the DUT's VBUS (the CoreS3's boost, AW9523B `USB_OTG_EN`); the AUX console on Grove C; RESET/BOOT on Grove B; updates over Wi-Fi (MCUboot).  With a self-powered USB hub on the USB-C: several DUTs, the busid by port (`1-1.n`), the hidden hub, re-plugs, BOOTSEL round trips (the spike's step 8) | the CH224A driver and the PD policy with a real charger: 9 V at plug-in, then 28 V EPR (or 20 V), the fall-back, PG events, VBUS on the ADC; row A as logic levels (stagger, the FLT blanking, the pad hold across a reset); the web page, `/metrics`, the shell, updates over Wi-Fi |
| **Missing** | the muxes and classic mode, PC detect, the TPS2553 (a grounded G10 fakes a fault), the camera (the CoreS3's is a GC0308 on DVP, not an Arducam Mega), the status LED, the rack bus (no transceiver), V/I without an INA226 | the eFuses and IMON (so shedding by current and the adaptive policy), rows B–D, the CTL LED unless you add one; CAN without a transceiver |
| **Hardware** | a USB-C OTG cable or adapter and a DUT; for several DUTs a self-powered USB hub; jumpers for UART, RESET and BOOT; optional: an INA226 breakout in the DUT's VBUS | a CH224A or CH224Q board that breaks out CFG1–3 and PG; a USB PD charger (EPR 140 W for 28 V, any 20 V PD charger otherwise) and its cable; 100k + 10k for VBUS_SENSE; an LED + 330 Ω for row A; optional: an SN65HVD230 CAN module |

### Flashing the node again

- **Download mode:** hold the CoreS3's RESET button 2–3 s, until its green LED lights, then
  `west flash`.  Then press RESET.
- **SERVICE:** G7 (M-Bus) to 3.3 V gives the PHY back to the USB-Serial-JTAG (console, `west flash`)
  without reflashing; G7 back to GND and the USB host returns.
- **Over Wi-Fi:** `bayctl update build-node/bay-node/zephyr/zephyr.signed.bin <bay>`.
- **The shell over telnet:** `telnet bay-<id>.local`.  `bay access claim` is refused there; use
  SERVICE's local shell for it.

With a DUT on its USB-C the CoreS3 runs from its battery: charge it first (an hour on a PC), or feed
5 V on the M-Bus.

### Bay node: wiring

| CoreS3 | To |
|---|---|
| USB-C | the DUT, through a USB-C OTG cable or adapter (or a self-powered USB hub, then the DUTs) |
| Grove C: G17 TX, G18 RX, GND | the DUT's UART (3.3 V): AUX console |
| Grove B: G8, G9 | the DUT's RESET (EN) and BOOT (IO0): open drain, active low |
| Grove A: G2 SDA, G1 SCL, 5V, GND | optional: an INA226 breakout at 0x40 with its shunt in the DUT's VBUS |
| M-Bus G7 | SERVICE: GND or open = normal, 3.3 V = the USB-C back to the PC |
| M-Bus G10 | DUT_FLT_N: open = no fault, to GND = a fake current limit |

### Bay node: bench plan

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

### Power hub: wiring

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

### Power hub: bench plan

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

## Seeed XIAO ESP32-S3

ESP32-S3R8 (8 MB of octal PSRAM in the package), 8 MB flash, a USB-C on the S3's own PHY, BOOT and
RESET buttons, a user LED (G21) and 11 pins.  The Sense variant adds a camera, a microphone and an SD
slot on D8–D10, pulled up on its board: use the same target and leave the slot empty (the node reads
SERVICE and PC_DET active low, so those pull-ups read "off").

**Clip its antenna on.**  The XIAO has no PCB antenna, only a u.FL connector (the antenna comes loose
in the box).  Without it, `wifi scan` shows the access point around −90 dBm and every connection
fails with "Connection timeout".

**Its USB-C in host mode.**  On Seeed's schematic the USB-C's VBUS is the 5V pin, with nothing between
(the diode sits between VBUS and the regulator) and 5.1 kΩ Rd on CC: the XIAO never sources VBUS.  So
the DUT's 5 V is whatever feeds the 5V pin: a bench 5 V supply or a USB breakout, which powers the XIAO
too.  The DUT's power is always on; `bay power` drives D2 (DUT_EN), which can switch a high-side switch
in that feed only if the XIAO runs from a LiPo on its BAT pads.  **Never feed the 5V pin while a PC is
on the USB-C.**

### Pin map

| Pin | Node | Hub |
|---|---|---|
| D0 G1 | RESET → DUT EN/RST (open drain) | VBUS_SENSE ← VBUS through 100k / 10k (ADC1 ch 0) |
| D1 G2 | BOOT → DUT IO0 (open drain) | ROW_EN_A (an LED + 330 Ω) |
| D2 G3 | DUT_EN (an external switch, see above) | FLT_A (pulled up; to GND = a fault) |
| D3 G4 | DUT_FLT_N (pulled up; to GND = a fault) | PD_INT ← the CH224A's PG |
| D4 G5 | SDA: INA226, DATA ×4 | SDA → the CH224A's CFG3 |
| D5 G6 | SCL | SCL → its CFG2 |
| D6 G43 | AUX TX → DUT RX | CAN TX (optional transceiver) |
| D7 G44 | AUX RX ← DUT TX | CAN RX |
| D8 G7 | SERVICE (pulled up; GND = the USB-C back to the PC) | POS_A |
| D9 G8 | PC_DET (pulled up; GND = a PC on the front port) | I2C_PU (nothing on it) |
| D10 G9 | MUX_FORCE_PC (unused) | IMON_A: a 10k potentiometer, 3V3 to GND (1.404 V/A) |
| LED G21 | the board's | CTL |

### Flashing the node again

- **Download mode:** hold BOOT, press and release RESET, release BOOT; then `west flash`, then RESET.
- **SERVICE:** D8 to GND gives the PHY back to the USB-Serial-JTAG without reflashing.
- **Over Wi-Fi:** `bayctl update build-node/bay-node/zephyr/zephyr.signed.bin <bay>`.
- **The shell over telnet:** `telnet bay-<id>.local` (`bay access claim` only on SERVICE's local shell).

Unplug the 5 V feed before plugging the PC.

### Bay node: bench plan

| # | Do | Expect | Pass |
|---|---|---|---|
| 1 | Flash (`--erase`) from the PC, keep it on the PC | the boot log on the USB-Serial-JTAG, then the host takes the port | the log reaches "web page and API on http port 80"; PSRAM 8 MB octal in the log |
| 2 | Wi-Fi as above; `http://bay-<id>.local/` | the node's page | `/api/status` answers; `path` `usbip` |
| 3 | Unplug the PC.  A 5 V supply on the 5V pin and GND, a DUT on the USB-C through an OTG adapter | the XIAO and the DUT power up together | `/api/status`: `usb.devices` 1 |
| 4 | `bayctl attach <bay> --show` on a Linux host | the DUT's `/dev/serial/by-id/…` | busid `1-1`; its console works |
| 5 | Unplug and replug the DUT | the session ends; `attach --follow` re-attaches | same busid; `kernel stacks` over telnet: no stack near full |
| 6 | Flash the DUT over USB/IP | it flashes | 1 MB in under 30 s, no error |
| 7 | D6/D7 to the DUT's UART; the page's console | the DUT's output; typing reaches it | RFC 2217: `esptool --port rfc2217://bay-<id>.local:4001 chip-id` |
| 8 | D0/D1 to an ESP32 DUT's EN/IO0; `bayctl reset`, `bayctl boot` | restart; then its ROM loader | `boot:0x…(DOWNLOAD…)` in its log |
| 9 | D3 to GND for 2 s | a VBUS fault, latched after 1 s | `dut.latched` true; `bayctl power <bay> on` clears it |
| 10 | A self-powered USB hub on the USB-C, 2–4 DUTs | one `usbip list` line per DUT, `1-1.<n>`, no hub line | busids follow the ports through re-plugs |
| 11 | The spike's step 8: 4 consoles, re-plugs, 20 BOOTSEL trips of a Pico | everything answers | no "No channel data slot", no stall |
| 12 | Optional: an INA226 breakout on D4/D5 with its shunt in the 5 V feed | V and I on the page | they match a USB meter within 5 % |
| 13 | `bayctl update …` | test boot, confirmed | the new version, confirmed |
| 14 | BOOT + RESET, `west flash` from the PC | the ROM loader takes the image | it boots the new image |

### Six USB/IP sessions: what the XIAO measured (2026-10-21)

The node exports up to six devices at once on boards with PSRAM (a DATA ×4: its four ports, the
logic variant's co-processor, a spare; `firmware/bay-node/Kconfig`).  The DRAM for six sessions
comes from the Wi-Fi adapter's heap, moved to PSRAM (`CONFIG_ESP_WIFI_HEAP_SPIRAM`).  The USB/IP pool
and the UHC buffers stay in internal RAM: the DWC2 moves them by DMA, which does not reach PSRAM.

| | internal RAM (dram0) |
|---|---|
| bay_node, before (one session) | 99.82 %, 672 B free |
| bay_node, six sessions, Wi-Fi heap in PSRAM | 99.30 %, 2648 B free |
| esp32s3_devkitc | 99.41 % |
| xiao_esp32s3 (bench conf) | 93.3 % |

On the XIAO, the page open (two web consoles), no DUT:

- system heap 33.6 KB: 8.9 KB free, 25.3 KB the most used;
- PSRAM heap: the Wi-Fi adapter's 67 KB, 70 KB at most;
- stacks: none past 60 % (telnet 52 %, wifi 53 %, the six USB/IP device threads 24 %).

Wi-Fi throughput, the Wi-Fi heap in PSRAM against the same build with it in internal RAM (four
sessions, to fit), back to back on the same network:

| Wi-Fi heap | 10 × 88 KB one after the other | 4 × 88 KB at once | 1 MB update upload |
|---|---|---|---|
| PSRAM | 53 KB/s, then 61 KB/s | 4.5–6.5 s | 23–28 s |
| internal | 40 KB/s | 6.8–7.2 s | 24 s |

No loss: the differences are the Wi-Fi's own.  Thirteen bursts of eight parallel 88 KB downloads
(more than the six HTTP slots) left the node up.

The 15-minute soak with DUTs behind a powered hub (all attached, consoles open, one DUT
reflashed, the page reloaded in a loop) did not complete.  The bench found three faults, none of
them this layout's; the last one was reproduced with the Wi-Fi heap in internal RAM:

- a USB 3 hub (Genesys USB 3.1 with its card reader) next to the XIAO's antenna: the node lost
  its Wi-Fi and its USB host saw transaction errors; moved 30–50 cm away, both stopped;
- an NXP MCU-Link on the hub: Zephyr's hub class resets its port again and again ("Port 2 not
  enabled after reset"), the node's network collapses, and once the USB host's thread panicked;
- an FT232 (an M5StickC): `esptool read_flash` over USB/IP fails at every baud rate, the data
  corrupted ("Invalid SLIP escape").

The last two are being looked at in the USB host stack (Zephyr's `usbh_hub`, `uhc_dwc2`, the
USB/IP service).  To do on the bench once they are fixed: the soak above with a Pico or an ESP32
with native USB.

### Power hub: bench plan

Wired as in the pin map; the PD charger into the CH224A board's USB-C, the XIAO on the PC.

| # | Do | Expect | Pass |
|---|---|---|---|
| 1 | Flash (`--erase`), open the console | the boot log, `hub` shell; the XIAO's LED (CTL) blinks slowly | `hub pd`: "no VBUS" |
| 2 | Plug the charger | "VBUS 9.0 V: PD sink up", then the 9 V contract | `hub pd`: status 0x08, PG low, VBUS ≈ 9 V (± 5 %) |
| 3 | Wait | 28 V EPR (or 20 V) asked and reached | VBUS on D0 ≈ 28 V (or 20 V) |
| 4 | After 0.5 s | "row A on" | D1 high; the CTL LED steady |
| 5 | `hub pd 20v`, `hub pd epr` | 28 → 20 → 28 V | each step within 3 s, row A stays on |
| 6 | A charger without EPR | the fall-back to 20 V | within 3 s, `epr_refused` true |
| 7 | Unplug the charger | rows off on PG high, then "VBUS gone" | D1 low within 20 ms |
| 8 | D2 to GND with row A on | "row A: eFuse fault" | counted; nothing when row A is off |
| 9 | The potentiometer up (D10) | row A's current on the page and in `/metrics` | `hub_row_amps{row="A"}` follows the knob (1.404 V/A) |
| 10 | A 100 W charger without EPR (Anker Nano 100 W: 20 V × 5 A) and a 5 A cable; `hub budget` | the budget from the contract | "4.50 A of 5.00 A contract less 10 %" (90 W); through a 3 A cable 2.70 A (54 W) |
| 11 | `hub budget cap 30` (1.5 A at 20 V, a 1.35 A budget); the knob between 1.35 and 1.5 A | "row A shed: … budget" after 1 s, D1 low | back ("row A back") 10 s after the knob goes down |
| 12 | The knob past 1.5 A | "row A shed: … contract" | within 0.5 s, not 1 s |
| 13 | Within a minute of it coming back, the knob up again, then down | shed again | it comes back after 20 s, not 10 (`hub budget`: sheds counted) |
| 14 | `/metrics`; then `hub budget cap off` | `hub_budget_amps`, `hub_rows_amps`, `hub_row_shed{row="A"}`, `hub_row_sheds_total` | the cap gone, saved across a reset like the margin (`hub budget margin`) |
| 15 | Build with `-DCONFIG_HUB_PD_ADAPTIVE=y`; charger EPR | 20 V first; the knob past 1.2 A: "asking for 28 V EPR" | VBUS 20 → 28 V without row A going off |
| 16 | Row A on, press RESET | the row stays on (pad hold) | D1 high through the reset |
| 17 | `bayctl update … --hub` | test boot, confirmed | the new version, confirmed |
