# One node, four boards: the firmware side

> **Status: design only in the firmware; the tools and the node's simulator
> follow it (see Tools).**  Density epic, decision 3
> (2026-10-19): one node serves up to four small USB-native boards through a
> hub on a "DATA ×4" board in the drawer, sub-slots A1.1–A1.4.  What the
> firmware needs, and what Zephyr lacks for it.  The bench spike that checks
> the risky part (a hub behind the ESP32-S3, several USB/IP exports) is
> [`firmware/spikes/usb-hub`](../firmware/spikes/usb-hub/README.md); its results
> may change this note.

## What the firmware sees

| | Today (one DUT) | With DATA ×4 |
|---|---|---|
| USB | the DUT on the S3's OTG port, or the front PC port (classic mode) | a hub on the OTG port, 4 DUTs behind it; classic mode: the laptop sees the hub and the 4 DUTs at high speed |
| Power | TPS2553 + INA226 on the node | one switch and one current sense per port on DATA ×4 (≈ 0.5 A each), reached over I²C on J7 (PH-8: I²C, an interrupt) |
| RESET / BOOT | two node GPIOs | per port, through an I²C expander on DATA ×4 |
| Console | the AUX UART | the boards' own USB (CDC): no AUX per sub-slot |

A node without DATA ×4 stays a one-port node: everything below keeps
working with N = 1, and today's API keeps its meaning.

**Devicetree.**  Today's `hwtr,dut-port`, one node per sub-slot, plus where
it sits; no `uart`.  The board's wiring stays data, not code:

```dts
dut_port1: dut-port-1 {
	compatible = "hwtr,dut-port";
	sub-slot = <1>;                 /* A1.1 */
	hub-port = <3>;                 /* the hub's downstream port wired to it */
	enable-gpios = <&ports_io 0 GPIO_ACTIVE_HIGH>;
	fault-gpios = <&ports_io 1 GPIO_ACTIVE_LOW>;
	reset-gpios = <&ports_io 2 GPIO_ACTIVE_HIGH>;
	boot-gpios = <&ports_io 3 GPIO_ACTIVE_HIGH>;
	power-monitor = <&port1_sense>;
};
/* dut-port-2..4 */
```

The expander's pins come up as inputs: pull-ups on DATA ×4 keep the
binding's rule that a board is powered before (and without) any firmware.

Power goes through the board's switches (current limit, fault, measured),
not the hub's own port power: it does not depend on the USB link, and works
for a board that hangs its USB.  The hub's `SetPortFeature(PORT_POWER)` stays
a fallback (the spike checks which hubs really switch).

## Names and USB/IP

- A sub-slot is the bay's position plus its port: `A1.2`.  The node knows
  its position from the rack bus (`bay_rack_position()`), its ports from the
  devicetree.
- **busid.**  Zephyr's USB/IP names a device `1-<address>`, the address the
  host gave at enumeration: it changes when a board re-enumerates, and two
  boards that reset together can swap.  The node names it by where it is
  plugged instead, as Linux does: `1-1.<hub port>` (root port 1, then the hub's
  port), so `A1.2` is always the same busid.  A one-board node keeps `1-1`.
- **The hub is hidden** from `usbip list`; only the boards are exported.
- **A board that disconnects** ends its USB/IP session (the client sees a
  detach); when it comes back, it is listed again under the same busid, and
  `bayctl attach --follow` re-attaches it.
- **Sessions.**  `CONFIG_USBIP_DEVICES_COUNT=4`: one thread and a 2 KB stack
  each.

The busid, the hidden hub and the session that ends with its board are
done: a patch to Zephyr's `subsys/usb/host/usbip.c` that the workspace
applies (`west patch apply`, [`zephyr/patches.yml`](../zephyr/patches.yml)),
tested on native_sim with Zephyr's virtual USB bus
([`firmware/common/tests/usbip`](../firmware/common/tests/usbip/test_usbip.py)),
not yet on a node or behind a real hub.

## Per-port state

Each sub-slot gets what the single DUT has today: power on / off / cycle, a
latched fault, its current (V, mA, mW), RESET and BOOT pulses, its USB
device (VID:PID, product, serial, busid) and the USB/IP client attached.
`dut.c` becomes a table of ports; port 1 of a one-port node is today's DUT.

## REST API

| Endpoint | |
|---|---|
| `GET /api/ports` | `[{"slot": "A1.2", "port": 2, "hub_port": 3, "power": {...}, "fault": ..., "usb": {"vid": ..., "pid": ..., "product": ..., "busid": "1-1.3"} \| null, "usbip": {"client": "10.0.4.17"} \| null, "lease": ...}]` |
| `POST /api/ports/<n>/power` | `{"action": "on" \| "off" \| "cycle", "ms": 1000}` |
| `POST /api/ports/<n>/reset`, `/boot` | as today, for one port |
| `GET /api/status` | adds `ports` (the same objects, shorter) |
| `/api/power`, `/api/reset`, `/api/boot` | unchanged on a one-port node; on a multi-port node they need `"port": n` (409 without) |
| `/metrics` | the DUT metrics labelled `port="A1.2"` |

