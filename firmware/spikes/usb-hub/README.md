# USB hub spike: up to 4 DUTs on one node

A bench test of the riskiest part of "one node, four boards" (density epic,
decision 3): an ESP32-S3 running Zephyr's USB host stack with its hub class,
exporting several devices at once over USB/IP.  It is not the bay node: a
DevKitC, a hub off the shelf, a few boards, and a shell to look at what the
stack sees.  The design it feeds is [docs/multi-dut-node.md](../../../docs/multi-dut-node.md).

Zephyr as pinned in [`firmware/west.yml`](../../west.yml) (3f7ae83); its USB
host files (`usbh_hub.c`, `usbip.c`, `usbh_device.c`, `uhc_dwc2.c`) are the same
as on main at a915b2f (2026-10-16).  `usbip.c` gets the rack's patch
(`west patch apply`, [`zephyr/patches.yml`](../../../zephyr/patches.yml)): the
three USB/IP rows below marked *patched*.

## What the code says, before the bench

| Question | Zephyr today | On an ESP32-S3 |
|---|---|---|
| Enumeration behind a hub | `CONFIG_USBH_HUB_CLASS` (NXP, 2025-26): ports powered at start, connect / disconnect / reset handled, devices get `hub`, `hub_port`, `level` | The S3's OTG is full speed only: the hub runs at full speed and full-speed DUTs need no split transactions (DWC2's split support is WIP, #120876, and only matters for a high-speed root such as the P4). **Low-speed DUTs behind the hub will not work**: DWC2 never sets `HCCHAR.LSPDDEV` (`TODO: Support Hubs`) |
| Several devices over USB/IP | `CONFIG_USBIP_DEVICES_COUNT` sessions, one thread and a 2 KB stack each; transfers queue when the 8 host channels are busy | 12 Mbit/s shared by all DUTs; RAM: the bay node has 12 KB of DRAM left |
| busid | Upstream: `1-<address>`, the address the host gave at enumeration (lowest free one), so two DUTs that reset together can swap.  *Patched*: by port, `1-1.<hub port>` | **To check**: the same busid after a reset, for each port |
| The hub in `usbip list` | Upstream: every device, the hub too (class 09).  *Patched*: only devices a USB/IP context is bound to, never a hub | **To check**: no hub in the list |
| A DUT that resets while attached | Upstream: USB/IP is not told, its session keeps a pointer to the freed device.  *Patched*: the session ends, its transfers are cancelled (native_sim: `firmware/common/tests/usbip`) | **To watch**: the client sees a detach; `usbip attach` again works |
| Per-port power | `SetPortFeature` / `ClearPortFeature(PORT_POWER)` exist (`usbh_req_set/clear_hcfs_port_power`), used once at start to power all ports; not public API | Works only on hubs that really switch each port (most cheap hubs do not) |
| Your DWC2 fixes | #120848 (bulk toggle from the controller), #120961 (rewind bulk transfers, seen behind a GL850G), #121688 (toggles on SET_CONFIGURATION / ClearFeature(HALT)): open.  *Patched*: carried in `zephyr/patches.yml` (`uhc-dwc2-channels.patch`) | Expected to matter behind a hub (re-enumerating DUTs, bulk retries) |
| Host channels | Upstream: a pending IN transfer keeps one of the 8 channels, a bulk IN while the device NAKs, an interrupt IN between polls; control and OUT transfers queue behind them.  The hub's status IN and two per open CDC console: 9 with 4 consoles open.  The endpoint state (32 slots) is freed only by a root port reset.  *Patched* (same file): an interrupt IN gives its channel back between polls, a NAKing bulk IN gives it to waiting transfers, the endpoint state is kept by address and freed when a device takes the address over | **To check**: step 8, untested so far |

## The spike

`src/main.c`: Wi-Fi (the stored credentials, `usbspike-<mac>.local`), the
USB/IP service with 4 sessions, the hub class, and a shell command on the
"UART" connector:

| Command | |
|---|---|
| `spike devs` | every device: address, USB/IP busid, root or hub port, speed, VID:PID |
| `spike hub` | the hub: VID:PID, ports, power switching (ganged, **per port**, none), over-current |
| `spike port <n>` | port n's status (power, connected, enabled, over-current) |
| `spike port <n> off` / `on` / `cycle [ms]` | ClearPortFeature / SetPortFeature(PORT_POWER) |

```console
west build -b esp32s3_devkitc/esp32s3/procpu hw-testing-rack/firmware/spikes/usb-hub
west flash
```

Then on its console (the "UART" connector, 115200), once: `wifi cred add -s
<your network> -k 1 -p <its password>`, `kernel reboot cold`.  The console
prints `network up: usbip list -r <address>`.

## Bench

**To buy or find**

- An ESP32-S3-DevKitC-1 (N8R8, as the bay node; any S3 devkit with the OTG
  pins out works).
