# Bay node HTTP API

A bay node serves HTTP on TCP port 80. `http://bay-b3.local/` is the bay's page, and the routes under
`/api/` form a JSON API. The examples use bay B3, which has a DATA ×4.

## Routes and the right each needs

Each route needs a right, which is one of the services in the [access rules](../use/access.md). Until the
node is claimed and its rules are on, everyone has every right. In the table, *admin* means a request
[signed with the node's key](#the-admin-signature). *Ticket* means a single-use token returned by the
previous request. A request without the right gets 403. While someone else holds a reservation, it gets 423.

| Route | Right | What it does |
|---|---|---|
| `GET /` | none | the bay's page |
| `GET /api/status` | status | the node's state ([field by field](#api-status-field-by-field)) |
| `POST /api/power` | control | power of the one board, or of a port with `"port"` |
| `POST /api/reset` | control | a RESET pulse |
| `POST /api/boot` | control | BOOT held across a RESET pulse |
| `POST /api/mode` | control | the data path, `usbip` or `classic` |
| `GET /api/ports` | status | every port's object |
| `POST /api/ports/<n>/power` | control, and the port's reservation | one port's power, n = 1 to 4 |
| `POST /api/ports/<n>/reset` | control, and the port's reservation | one port's RESET pulse |
| `POST /api/ports/<n>/boot` | control, and the port's reservation | one port into its bootloader |
| `GET /api/usb` | status | the USB devices |
| `GET /api/boards` | status | every port's board target |
| `GET /api/ports/<n>/board` | status | one port's board target, n = 1 to 4 |
| `PUT /api/ports/<n>/board` | control, and the port's reservation | sets or clears it |
| `GET /board-targets.json` | none | the targets the page suggests, by USB ID |
| `GET /api/aux` | status | the AUX UART's settings and clients |
| `POST /api/aux` | console | changes and saves them |
| `POST /api/aux/break` | console | a BREAK on the board's RX line |
| `POST /api/console/ticket` | console | a ticket for a WebSocket |
| `GET /console/ws/<n>?t=<ticket>` | ticket | a web console |
| `GET /api/camera` | status | the camera and its settings |
| `POST /api/camera` | control | changes and saves them |
| `GET /api/wires` | status | the DATA ×4's pin matrix |
| `POST /api/wires` | control, and the reservations of the ports it changes | sets it |
| `GET /api/analyzer` | status | the logic analyzer's owner |
| `POST /api/analyzer` | control | hands it to the page or to USB/IP |
| `GET /analyzer/ws?t=<ticket>` | ticket | the page's end of the analyzer |
| `GET /api/coproc` | none | the co-processor's stored image |
| `POST /api/coproc/begin` | admin | starts an upload of a new one |
| `POST /api/coproc?ticket=<ticket>` | ticket | the image itself |
| `GET /api/access` | status; admin sees more | rights, reservation, connections |
| `GET /api/access/nonce` | none | a nonce to sign with |
| `POST /api/access/claim` | none, then a press on BOOT | gives the node its key |
| `POST /api/access/rules` | admin | the rules |
| `POST /api/access/kick` | admin | closes a connection |
| `POST /api/access/key` | admin | a new key |
| `POST /api/lease` | control; to release: its holder, or admin | reserves, renews or releases |
| `GET /api/update` | none | the firmware and its last update |
| `POST /api/update/begin` | admin | starts an update |
| `POST /api/update?ticket=<ticket>` | ticket | the signed image |
| `GET /metrics` | status | Prometheus metrics |

Source: the `web.c` and `*_http.c` files in [firmware/bay-node/src](../../firmware/bay-node/src), and
[update_http.c](../../firmware/common/web/update_http.c).

The per-port routes exist for ports 1 to 4 only. On a DATA ×6, switch ports 5 and 6 with `POST /api/power`
and `"port": 5` or `"port": 6`.

## Requests, answers and errors

- Bodies and answers are JSON objects. An action returns the new status document. A per-port route returns
  the port's object.
- An error is `{"error": "…"}`. When the access rules refuse a request, the answer also holds `reason`
  (`not_allowed`, `kicked` or `reserved`), `service`, and `you`: your address as the node sees it.
- A longer body than its route takes gets 413. The limits are 96 bytes for an action, 192 for `/api/aux`,
  256 for `/api/camera`, 512 for a board target, 1 KB for the access routes and 1536 for `/api/wires`.

## /api/status, field by field

| Field | What it holds |
|---|---|
| `id`, `hostname`, `ip` | the bay id (`""` when unset), the host name without `.local`, the address |
| `version` | the Zephyr kernel's version. The firmware's is `firmware.version` |
| `path` | the data path: `usbip`, `classic` or `service` |
| `uptime_s`, `last_fault` | seconds since boot; the fatal error that restarted the node, `""` if none since power-on |
| `service`, `pc_detected`, `force_classic` | SERVICE switch on; a machine on the front port; classic mode forced |
| `usb` | `running`, `devices`, `sessions` (USB/IP) |
| `dut` | `on`, `fault`, `latched`, `meter`, `faults`, `mv`, `ma`, `mw`: the bay's supply on the DATA lead |
| `aux` | `baud`, `format` (`8N1`), `port` (raw TCP), `rfc2217_port`, `web_clients`, `rfc2217`, `raw` (each `true` while a client is connected), `rx`, `tx`, `dropped` |
| `access` | `enabled`, `claimed`, `you`, `allow` (the caller's rights), `refused`, `lease` (`holder`, `note`, `remaining_s`, `yours`; `holder` is `""` when there is none) |
| `rack` | `node` (0 until the hub gives one), `pos` (`"C3"`), `hub`, `hub_mv`, `hub_epr`, `rows_on` |
| `firmware` | what `GET /api/update` returns |
| `camera` | what `GET /api/camera` returns, without `settings` and `choices` |
| `budget` | `unit` (`mW`), `limit`, `granted` (the limit is the hub's grant), `reserve`, `draw`, `waiting`, `sheds`, `board` (a DATA board answers), `lead_off` (why the DATA lead is off, `null` when it is on) |
| `ports` | one short object per port: `slot`, `port`, `hub_port`, `lines`, `power` (`on`, `ma`, `state`, `queued`), `fault`, `usb` (`busid`), `usbip`, `lease` |
| `data_board` | `"x4"`, `"x6"`, `"unknown"` (something at 0x20 that is neither, left alone) or `null` |
| `coproc`, `analyzer` | what `GET /api/coproc` and `GET /api/analyzer` return |

The possible texts of `lead_off` are listed under
[Why the DATA lead stays off](states-and-messages.md#why-the-data-lead-stays-off).

## Power, reset, bootloader and mode

| Route | Body |
|---|---|
| `POST /api/power` | `{"action": "on" \| "off" \| "cycle", "ms": 1000, "port": 2}`; with a port, also `"action": "cancel"`, and `"when": "available"` beside `"on"` |
| `POST /api/reset` | `{"ms": 100, "port": 2}`, body optional |
| `POST /api/boot` | `{"port": 2, "power_cycle": true}`, body optional |
| `POST /api/mode` | `{"mode": "usbip" \| "classic"}`, saved |

- On a node with a DATA board, these routes need `"port"`.
- `ms` goes from 1 to 10000. A port that cycles stays off until its VBUS is under 1 V, 2 s at most.
- `"when": "available"` queues a power-on that the bay's budget has no room for (202). Without it, the
  request fails with 409 ([Power budget and queued ports](../use/power-budget.md)).
- A DATA ×6's port has no RESET or BOOT line (400).

## Ports of a DATA board

`GET /api/ports` returns an array, one object per port.

| Field | What it holds |
|---|---|
| `slot`, `port` | `"B3.2"` (the bay's place, else its id, and the port); the port's number |
| `hub_port` | the port of the DATA board's USB hub: n on a DATA ×4; on a DATA ×6, 6 for port 1 and n − 1 for port n |
| `lines` | `true` when the port has RESET and BOOT lines (a DATA ×4's port) |
| `power` | `on`, `mv`, `ma`, `mw`, `faults`, `state`, `queued` |
| `fault` | a latched over-current |
| `usb` | `{"vid", "pid", "busid"}`, or `null` without a device |
| `usbip` | `{"client": "<address>"}`, or `null` |
| `lease` | `{"holder", "note", "remaining_s", "yours"}`, or `null` |

`power.state` is `on`, `off`, `fault`, `shed` or `waiting`
([what each means](states-and-messages.md)). `power.queued` is `true` while a `"when": "available"` request
waits.

The per-port routes take the same bodies without `port`:

```console
$ curl -s -X POST bay-b3.local/api/ports/2/power -d '{"action":"cycle"}'
{"slot": "B3.2", "port": 2, "hub_port": 2, "lines": true, "power": {"on": true, "mv": 5071, "ma": 97, "mw": 491, "faults": 1, "state": "on", "queued": false}, "fault": false, "usb": null, "usbip": null, "lease": null}
```

## USB devices and board targets

`GET /api/usb` returns `{"hub": …, "devices": […]}`: the DATA board's USB hub, then each device with
`busid`, `slot`, `hub_port`, `vid`, `pid`, `name`, `name_from`, `manufacturer`, `serial`, `strings`, `speed`,
`classes`, `ttys`, `usbip` and `ma`.

| Field | What it holds |
|---|---|
| `classes` | a list of `CMSIS-DAP`, `Debug probe`, `Serial (FTDI)`, `Serial (CP210x)`, `Serial (CH34x)`, `Serial (PL2303)`, `Serial`, `CDC ACM`, `HID`, `Mass storage`, `DFU`, `Audio`, `Video`, `Vendor`, `Other` |
| `ttys` | the interfaces a host makes a tty of, numbered as udev does: `[{"if": "02"}]`, with `"port": 0` for a serial bridge |
| `usbip` | `{"client", "since_s", "offered", "read_ahead"}`. `offered` is `false` for a device the USB/IP service does not export |

`GET /api/boards` returns `{"slots": [{"slot", "port", "board", "runner", "probe_id", "console", "map",
"pinned", "device", "mismatch"}]}`. `PUT /api/ports/<n>/board` saves a port's target for the device that is in the port
now:

```console
$ curl -s -X PUT bay-b3.local/api/ports/1/board -d '{"board": "nucleo_g474re", "runner": "stm32cubeprogrammer", "console": "usb", "map": true}'
```

`console` is `usb`, `usb:02` (an interface), `aux` or `none`. A DATA board's port takes no `aux`. `"pin": {"vid", "pid", "serial"}` saves the
target for another device. A body without `board` clears the port. See [Board targets](../use/board-targets.md).

## Console

`POST /api/aux` takes any of these fields, applies them and saves them:

```json
{"baud": 115200, "data_bits": 8, "parity": "none", "stop_bits": 1, "enter": "cr", "echo": false, "esptool_reset": false}
```

`parity` is `none`, `odd` or `even`, `enter` is `cr`, `lf` or `crlf`, and `baud` goes from 300 to 5000000.
`POST /api/aux/break` takes `{"ms": 250}`. The board must be powered.

To open a web console:

1. Get a ticket from `POST /api/console/ticket`. A ticket works once, within 10 s.
2. Open the WebSocket `GET /console/ws/<n>?t=<ticket>`, with n = 0 or 1.

On connect, the WebSocket replays the last 16 KB of console output. The analyzer's WebSocket,
`GET /analyzer/ws?t=<ticket>`, also takes a ticket from `POST /api/console/ticket`. See
[Serial console](../use/serial-console.md).

## Camera

`GET /api/camera` returns the camera's state, its `settings` and their `choices`. `POST /api/camera` takes a
flat object of settings, such as `{"white_balance": "cloudy"}`, and saves them. Add `"reset": true` to put
the image settings back to automatic first. [Camera](../use/camera.md) lists the settings.

## Wires, analyzer and co-processor

These routes exist only on a node built to drive a DATA ×4.

| Route | Body and answer |
|---|---|
| `GET /api/wires` | `{"matrix", "error", "names": [8 strings], "pins": [{"port", "pin", "bus", "closed"}], "ports": [{"port", "on", "vref_mv", "held"}]}` |
| `POST /api/wires` | `{"pins": [{"port": 2, "pin": 1, "bus": "A"}, …], "names": ["UART", "", …]}`: puts these pins on their buses and takes every other pin off. `"pins": []` opens them all. Returns the same as `GET`, plus `changed`: the switches it moved |
| `GET /api/analyzer` | `{"owner", "present", "busid", "page", "from_device", "to_device", "dropped", "error"}` |
| `POST /api/analyzer` | `{"owner": "page" \| "usbip"}`. 409 while the analyzer is busy |
| `GET /api/coproc` | `{"image": {"name", "size", "addr", "sha256"} \| null, "upload", "error", "load": {"state", "loads", "failures", "last_ms", "error"}}` |
| `POST /api/coproc/begin` | admin, `{"size": N, "sha256": "<64 hex>"}` → `{"ticket": "<16 hex>"}` |
| `POST /api/coproc?ticket=…` | the image as `bayctl coproc load` makes it: a 64-byte header, then the bytes for the co-processor's SRAM. Returns the `GET` document |

A port is 1 to 4, a pin 1 to 8, a bus `A` to `H`. An upload erases the stored image first, so a failed
upload leaves the node with none. The image must be an RP2350 `no_flash` build. See
[Wires between boards](../use/wires.md) and [Logic analyzer](../use/logic-analyzer.md).

## Access and reservations

| Route | Body and answer |
|---|---|
| `GET /api/access` | `enabled`, `claimed`, `admin`, `you`, `source`, `allow`, `lease`, `connections` (`id`, `service`, `label`, `peer`, `port`, `since_s`), `refused_total`, `claim`. A signed request also gets `rules` and the log of refusals |
| `GET /api/access/nonce` | `{"nonce": "<16 hex>"}`: works once, for 60 s |
| `POST /api/access/claim` | `{}`, or `{"key": "<64 hex>"}` to give the node that key → `{"state": "pending", "ticket", "remaining_s"}`. Then poll with `{"ticket": "…"}`: `{"state": "pending", "remaining_s"}` until someone presses BOOT, then `{"state": "done", "key": "<64 hex>"}` |
| `POST /api/access/rules` | admin, `{"enabled": true, "everyone": ["status"], "sources": [{"name": "ci-runners", "cidr": "192.168.1.40/30", "allow": ["status", "control", "console", "usbip"]}]}`. Eight sources at most |
| `POST /api/access/kick` | admin, `{"id": "usbip:51234"}`, an id from `GET /api/access` |
| `POST /api/access/key` | admin, `{"key": "<64 hex>"}` → `{"saved": true}` |
| `POST /api/lease` | `{"ttl_s": 3600, "note": "twister job 8812"}` reserves or renews the bay. Add `"ports": ["B3.2"]` to reserve one or more ports instead. `{"release": true}` ends it. Returns the same as `GET /api/access`, with `ports` on a node with a DATA board |

A claim waits 60 s for someone to press BOOT. `ttl_s` goes from 10 to 86400, 3600 by default. `note` holds
up to 39 characters. A restart of the node ends a reservation.
[Reserve a bay](../use/reserve-a-bay.md) says what a reservation blocks.

## Firmware update

`GET /api/update` returns `version`, `id` (`bay-node/bay_node`), `test_key`, `slot_kb`, `state`,
`received`, `size`, `trial`, `last` and `error`. An update takes two requests:

1. `POST /api/update/begin`, admin, `{"size": N, "sha256": "<64 hex>", "force": false}` →
   `{"ticket": "<16 hex>", "id": "bay-node/bay_node"}`. The ticket works for one minute. A reserved bay
   needs `"force": true`.
2. `POST /api/update?ticket=…` with `zephyr.signed.bin` as the body. The node restarts and runs the new
   firmware on trial ([Update the firmware](../use/update-firmware.md)).

## The admin signature

An admin request carries the header `X-Bay-Auth: <nonce>:<mac>`. The nonce comes from
`GET /api/access/nonce` and works once, for 60 s. The mac is the HMAC-SHA256, under the node's 32-byte key,
of four lines: the nonce, the method, the path without its query string, and the body. This is how
`bayctl` signs a request:

```{literalinclude} ../../tools/bayctl.py
:language: python
:pyobject: sign
:caption: tools/bayctl.py
```

The key crosses the network once, in the answer to a claim.

## Status codes and their texts

| Code | When | Texts |
|---|---|---|
| 200 | done | |
| 202 | a port's power-on is queued | |
| 400 | a bad body or value | `bad JSON`; `ms must be 1..10000`; `action must be on, off, cycle or cancel`; `"when": "available" goes with "action": "on"`; `this port has no such line`; `mode must be usbip or classic`; `the DUT is powered off`; `no BREAK on this board (no tx-gpios)`; `parity must be none, odd or even`; `enter must be cr, lf or crlf`; `this node serves one board: lease the bay (no "ports")`; `ttl_s must be 10..86400`; `ports: a list of sub-slots`; `ports: unknown sub-slot`; `key: 64 hex digits`; `baud 300..5000000, data bits 5..8, stop bits 1 or 2`; `size and sha256 (64 hex digits) needed`; a board target's or a camera setting's own text; for an upload, `SHA-256 does not match`, `fewer bytes than announced`, `image for power-hub/power_hub, this is bay-node/bay_node` |
| 403 | refused | `not allowed from this address`; `kicked by an admin: retry in a minute`; `bad or expired admin signature`; `admin only: sign the request with the key`; `admin only: unlock with the admin key`; `admin only: claim the device first`; `only its holder or an admin may release it`; `no such ticket: begin again` |
| 404 | nothing there | `no port 5 on this node`; `no camera on this bay`; `nobody pressed BOOT in time`; `no such claim from this address`; `no such connection`; any route that does not exist |
| 409 | not now | `this node serves 4 boards: say which ("port": 1..4, or /api/ports/<n>/...)`; `no room in the bay's budget: the bay draws <n> mW, <n> mW kept for a start, <n> mW in all (the hub's grant)`; `the port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone`; `no queued request on this port`; `already claimed: unlock with the admin key, or reset the node`; `the analyzer is busy: try again (<n>)`; `the running firmware is on trial: wait until it confirms itself`; `another update is on its way`; `reserved by <address> for <n> min more: force to update anyway`; `the co-processor is being loaded: try again in a few seconds` |
| 413 | too large | `body too large`; `size: larger than the update slot`; `size: larger than the coproc partition` |
| 423 | reserved by another address | `reserved by <address> (<note>), <n> min left`; `B3.2 reserved by <address> (<note>), <n> min left`; `B3.2 reserved by <address>`, to a lease over a held port; `B3.2 is reserved by another address`; `reserved: another address holds the lease` |
| 500 | the node failed | `action failed`; `response too large`; `rules applied, not saved`; `the UART refused it` |
| 503 | the port cannot act | `the port is off, or the DATA board is not set up (DUT_5V off?)` |

Source: the route files, [update.c](../../firmware/common/lib/update.c) and
[coproc.c](../../firmware/bay-node/src/coproc.c).
[States and messages](states-and-messages.md) explains each text.

## Examples with curl

```console
$ curl -s bay-b3.local/api/status | jq .budget
$ curl -s bay-b3.local/api/ports | jq '.[] | {slot, state: .power.state, busid: .usb.busid}'
$ curl -s -X POST bay-b3.local/api/ports/2/power -d '{"action":"on","when":"available"}'
$ curl -s -X POST bay-b3.local/api/ports/2/boot -d '{"power_cycle":true}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"ttl_s":1800,"note":"twister job 8812","ports":["B3.2"]}'
$ curl -s -X POST bay-b3.local/api/lease -d '{"release":true,"ports":["B3.2"]}'
$ curl -s -X POST bay-b3.local/api/wires -d '{"pins":[{"port":1,"pin":1,"bus":"A"},{"port":2,"pin":1,"bus":"A"}]}'
```