## Access control and leases

- The services stay (status, control, console, usbip, shell, camera).
- **A lease takes sub-slots**: `{"ttl_s": 3600, "ports": ["A1.2"]}` (no
  `ports`: the whole bay, as today).  Control of a leased port, and its
  USB/IP import, belong to the holder; the other ports stay free.
- USB/IP shares one TCP port (3240) for every board, so the per-port check
  cannot be the packet filter: the node checks at **import** time (the busid
  names the port).  That needs a policy hook in Zephyr's USB/IP service.

## Rack bus (CAN)

- **STATUS** keeps the node's totals (the sum of the currents, flags ORed),
  so a hub that does not know ports still shows the bay; a new byte 6 bit,
  `RACK_ST2_PORTS`, says the node has several.
- A new **PORTS** frame (function 0x7, `0x380 + id`, unused today; every
  second, multi-port nodes only), 8 bytes: bytes 0–1 four 4-bit port flags
  (powered, fault, USB device, USB/IP attached: STATUS's own bits), bytes
  2–7 four 12-bit currents in mA (4095: more).
- **CMD** POWER, RESET and BOOTLOADER take the port in `arg[5]` (`nargs` 6;
  absent or 0: every port).  **ALERT** adds the port in byte 3.
- `RACK_PROTO_VERSION` 2 (HELLO and INFO carry it): a v1 hub ignores PORTS,
  a v2 hub treats a v1 node as one port.  The hub's page shows four dots on
  a multi-port tile.

## Tools

- `config/lab.yaml` names boards by sub-slot (`bays: {A1.2: {platform:
  xiao_esp32c3}}`); `config/rack.yaml` says which bays hold a DATA ×4.
- `bayctl attach A1.2` asks `bay-a1.local/api/ports` for port 2's busid and
  runs `usbip attach -r bay-a1.local -b 1-1.3`; a new `--follow` re-attaches
  after a reset.  `bayctl power A1.2 cycle`, `bayctl reset A1.2`; a bare
  `A1` still means the whole bay.
- `bayctl hwmap` and the labgrid / twister exports: one target per sub-slot.

Done on the tools side (2026-10-19), against the simulated node: a bay's
`boards:` in `config/rack.yaml` (`tools/rackcfg.py` › `dut_slots`,
`bay_boards`), one shared plate per converted bay (`board_plate.scad`
`BAY="<id>"`, `plate_bay_<id>.stl`, laid out from each board's `at` and checked
clear of the RESET/BOOT pin holes), `bayctl ports`, per-port power, reset,
leases and `attach --follow`, and `firmware/bay-node/web/dev_server.py
--ports 4` serving this API.  The firmware itself: nothing yet.

## Resources

The bay node has about 12 KB of DRAM left.  Three more USB/IP sessions (≈ 6 KB of
stacks), the hub class (2 KB work queue stack, its data), more host devices
and transfers: about 10–12 KB, to measure in the spike (`kernel stacks`).
`CONFIG_ESP32_WIFI_NET_ALLOC_SPIRAM` (network buffers and TCP connections to
PSRAM, ≈ 30 KB) is the likely way, once USB/IP throughput through PSRAM is
measured.  USB stays 12 Mbit/s for the four boards: parallel flashing shares
it (measured in the spike).

## What Zephyr needs (upstream)

| Where | What | |
|---|---|---|
| `usbip.c` | busid by port path (`1-1.3`), not by address | in `zephyr/patches.yml`, not proposed upstream yet |
| `usbip.c` | hubs left out of the device list | same patch |
| `usbip.c` | a session ends when its device disconnects (upstream keeps a pointer to the freed device) | same patch |
| `usbip.c` | an import policy callback (busid, client address) | for per-port leases |
| host core | a device's removal that waits for its cancelled transfers before freeing it (`usbh_device_disconnect()` frees at once; the controller cancels in its own thread) | a narrow window, for every class, not only USB/IP |
| hub class | a public API for port power and status, and port events for the application | the spike uses the stack's private requests |
| `uhc_dwc2.c` | low-speed devices behind a full-speed hub (`HCCHAR.LSPDDEV`) | only if a low-speed DUT is wanted |
| `uhc_dwc2.c` | #120848, #120961, #121688 (data toggles, bulk retries; seen behind a hub on the P4) | to land first |

## Open

- Which hub chip on DATA ×4: high speed upstream for the laptop mode,
  full speed behind the node.  One configurable over I²C (USB2514B-class,
  with per-port power pins) would let the node set it up on the same bus.
- One node failing takes four boards: the hub page should say so.
- The AUX UART: a multiplexer on DATA ×4, or none (decision 1: USB-native
  boards only).
- The camera sees four boards on one plate (decision 7, open).
