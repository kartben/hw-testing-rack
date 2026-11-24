# Network ports, names and metrics

A bay node listens on six TCP ports and answers mDNS; the power hub listens on TCP 80 alone and answers
mDNS. Both speak IPv4 only, over Wi-Fi.

:::{status} simulated
DNS-SD is tested on native_sim. The `.local` names, telnet, USB/IP, the page and `/metrics` were in use on
the XIAO ESP32-S3 stand-in. The client counts below are the firmware's settings: none has been tried to its
limit on a v1.0 bay node, and no v1.0 hub has run. See
[What exists today](../plan/status.md#status-names).
:::

## A bay node's ports, and how many clients each takes

| Port | Service | Clients at once | Right |
|---|---|---|---|
| TCP 80 | the bay's page, the JSON API, the web consoles' and the analyzer's WebSockets, `/metrics` | 6 HTTP connections, and besides them 2 web consoles and 1 analyzer page | per route ([Bay node HTTP API](node-api.md)) |
| TCP 3240 | USB/IP | 6 sessions, one per device, and a `usbip list` meanwhile | usbip |
| TCP 23 | telnet, the node's shell | 1 | shell |
| TCP 4001 | the AUX UART, RFC 2217 | 1 | console |
| TCP 4000 | the AUX UART, raw bytes | 1 | console |
| TCP 8081 | the camera: `/snapshot.jpg`, `/stream.mjpg` | 3, streams and snapshots together | camera |
| UDP 5353 | mDNS and DNS-SD | | |

Read from the bay node's [prj.conf](../../firmware/bay-node/prj.conf) and
[Kconfig](../../firmware/bay-node/Kconfig), where each port and count is a build option:

- TCP 80 is `CONFIG_BAY_HTTP_PORT`. The server speaks HTTP/1.1 only and keeps 6 clients
  (`CONFIG_HTTP_SERVER_MAX_CLIENTS`); a connection idle for 3 s is closed, so that a browser's spare
  keep-alive connections do not hold every slot. The web consoles are `CONFIG_BAY_CONSOLE_WEB_CLIENTS`,
  1 to 4.
- USB/IP keeps 6 sessions on a module with PSRAM, which every v1.0 node has, and 1 without
  (`CONFIG_USBIP_DEVICES_COUNT`). The node's USB host holds 8 devices: the DATA board's hub, its boards, the
  co-processor and a spare.
- TCP 4001 and 4000 are `CONFIG_BAY_RFC2217_PORT` and `CONFIG_BAY_AUX_TCP_PORT`; 0 turns either off.
- TCP 8081 is `CONFIG_BAY_CAMERA_PORT`, its clients `CONFIG_BAY_CAMERA_CLIENTS`, 1 to 8. Without a camera
  it answers 503.

The access rules drop a refused connection to 3240, 23, 4000 and 4001 without an answer, so the client
waits for its own timeout. There is no TLS, no IPv6 and no login on telnet:
[Access rules and security](../use/access.md).

## The hub's ports

| Port | Service | Clients at once |
|---|---|---|
| TCP 80 | the rack's page, the JSON API, `/metrics` | 6 HTTP connections |
| UDP 5353 | mDNS and DNS-SD | |

Read from [prj.conf](../../firmware/power-hub/prj.conf) of the power hub. The hub has no telnet. Its shell,
which has no login of its own, is on its console USB-C only, so it takes a hand on the box. Its API is open
to anyone for reading, and every request that changes something is signed ([Power hub HTTP API](hub-api.md)).

## Names and DNS-SD records

A node answers to `bay-b3.local` once the hub has given it place B3, and the hub to `rack.local`. How each
gets its name, and the `hub id` trap: [Bays, ports and addresses](../use/names.md#host-names-and-how-a-bay-gets-its-own).

Under that name each advertises the services that listen:

| Device | Service | Port | Advertised |
|---|---|---|---|
| bay node | `_http._tcp` | 80 | always |
| bay node | `_usbip._tcp` | 3240 | while the data path is USB/IP: not in classic mode, not in SERVICE mode |
| bay node | `_rfc2217._tcp` | 4001 | while it listens |
| power hub | `_http._tcp` | 80 | always |

A node's TXT record holds `id` (its bay id), `pos` (its rack position), `fw` (the firmware's version),
`mode` (`usbip`, `classic` or `service`) and, with a DATA board, `slots`, the number of its ports. The hub's
holds `id` and `fw`. Read from [net.c](../../firmware/bay-node/src/net.c) of the node and `dnssd_fill()` in
[main.c](../../firmware/power-hub/src/main.c) of the hub.

The records are checked every 2 s (`CONFIG_HWTR_DNSSD_REFRESH_MS`) and kept 2 min in caches
(`CONFIG_MDNS_RESPONDER_TTL`, 120 s), so a service that stops can stay listed that long. The nodes that
offer USB/IP, on Linux and on macOS:

```console
$ avahi-browse -rt _usbip._tcp
$ dns-sd -B _usbip._tcp
```

## Prometheus metrics of a bay node

`GET /metrics` on TCP 80, with the status right. Fourteen metrics, each with one label, `bay="<id>"`, or
the host name when the bay has no id. There is no label per port: on a v1.0 node the `bay_dut_` metrics are
the DATA lead's, every board of the bay together.

| Metric | Type | What it measures |
|---|---|---|
| `bay_dut_vbus_volts` | gauge | the bay's supply after its switch: the DATA lead's on a v1.0 node |
| `bay_dut_current_amperes` | gauge | its current |
| `bay_dut_power_watts` | gauge | its power |
| `bay_dut_power_on` | gauge | 1 on, 0 off |
| `bay_dut_fault` | gauge | 1 in current limit or cut by a fault |
| `bay_dut_faults_total` | counter | faults since boot |
| `bay_usb_devices` | gauge | USB devices enumerated |
| `bay_usbip_sessions` | gauge | open USB/IP sessions |
| `bay_aux_rx_bytes_total` | counter | bytes from the board's console to the clients |
| `bay_aux_tx_bytes_total` | counter | bytes from the clients to the board's console |
| `bay_access_refused_total` | counter | connections and requests the rules refused |
| `bay_power_limit_watts` | gauge | what the ports are switched on within: the hub's grant, or the bay's own limit; 0 on a stand-in, which counts in mA |
| `bay_ports_waiting` | gauge | ports wanted on and kept off, waiting for power |
| `bay_ports_shed_total` | counter | ports shed for power since boot |

Read from `metrics_update()` in [web.c](../../firmware/bay-node/src/web.c). A negative reading, the meter's
offset around 0 A, is given as 0. The simulated node adds a `port` label that the firmware does not have.

## Prometheus metrics of the hub

`GET /metrics` on TCP 80, open to anyone. Fifteen metrics; the four `hub_row_` ones have a line per row
fitted on the hub, labelled `row="A"` to `row="D"`.

| Metric | Type | What it measures |
|---|---|---|
| `hub_contract_volts` | gauge | the USB PD contract's voltage |
| `hub_contract_amps` | gauge | the contract's current |
| `hub_vbus_volts` | gauge | VBUS (VRACK) on the controller's ADC |
| `hub_row_on` | gauge | 1 while the row is switched on |
| `hub_row_amps` | gauge | the row's current, from its eFuse |
| `hub_row_faults_total` | counter | the row's eFuse faults since boot |
| `hub_row_shed` | gauge | 1 while the row is off for lack of power |
| `hub_rows_amps` | gauge | what the rows draw together |
| `hub_budget_amps` | gauge | what the rows may draw: the contract, or the cap, less the margin |
| `hub_budget_cap_watts` | gauge | the cap set by hand, 0 for none |
| `hub_row_sheds_total` | counter | rows shed for lack of power since boot |
| `hub_nodes` | gauge | nodes on the rack bus |
| `hub_nodes_lost` | gauge | nodes gone silent |
| `hub_can_frames_total` | counter | CAN frames received |
| `hub_can_bus_off_total` | counter | bus-off events |

Read from `metrics_handler()` in [web.c](../../firmware/power-hub/src/web.c) of the hub.

```console
$ curl -s bay-b3.local/metrics
$ curl -s rack.local/metrics
```
