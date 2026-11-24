# Network ports and metrics

This page lists the network ports, mDNS names and Prometheus metrics of the bay nodes and the power hub. Both
connect over Wi-Fi, with IPv4 only.

## A bay node's ports

| Port | Service | Clients at once | Right |
|---|---|---|---|
| TCP 80 | the bay's page, the JSON API, the WebSockets of the web consoles and the analyzer, `/metrics` | 6 HTTP connections, plus 2 web consoles and 1 analyzer page | per route ([Bay node HTTP API](node-api.md)) |
| TCP 3240 | USB/IP | 6 sessions, one per device, plus one `usbip list` | usbip |
| TCP 23 | telnet, the node's shell | 1 | shell |
| TCP 4001 | the AUX UART, RFC 2217 | 1 | console |
| TCP 4000 | the AUX UART, raw bytes | 1 | console |
| TCP 8081 | the camera: `/snapshot.jpg`, `/stream.mjpg` | 3, streams and snapshots together | camera |
| UDP 5353 | mDNS and DNS-SD | | |

You can change each port and each count with a build option, in the bay node's
[prj.conf](../../firmware/bay-node/prj.conf) and [Kconfig](../../firmware/bay-node/Kconfig):

| Option | Default |
|---|---|
| `CONFIG_BAY_HTTP_PORT` | 80 |
| `CONFIG_HTTP_SERVER_MAX_CLIENTS` | 6 |
| `CONFIG_BAY_CONSOLE_WEB_CLIENTS` | 2, from 1 to 4 |
| `CONFIG_USBIP_DEVICES_COUNT` | 6 on a module with PSRAM, as on the bay node PCB |
| `CONFIG_BAY_RFC2217_PORT`, `CONFIG_BAY_AUX_TCP_PORT` | 4001 and 4000. 0 turns either off |
| `CONFIG_BAY_CAMERA_PORT`, `CONFIG_BAY_CAMERA_CLIENTS` | 8081, and 3 clients, from 1 to 8 |

The node closes an HTTP connection after 3 s without traffic. On the other ports, the access rules drop a
refused connection without an answer, so the client waits until its own timeout. There is no TLS, and no
login on telnet ([Control who can use the rack](../use/access.md)).

## The hub's ports

| Port | Service | Clients at once |
|---|---|---|
| TCP 80 | the rack's page, the JSON API, `/metrics` | 6 HTTP connections |
| UDP 5353 | mDNS and DNS-SD | |

The hub has no telnet: its shell is on its console USB-C ([Power hub shell](hub-shell.md)).

## Names and DNS-SD records

A node answers to `bay-b3.local` once the hub has given it place B3, and the hub to `rack.local`
([Bays, ports and addresses](../use/names.md)). Each advertises its services:

| Device | Service | Port | Advertised |
|---|---|---|---|
| bay node | `_http._tcp` | 80 | always |
| bay node | `_usbip._tcp` | 3240 | while the data path is USB/IP: not in classic mode, not in SERVICE mode |
| bay node | `_rfc2217._tcp` | 4001 | while it listens |
| power hub | `_http._tcp` | 80 | always |

A node's TXT record holds `id`, `pos` (its place), `fw` (its firmware version), `mode` (`usbip`, `classic`
or `service`) and, with a DATA board, `slots` (its number of ports). The hub's TXT record holds `id` and
`fw`. After a service stops, caches can still list it for 2 min.

To list the nodes that offer USB/IP on Linux:

```console
$ avahi-browse -rt _usbip._tcp
```

On macOS:

```console
$ dns-sd -B _usbip._tcp
```

## Metrics of a bay node

Read them with `GET /metrics` on TCP 80. This needs the status right. Each metric has one label,
`bay="<id>"`, or the host name when the bay has no id. The `bay_dut_` metrics cover the whole bay. There is
no label per port.

| Metric | Type | What it measures |
|---|---|---|
| `bay_dut_vbus_volts` | gauge | the DATA lead's voltage, after the node's switch |
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
| `bay_power_limit_watts` | gauge | the power the ports are switched on within: the hub's grant, or the bay's own limit |
| `bay_ports_waiting` | gauge | ports wanted on and kept off, waiting for power |
| `bay_ports_shed_total` | counter | ports shed for lack of power since boot |

Source: `metrics_update()` in [web.c](../../firmware/bay-node/src/web.c).

## Metrics of the hub

Read them with `GET /metrics` on TCP 80. Anyone may read them. The `hub_row_` metrics have one line per row,
labelled `row="A"` to `row="D"`.

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

Source: `metrics_handler()` in the hub's [web.c](../../firmware/power-hub/src/web.c).

```console
$ curl -s bay-b3.local/metrics
$ curl -s rack.local/metrics
```