- A self-powered hub that really switches each port (uhubctl's list):
  - D-Link DUB-H4, **rev D or E only** (black; the label says): USB 2.0,
    `05e3:0608`, the Genesys GL850G family.  Cheap, often second-hand.
  - UUGear MEGA4: USB 3 (its USB 2 half runs here), VL817, `2109:0817`, made
    for uhubctl; it needs its own 5 V supply (USB-C).
  Check before buying further: some hubs advertise per-port switching and cut
  only the data lines (Raspberry Pi 5's), or switch the ports together.
- A USB-A female breakout (any 4-pin board): the DevKitC's "USB" connector
  does not give VBUS, and a hub only connects when it sees VBUS on its
  upstream port.  Wire VBUS to the DevKitC's 5V pin, D- to IO19, D+ to IO20,
  GND to GND, and plug the hub into it.
- 2 to 4 full-speed DUTs: Seeed XIAO ESP32-C3 or S3, M5Stack AtomS3 (USB
  Serial/JTAG), Raspberry Pi Pico (BOOTSEL mass storage, then CDC).  No
  keyboards or other low-speed devices.
- A Linux PC on the same network: `usbip` (`linux-tools-generic` on Ubuntu),
  `sudo modprobe vhci-hcd`, esptool, picotool.
- A USB voltmeter or a multimeter for VBUS on the hub's ports.

**What to measure** (keep the node's console log for each)

1. **Enumeration.**  Hub with nothing, then 1, 2, 4 DUTs plugged one by one:
   `spike devs` after each; the time from plugging to "New device with
   address" in the log.  Then all four plugged before power-up.
2. **The hub's switching.**  `spike hub`: per port or not.  `spike port 2 off`:
   VBUS on port 2 drops to 0 V (meter), the DUT goes dark, the log shows its
   disconnect; `on`: it comes back and re-enumerates.  The other ports stay up.
3. **Listing and attaching.**  `usbip list -r usbspike-xxxx.local` (the hub
   shows up too, note it).  `sudo usbip attach -r ... -b 1-<addr>` for 2, then
   4 DUTs at once; `lsusb`, `/dev/ttyACM*` on the PC; a console on each.
4. **Flash time.**  One DUT alone: `time esptool --port /dev/ttyACM0
   write_flash 0x0 <1 MB image>` (twice).  Then 2 and 4 in parallel, each
   timed.  Expect the 12 Mbit/s to be shared; note errors and retries.
   A Pico in BOOTSEL: copy a UF2 alone, then while an ESP32 flashes.
5. **busid stability.**  Reset one DUT (its button, `esptool ... run`, or
   `spike port <n> cycle`): its address and busid before and after; the
   attached session on the PC (what `dmesg` and `usbip port` say, whether the
   node logs errors or crashes).  Then reset two DUTs at the same time: do
   their busids swap?  Re-attach and check you got the board you meant.
6. **Endurance.**  4 consoles streaming for 30 minutes; `kernel stacks` on the
   node before and after; Wi-Fi drops; errors in the log.
7. **Optional, without the DWC2 patch**, to compare: take
   `uhc-dwc2-channels.patch` out of `zephyr/patches.yml` locally, `west patch
   reverse && west patch apply`, rebuild, repeat 4, 5 and 8.
8. **Host channels.**  The DUTs quiet (nothing printing), a console open on
   each of the 4 (`picocom /dev/ttyACM0` … `ttyACM3` on the PC):
   - type a command in each console in turn: each answers at once (without
     the patch, one console does not open, or a command to a quiet board
     waits until another board prints);
   - change one console's line settings (`stty -F /dev/ttyACM1 9600`, a
     SET_LINE_CODING): no delay;
   - unplug and plug one DUT (or `spike port <n> cycle`), the other consoles
     open: it enumerates again within a couple of seconds, `usbip attach`
     works, its console comes back;
   - 10 re-plugs in a row, then `spike devs`: all four there, no "No channel
     data slot" and no stall in the node's log;
   - the endpoint slots (32) across re-enumerations, as the DATA ×4 v2
     co-processor's image swaps will do it: a Pico, attached over USB/IP,
     20 times `picotool reboot -u -f` (to BOOTSEL) then `picotool reboot`
     (back to its application), the other consoles open.  Each trip is two
     new devices with their own endpoints: without the patch each trip leaks
     4–6 slots, until "No channel data slot" a few trips later.  The
     Pico comes back every time, the other boards keep answering;
   - with the B3 analyzer as one of the four (a Pico 2 on gusmanb's UF2,
     [docs/multi-dut-node.md](../../../docs/multi-dut-node.md#a-logic-analyzer-in-a-sub-slot)):
     gusmanb's app attached and three consoles open, a full 8-channel
     capture (393 KB) downloads; time it, and type in a quiet console
     meanwhile: it answers.
   With `CONFIG_UHC_DRIVER_LOG_LEVEL_DBG=y` the log shows the channels given
   back ("Park ep …").

Bring back: the console logs, the times of 4, what 5 and 8 did, and `spike
hub`'s line for the hub used.
