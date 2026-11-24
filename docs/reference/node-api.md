# Bay node HTTP API

A bay node answers plain HTTP/1.1 on TCP 80: `http://bay-b3.local/` is the bay's page, `/api/…` a JSON API
that does what the node's shell does, `/metrics` its Prometheus metrics. The camera's pictures are on TCP
8081, and the server keeps six clients ([Network ports, names and metrics](network.md)).

:::{status} bench
The XIAO ESP32-S3 stand-in served the page, `/api/status`, `/metrics`, a claim and an update over Wi-Fi. The
other routes are tested on native_sim and against the simulated node, `web/dev_server.py`, whose JSON has the
firmware's shape with a few differences (the note below). The routes of a DATA board's ports have run
against emulated DATA boards only, never on a v1.0 bay node. See
[What exists today](../plan/status.md#status-bay-page).
:::

The examples act on bay B3, a DATA ×4 bay; the answer shown was captured from the simulated node, which puts
a space after each `:` and `,` where the firmware puts none, and whose readings change from run to run.

## Routes and the right each needs

A right is one of the services of the access rules: `status`, `control`, `console`, `usbip`, `shell`,
`camera` ([Access rules and security](../use/access.md)). Until a node is claimed and its rules are switched
on, every address has every right. *Admin* is a request signed with the node's key
([The admin signature](#the-admin-signature)); *ticket* is a single-use token handed out by the request
before it. A route needs the right named, and refuses with 403 or 423 otherwise.

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
| `POST /api/lease` | control; a release: its holder, or admin | reserves, renews or releases |
| `GET /api/update` | none | the firmware and its last update |
| `POST /api/update/begin` | admin | starts an update |
| `POST /api/update?ticket=<ticket>` | ticket | the signed image |
| `GET /metrics` | status | Prometheus metrics |

Read from [web.c](../../firmware/bay-node/src/web.c), [wires_http.c](../../firmware/bay-node/src/wires_http.c),
[analyzer_http.c](../../firmware/bay-node/src/analyzer_http.c),
[coproc_http.c](../../firmware/bay-node/src/coproc_http.c) and
[update_http.c](../../firmware/common/web/update_http.c). The page's own scripts and styles (`/rack.css`,
`/rack.mjs`, xterm.js, `/wires-card.mjs`, `/analyzer/card.mjs` and its modules) are served to anyone. The
camera routes exist on builds with the camera, the wires, analyzer and co-processor routes on builds for a
node that can drive a DATA ×4.

:::{note}
Where the simulated node and firmware 0.5.0 differ. Firmware 0.5.0 registers `/api/ports/<n>/power`,
`/reset`, `/boot` and `/board` for ports 1 to 4 only: on a DATA ×6, ports 5 and 6 answer 404 there. Their
power goes through `POST /api/power` with `"port": 5`, which is what the bay's page sends for every port;
`bayctl`, which uses the per-port routes, reaches ports 1 to 4. The simulated node accepts any port number.
A port's `usb` object in `/api/ports` is `{"vid", "pid", "busid"}` on the firmware; the simulated node adds
`manufacturer`, `product`, `serial`, `classes` and `ttys`, so `bayctl ports` prints a product name there and
none on a node. The names are in `GET /api/usb`.
:::

## Requests, answers and errors

- A body is a JSON object. The action routes (`/api/power`, `/reset`, `/boot`, `/mode`, `/aux/break`)
  answer with the new status document, the per-port routes with the port's object.
- An error is `{"error": "…"}` with a 4xx or 5xx status. A refusal by the access rules adds `reason`
  (`not_allowed`, `kicked` or `reserved`), `service` and `you`, the address the node saw.
- A body larger than its route takes is refused with 413 `body too large`: 96 bytes for an action, 192 for
  `/api/aux`, 256 for `/api/camera`, 512 for a board target, 1536 for `/api/wires`, 1 KB for the access
  routes, enough for eight sources.
- A connection idle for 3 s is dropped.

## /api/status, field by field

| Field | What it holds |
|---|---|
| `id`, `hostname`, `ip` | the bay id (`""` unset), the host name without `.local`, the address |
| `version` | the Zephyr kernel's version. The firmware's is `firmware.version` |
| `path` | the data path: `usbip`, `classic` or `service` |
| `uptime_s`, `last_fault` | seconds since boot; the fatal error that restarted the node, `""` if none since power-on |
| `service`, `pc_detected`, `force_classic` | SERVICE switch on; a machine on the front port; classic mode forced |
| `usb` | `running`, `devices`, `sessions` (USB/IP) |
| `dut` | `on`, `fault`, `latched`, `meter`, `faults`, `mv`, `ma`, `mw`: the bay's supply, on a v1.0 node the DATA lead's |
| `aux` | `baud`, `format` (`8N1`), `port` (raw TCP), `rfc2217_port`, `web_clients`, `rfc2217`, `raw` (each `true` while a client is connected), `rx`, `tx`, `dropped` |
| `access` | `enabled`, `claimed`, `you`, `allow` (the caller's rights), `refused`, `lease` (`holder`, `note`, `remaining_s`, `yours`; `holder` `""` when none) |
| `rack` | `node` (0 before the hub gave one), `pos` (`"C3"`), `hub`, `hub_mv`, `hub_epr`, `rows_on` |
| `firmware` | what `GET /api/update` answers |
| `camera` | what `GET /api/camera` answers, without `settings` and `choices` |
| `budget` | `unit` (`mW` on a v1.0 node, `mA` on a stand-in), `limit`, `granted` (the limit is the hub's grant), `reserve`, `draw`, `waiting`, `sheds`, `board` (a DATA board answers), `lead_off` (why the DATA lead is off, `null` when it is not) |
| `ports` | one short object per port: `slot`, `port`, `hub_port`, `lines`, `power` (`on`, `ma`, `state`, `queued`), `fault`, `usb` (`busid`), `usbip`, `lease` |
| `data_board` | `"x4"`, `"x6"`, `"unknown"` (something at 0x20 that is neither, left alone) or `null` |
| `coproc`, `analyzer` | what `GET /api/coproc` and `GET /api/analyzer` answer |

Read from `status_fill()` and `respond_status()` in [web.c](../../firmware/bay-node/src/web.c). The texts
of `lead_off`: [Bay node shell](node-shell.md#the-data-leads-reasons).

## Power, reset, bootloader and mode

| Route | Body |
|---|---|
| `POST /api/power` | `{"action": "on" \| "off" \| "cycle", "ms": 1000, "port": 2}`; with a port, also `"action": "cancel"`, and `"when": "available"` beside `"on"` |
| `POST /api/reset` | `{"ms": 100, "port": 2}`, body optional |
| `POST /api/boot` | `{"port": 2, "power_cycle": true}`, body optional |
| `POST /api/mode` | `{"mode": "usbip" \| "classic"}`, saved |

On a node with a DATA board, `/api/power`, `/reset` and `/boot` need `"port"`, or the per-port routes below;
without it they answer 409. `ms` goes from 1 to 10000. A `cycle` keeps the one board off `ms`, 1000 by
default. A port stays off `ms` (0 by default), then until its VBUS reads under 1 V, 2 s at most: a port's
switch does not discharge its output. A RESET pulse is 100 ms unless `ms`. `power_cycle` holds BOOT across a power cycle of the port instead of a RESET pulse. `"when":
"available"` queues a power-on that the bay's budget has no room for: 202, and the port goes on by itself in
its turn ([Power budget and queued ports](../use/power-budget.md)); without it the request fails with 409.
A DATA ×6's port has no RESET or BOOT line: 400 `this port has no such line`.

## Ports of a DATA board

`GET /api/ports` answers an array, one object per port; a node without a DATA board answers one object,
port 1, with `hub_port` `null` and the busid `1-1`.

| Field | What it holds |
|---|---|
| `slot`, `port` | `"B3.2"` (the bay's place, else its id, and the port), the port's number |
| `hub_port` | the port of the DATA board's USB hub: n on a DATA ×4; 6 for port 1 and n − 1 for port n on a DATA ×6 |
| `lines` | the port has RESET and BOOT lines (a DATA ×4's port) |
| `power` | `on`, `mv`, `ma`, `mw`, `faults`, `state`, `queued` |
| `fault` | a latched over-current |
| `usb` | `{"vid", "pid", "busid"}`, or `null` without a device |
| `usbip` | `{"client": "<address>"}`, or `null` |
| `lease` | `{"holder", "note", "remaining_s", "yours"}`, or `null` |

`power.state` is `on`; `fault`; `shed`, switched off for power and back once there is room; `waiting`,
wanted on and kept off for its turn or for power; or `off`. `power.queued` is `true` while a `"when":
"available"` request waits. Why port 1 of a DATA ×6 sits on hub port 6: [Bays, ports and addresses](../use/names.md).

`POST /api/ports/<n>/power`, `/reset` and `/boot` take the bodies of `/api/power`, `/reset` and `/boot`
without `port`, and answer with the port's object:

```console
$ curl -s -X POST bay-b3.local/api/ports/2/power -d '{"action":"cycle"}'
{"slot": "B3.2", "port": 2, "hub_port": 2, "lines": true, "power": {"on": true, "mv": 5071, "ma": 97, "mw": 491, "faults": 1, "state": "on", "queued": false}, "fault": false, "usb": null, "usbip": null, "lease": null}
```

## USB devices and board targets

`GET /api/usb` answers `{"hub": …, "devices": […]}`. `hub` is the DATA board's hub, `{"vid", "pid", "name",
"data_x4"}`, or `null`; hubs are never in `devices`. Each device has `busid`, `slot`, `hub_port`, `vid`,
`pid`, `name`, `name_from` (`product`, `table` or `ids`), `manufacturer`, `serial`, `strings`, `speed`
(`low`, `full`, `high` or `unknown`), `classes`, `ttys`, `usbip` and `ma`.

- `classes` is a list of `CMSIS-DAP`, `Debug probe`, `Serial (FTDI)`, `Serial (CP210x)`, `Serial (CH34x)`,
  `Serial (PL2303)`, `Serial`, `CDC ACM`, `HID`, `Mass storage`, `DFU`, `Audio`, `Video`, `Vendor`, `Other`.
- `ttys` lists the interfaces a host makes a tty of, numbered as udev does: `[{"if": "02"}]`, with
  `"port": 0` for a serial bridge.
- `usbip` is `{"client", "since_s", "offered", "read_ahead"}`: `offered` is false for a device the USB/IP
  service does not export. The serial numbers are readable with the status right, for twister's hardware
  maps.

`GET /api/boards` answers `{"slots": [{"slot", "port", "board", "runner", "probe_id", "console", "map",
"pinned", "device", "mismatch"}]}`, `null` where a field is unset or a port is empty. `PUT
/api/ports/<n>/board` saves a port's target for the device in it now:

```console
$ curl -s -X PUT bay-b3.local/api/ports/1/board -d '{"board": "nucleo_g474re", "runner": "stm32cubeprogrammer", "console": "usb", "map": true}'
```

`console` is `usb`, `usb:02` (an interface, two hex digits), `aux` or `none`; a DATA board's port takes no
`aux`. `"pin": {"vid", "pid", "serial"}` saves it for another device, as a restore does. A body without
`board` clears the port. What a target is for: [Board targets](../use/board-targets.md).

## Console

`POST /api/aux` takes any of `{"baud": 115200, "data_bits": 8, "parity": "none" | "odd" | "even",
"stop_bits": 1, "enter": "cr" | "lf" | "crlf", "echo": false, "esptool_reset": false}`, applies and saves
them, and answers as `GET /api/aux` does: those fields, then `web_clients`, `web_slots`, `rfc2217`,
`rfc2217_port`, `raw`, `raw_port`, `rx`, `tx`, `dropped`. Baud goes from 300 to 5000000. `POST
/api/aux/break` takes `{"ms": 250}`, body optional, and needs the board powered.

A WebSocket has no address the node can check, so a browser first asks `POST /api/console/ticket` for
`{"ticket": "<16 hex>"}`: single use, valid 10 s, and worth the console right of the address that asked
for it. Then `GET /console/ws/<n>?t=<ticket>` opens console n, 0 or 1 by default: binary frames both ways,
the last 16 KB replayed on connect, text frames for control. The analyzer's WebSocket takes the same ticket. What the
console is for, and RFC 2217 and raw TCP beside it: [Serial console](../use/serial-console.md).

## Camera

`GET /api/camera` answers `present` (`false`: no camera answered), `model`, `port`, `resolution`, `quality`,
`light`, `rotation`, `lit`, `clients`, `streams`, `slots`, `frames`, `errors`, `last_bytes`, `last_ms`,
`fps`, then `settings` and their `choices`. `POST /api/camera` takes a flat object of settings, numbers or
words, and `"reset": true` to put the image settings back to automatic first; all or nothing, saved.
Without a camera it answers 404 `no camera on this bay`. The settings and their ranges:
[Camera](../use/camera.md).

## Wires, analyzer and co-processor

Served by a node built to drive a DATA ×4.

| Route | Body and answer |
|---|---|
| `GET /api/wires` | `{"matrix", "error", "names": [8 strings], "pins": [{"port", "pin", "bus", "closed"}], "ports": [{"port", "on", "vref_mv", "held"}]}` |
| `POST /api/wires` | `{"pins": [{"port": 2, "pin": 1, "bus": "A"}, …], "names": ["UART", "", …]}`: the pins from now on, every other pin off the buses; `"pins": []` opens them all. Answers as `GET`, with `changed`, the switches moved |
| `GET /api/analyzer` | `{"owner", "present", "busid", "page", "from_device", "to_device", "dropped", "error"}` |
| `POST /api/analyzer` | `{"owner": "page" \| "usbip"}`; 409 while the analyzer is busy |
| `GET /api/coproc` | `{"image": {"name", "size", "addr", "sha256"} \| null, "upload", "error", "load": {"state", "loads", "failures", "last_ms", "error"}}` |
| `POST /api/coproc/begin` | admin, `{"size": N, "sha256": "<64 hex>"}` → `{"ticket": "<16 hex>"}` |
| `POST /api/coproc?ticket=…` | the image as `bayctl coproc load` makes it: a 64-byte header, then the bytes for the co-processor's SRAM → the `GET` document |

A port is 1 to 4, a pin 1 to 8, a bus `A` to `H`; a pin goes on one bus. `vref_mv` is `null` on a v1.0
DATA ×4, which has no VREF reading. `upload` is `idle`, `ready` or `receiving`; `load.state` is `idle`,
`loading`, `started`, `loaded`, `failed` or `left to USB/IP`. An upload erases the stored image as its
first bytes arrive, so a failed upload leaves the node with none. The node refuses (400) an image that is not
for an RP2350 in Arm mode or does not lie wholly in its SRAM: `image outside the RP2350's SRAM (a no_flash
build is needed)`. How to use them:
[Wires between boards](../use/wires.md), [Logic analyzer](../use/logic-analyzer.md).

## Access and reservations

| Route | Body and answer |
|---|---|
| `GET /api/access` | `enabled`, `claimed`, `admin`, `you`, `source`, `allow`, `lease`, `connections` (`id`, `service`, `label`, `peer`, `port`, `since_s`), `refused_total`, `claim`; signed, also `rules` and the log of refusals |
| `GET /api/access/nonce` | `{"nonce": "<16 hex>"}`: single use, 60 s |
| `POST /api/access/claim` | `{}`, or `{"key": "<64 hex>"}` to give the node that key → `{"state": "pending", "ticket", "remaining_s"}`. Then `{"ticket": "…"}` until someone presses BOOT: `{"state": "pending", "remaining_s"}`, then `{"state": "done", "key": "<64 hex>"}` |
| `POST /api/access/rules` | admin, `{"enabled": true, "everyone": ["status"], "sources": [{"name": "ci-runners", "cidr": "192.168.1.40/30", "allow": ["status", "control", "console", "usbip"]}]}`; eight sources at most |
| `POST /api/access/kick` | admin, `{"id": "usbip:51234"}`, an id from `GET /api/access` |
| `POST /api/access/key` | admin, `{"key": "<64 hex>"}` → `{"saved": true}` |
| `POST /api/lease` | `{"ttl_s": 3600, "note": "twister job 8812"}` reserves or renews the bay; `"ports": ["B3.2"]` one or more ports instead; `{"release": true}` ends it. Answers as `GET /api/access`, with `ports` on a node with a DATA board |

A claim waits 60 s for the press on BOOT. `ttl_s` goes from 10 to 86400 and is 3600 when left out; `note`
holds 39 characters. A reservation lives in the node's RAM: a restart ends it. While another address holds
the bay, control and console requests refuse with 423 and USB/IP answers only the holder; while it holds a
port, that port's control and its wires refuse with 423, but its USB/IP stays open to other machines. What
each one stops, in full: [Reserve a bay](../use/reserve-a-bay.md).

## Firmware update

`GET /api/update` answers `version`, `id` (`bay-node/bay_node`), `test_key`, `slot_kb`, `state` (`idle`,
`ready`, `receiving`, `rebooting`), `received`, `size`, `trial` (`left_s`, `need`, `up`, or `null`), `last`
(`result`, `to`, `from`, or `null`) and `error`. An update is two requests:

1. `POST /api/update/begin`, admin, `{"size": N, "sha256": "<64 hex>", "force": false}` →
   `{"ticket": "<16 hex>", "id": "bay-node/bay_node"}`. The ticket is good for one minute, from the same
   address. A reserved bay needs `"force": true`.
2. `POST /api/update?ticket=…` with `zephyr.signed.bin` as the body, written into slot 1 as it streams in →
   `{"state": "rebooting", "version": "…", "id": "…"}`, then a test boot.

An image built for another board or for the hub is refused once it has arrived. The trial, the rollback and
the steps from `bayctl`: [Update the firmware](../use/update-firmware.md).

## The admin signature

An admin request carries one header, `X-Bay-Auth: <nonce>:<mac>`. The nonce is 16 hex digits from `GET
/api/access/nonce`, good once and for 60 s. The mac is the HMAC-SHA256, under the node's 32-byte key, of
the nonce, the method, the path without its query string and the body as sent, joined by newlines, in 64
hex digits. `bayctl` signs this way:

```{literalinclude} ../../tools/bayctl.py
:language: python
:pyobject: sign
:caption: tools/bayctl.py
```

The key crosses the network once, in the answer to a claim. A signature that does not check answers 403
`bad or expired admin signature`. Where the key comes from and where `bayctl` reads it:
[Set up bayctl and usbip](../use/set-up-your-machine.md).

## Status codes and their texts

| Code | When | Texts |
|---|---|---|
| 200 | done | |
| 202 | a port's power-on is queued | |
| 400 | a bad body or value | `bad JSON`; `ms must be 1..10000`; `action must be on, off, cycle or cancel`; `"when": "available" goes with "action": "on"`; `this port has no such line`; `mode must be usbip or classic`; `the DUT is powered off`; `no BREAK on this board (no tx-gpios)`; `parity must be none, odd or even`; `enter must be cr, lf or crlf`; `this node serves one board: lease the bay (no "ports")`; `ttl_s must be 10..86400`; `ports: a list of sub-slots`; `ports: unknown sub-slot`; `key: 64 hex digits`; `baud 300..5000000, data bits 5..8, stop bits 1 or 2`; `size and sha256 (64 hex digits) needed`; a board target's or a camera setting's own text; for an upload, `SHA-256 does not match`, `fewer bytes than announced`, `image for power-hub/power_hub, this is bay-node/bay_node` |
| 403 | refused | `not allowed from this address`; `kicked by an admin: retry in a minute`; `bad or expired admin signature`; `admin only: sign the request with the key`; `admin only: unlock with the admin key`; `admin only: claim the device first`; `only its holder or an admin may release it`; `no such ticket: begin again` |
| 404 | nothing there | `no port 5 on this node`; `no camera on this bay`; `nobody pressed BOOT in time`; `no such claim from this address`; `no such connection`; any route that is not registered |
| 409 | not now | `this node serves 4 boards: say which ("port": 1..4, or /api/ports/<n>/...)`; `no room in the bay's budget: the bay draws <n> mW, <n> mW kept for a start, <n> mW in all (the hub's grant)`; `the port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone`; `no queued request on this port`; `already claimed: unlock with the admin key, or reset the node`; `the analyzer is busy: try again (<n>)`; `the running firmware is on trial: wait until it confirms itself`; `another update is on its way`; `reserved by <address> for <n> min more: force to update anyway`; `the co-processor is being loaded: try again in a few seconds` |
| 413 | too large | `body too large`; `size: larger than the update slot`; `size: larger than the coproc partition` |
| 423 | reserved by another address | `reserved by <address> (<note>), <n> min left`; `B3.2 reserved by <address> (<note>), <n> min left`; `B3.2 reserved by <address>`, to a lease over a held port; `B3.2 is reserved by another address`; `reserved: another address holds the lease` |
| 500 | the node failed | `action failed`; `response too large`; `rules applied, not saved`; `the UART refused it` |
| 503 | the port cannot act | `the port is off, or the DATA board is not set up (DUT_5V off?)` |

Read from the files under [Routes and the right each needs](#routes-and-the-right-each-needs) and from
[update.c](../../firmware/common/lib/update.c) and [coproc.c](../../firmware/bay-node/src/coproc.c). What a
text means for the board in the bay: [States and error messages](states-and-messages.md).

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
