# Power hub HTTP API

The hub answers plain HTTP/1.1 on port 80 at `rack.local`, or `rack-<id>.local` once it has a rack id: anyone
on the network may read, and every action is a request signed with the hub's admin key.

:::{status} simulated
The routes the rack's page and `bayctl` use have run against the simulated hub
(`firmware/power-hub/web/dev_server.py`), whose answers have the firmware's shape and some texts of their
own. No hub has been on a bench. See [What exists today](../plan/status.md#status-rack-page).
:::

| Route | Who | Body, and what comes back |
|---|---|---|
| `GET /api/status` | anyone | the whole state ([below](#api-status-field-by-field)) |
| `GET /api/events` | anyone | the recent events, newest first |
| `GET /metrics` | anyone | Prometheus text ([Network ports, names, metrics](network.md)) |
| `POST /api/row` | admin | `{"row": "B", "action": "on" \| "off" \| "cycle", "ms": 2000}` |
| `POST /api/pd` | admin | `{"pref": "20v" \| "epr"}` |
| `POST /api/enumerate` | admin | `{}` |
| `POST /api/node` | admin | `{"id": 35, "action": "identify" \| "reset" \| "bootloader" \| "power-on" \| "power-off" \| "power-cycle" \| "reboot"}` |
| `GET /api/access/nonce` | anyone | `{"nonce": "<hex>"}`, for one signed request |
| `POST /api/access/claim` | anyone | `{}` or `{"key": "<64 hex>"}`, then `{"ticket": "<hex>"}` |
| `POST /api/access/check` | admin | `{}`: 200 with the right key, else 403 |
| `GET /api/update` | anyone | the running firmware and the state of an update |
| `POST /api/update/begin`, `POST /api/update?ticket=…` | admin, then the ticket | an update over the network |

Read from `firmware/power-hub/src/web.c` and `firmware/common/web/update_http.c`.

## Answers and signatures

The answers are JSON, the page itself (`GET /`) excepted. The hub serves six clients at once. A body may not
exceed 128 bytes. A successful action answers 200 with the whole status document, as `GET /api/status`
would; a refusal is `{"error": "<text>"}` with its code ([below](#status-codes-and-their-texts)).

An admin request carries the header `X-Bay-Auth: <nonce>:<signature>`. The nonce comes from
`GET /api/access/nonce`, serves once and expires after 60 s. The signature is the HMAC-SHA256, in lower-case
hex, of the nonce, the method, the path and the body, joined by newlines, under the 32-byte admin key:

```text
<nonce>\nPOST\n/api/row\n{"row":"B","action":"cycle"}
```

The key itself crosses the network once, when the hub is claimed. The bay nodes sign the same way, with the
same code: [Bay node HTTP API](node-api.md). Who holds the key, and how to share one key between the hub and
the bays: [Access rules and security](../use/access.md).

## /api/status field by field

| Field | Holds |
|---|---|
| `hostname`, `ip`, `version`, `uptime_s` | the hub's name without `.local`, its address, its firmware, seconds since it started |
| `access` | `claimed` (it has an admin key), `claim_pending` (a claim waits for BOOT) |
| `pd` | the charger, below |
| `rows` | four objects, A to D, below |
| `budget` | what the rows may draw, below |
| `can` | the rack bus, below |
| `firmware` | as `GET /api/update`; present on a build with updates over the network |

`pd`:

| Field | Holds |
|---|---|
| `state` | `usb` (no charger: the controller runs from its console USB-C), `starting`, `spr`, `epr` |
| `pref` | what the hub asks for: `20v` or `epr` |
| `final` | the contract is final: 15 V or more, held 500 ms. The rows wait for it |
| `contract` | `{"mv", "ma", "epr", "pdo"}`, or `null` |
| `vbus_mv`, `rows_ma` | VBUS on the controller's ADC, the rows' summed current |
| `asked_mv`, `granted_ma` | the voltage asked for (0: none yet, the sink's own 9 V), the current the charger grants |
| `pg` | the sink's power good |
| `epr_refused` | 28 V was asked and VBUS did not follow: 20 V until the charger changes |
| `pdos` | the charger's offers: `index`, `type` (`fixed`, `pps`, `avs`), `mv`, `mv_min`, `ma`, `epr`, `w` for AVS; `selected: true` on the one in use, `refused: "above 28 V"` on those the hub never takes |
| `max_mw` | the largest offer |

`rows[]`:

| Field | Holds |
|---|---|
| `name` | `A` to `D` |
| `state` | `on`, `off`, `waiting`, `shed`, `cycling`, `absent`, or `fault` while the eFuse reports one ([what each means](states-and-messages.md#a-rows-states)) |
| `on`, `wanted`, `fault` | switched on now; wanted on (false once switched off by hand); a fault now |
| `faults` | faults since the hub started |
| `ma`, `mw` | the row's current, and its power at the contract's voltage; 0 while off |
| `nodes` | the bays on the row, below |

`rows[].nodes[]`:

| Field | Holds |
|---|---|
| `id`, `pos` | the node id as a number (C3 is 35), and the place, `"C3"` |
| `ip`, `mac`, `version` | `"0.0.0.0"` for a node without an address; its firmware |
| `state` | `attached`, `enumerated`, `usbip`, `off`, `fault`, `classic`, `service`, `lost`, `failed`, `incompatible` ([what each means](states-and-messages.md#a-bays-states-on-the-racks-page)) |
| `camera` | `none`, `ready`, or `active` while someone watches |
| `dut_mv`, `dut_ma` | the DATA lead's voltage and current |
| `grant_mw` | the last grant sent to the bay, in mW; `null` before the first |
| `waiting` | the bay's ports waiting for power |
| `seen_s` | seconds since the node was last heard |
| `name` | empty: the firmware sends `""` |

`budget`:

| Field | Holds |
|---|---|
| `contract_mw` | the contract's power |
| `limit_mw`, `limit_ma` | what the rows may draw: the contract's current, or the cap's if lower, less the margin |
| `used_mw`, `total_ma` | what the rows that are on draw |
| `margin_pct`, `cap_mw` | the margin; the cap, 0 for none |
| `shed`, `sheds`, `shed_order` | the rows shed now (`"C"`), how many sheds since the hub started, the order (`"DCBA"`) |

`can`:

| Field | Holds |
|---|---|
| `state` | `error-active`, `error-warning`, `error-passive`, `bus-off`, `stopped` |
| `bitrate` | 250000 |
| `nodes`, `lost` | bays on the bus, bays gone silent |
| `rx_fps` | frames received per second |
| `errors` | the controller's receive and transmit error counters now, not a total since the start |
| `tx_errors`, `bus_off` | send failures and bus-off events since the start |
| `enumerating`, `enumerated_s`, `enumerations` | numbering now; seconds since the last numbering (-1: never); how many |

Read from `firmware/power-hub/src/web.c` (`respond_status()`).

## Rows, the contract and the bays

`POST /api/row` takes `row` and `action`. `on` and `off` are saved across a restart of the hub. `cycle` keeps
the row off for `ms`, clamped to 100 to 60000, and 2000 ms without it; a row can only be cycled while it is
on. What the bays of a row go through: [Rows and the rack's page](../use/rack-page.md#switch-or-cycle-a-row).

With `pref`, `POST /api/pd` makes the hub renegotiate, and saves the choice. On a default build `epr` changes
nothing and the answer is still 200: 28 V is locked out by the build option `CONFIG_HUB_EPR_ALLOWED`, and only
the hub's shell says so ([Power hub shell](hub-shell.md#notes)). `pd.pref` then still reads `20v`.

`POST /api/enumerate`, with `{}`, numbers the rack bus again; the result is in the next status.

A command to one bay goes over the rack bus with `POST /api/node`. Its `id` is a number: the row's index (A is
0) times 16 plus the place, so B3 is 19 and C3 is 35. The answer comes back at once, before the bay has acted;
the bay's reply arrives as an event (`node C3: command 0x04 done`), or `no answer to command …` after three
tries 100 ms apart. A reserved bay refuses every action but `identify`. What each action does on a v1.0 bay:
[Rows and the rack's page](../use/rack-page.md#act-on-a-bay-through-the-hub).

## Events

`GET /api/events` gives up to 32 events, newest first, kept in RAM and lost when the hub restarts:

```json
[{"age_s":3,"kind":"row","text":"row B power cycle (2000 ms off)"}]
```

`age_s` counts from the event to the request. `kind` is `pd`, `row`, `fault`, `can`, `node` or `firmware`.
Every text: [States and error messages](states-and-messages.md#the-hubs-events).

## Claim the hub, check a key

`POST /api/access/claim` with `{}` asks the hub for a new key, with `{"key": "<64 hex>"}` offers the rack's
own. The answer is `{"state": "pending", "ticket": "<hex>", "remaining_s": 60}`, and the hub's CTL LED
flickers. Someone then has 60 s to press the hub's BOOT button, or to type `hub access claim` on its console.
The same address polls with `{"ticket": "<hex>"}`: `{"state": "pending", "remaining_s": <n>}` until the press,
then `{"state": "done", "key": "<64 hex>"}`.

A browser or a script that already holds the key checks it with a signed `POST /api/access/check`. A lost
key: [Recover a node or a hub](../use/recover.md).

## Firmware update

`GET /api/update` gives `version`, `id` (`power-hub/power_hub`), `test_key`, `slot_kb`, `state`,
`received` and `size`, `trial` while the new firmware is on trial, `last`, the result of the last update, and
`error`. A signed `POST /api/update/begin` with `{"size": <bytes>, "sha256": "<64 hex>"}` answers a ticket; the image,
`zephyr.signed.bin`, goes in `POST /api/update?ticket=<ticket>`. The hub then restarts into it on trial. The
protocol is the bay nodes' ([Bay node HTTP API](node-api.md)); how to run an update and what the trial checks:
[Update the firmware](../use/update-firmware.md).

## Status codes and their texts

| Code | Text | When |
|---|---|---|
| 200 | the status document | an action done. Also `/api/pd` with `epr` on a default build |
| 400 | `bad JSON` | the body is not JSON |
| 400 | `row and action needed`, `row must be A-D`, `action must be on, off or cycle` | `/api/row` |
| 400 | `row not fitted` | a row the hub does not have (B to D on the bench stand-ins) |
| 400 | `row is not on` | a `cycle` of a row that is off |
| 400 | `failed` | the row could not be switched |
| 400 | `pref must be epr or 20v` | `/api/pd` |
| 400 | `id (a node id) and action needed`, `unknown action` | `/api/node` |
| 400 | `rack bus busy` | the command could not be queued: try again |
| 400 | `key: 64 hex digits` | a claim offering a malformed key |
| 403 | `admin only: unlock with the hub's admin key` | unsigned, or signed with another key |
| 403 | `admin only: claim the hub first (its BOOT button)` | the hub has no key yet |
| 404 | `nobody pressed BOOT in time`, `no such claim from this address` | polling a claim |
| 409 | `already claimed: unlock with the admin key, or reset the hub` | a claim of a hub that has a key |
| 413 | `body too large` | a body over 128 bytes |

Read from `firmware/power-hub/src/web.c`. The refusals of an update are those of the bay nodes.

## Examples with curl

Read the state and the events:

```console
$ curl -s rack.local/api/status | python3 -m json.tool
$ curl -s rack.local/api/events
```

Cycle row B, signed with the key in `KEY` (64 hex digits) and `openssl`:

```console
$ NONCE=$(curl -s rack.local/api/access/nonce | python3 -c 'import json,sys; print(json.load(sys.stdin)["nonce"])')
$ BODY='{"row":"B","action":"cycle"}'
$ SIG=$(printf '%s\nPOST\n/api/row\n%s' "$NONCE" "$BODY" | openssl dgst -sha256 -mac HMAC -macopt hexkey:$KEY -r | cut -d' ' -f1)
$ curl -s -X POST rack.local/api/row -H "X-Bay-Auth: $NONCE:$SIG" -d "$BODY"
```

With `BODY='{"id":35,"action":"identify"}'`, and `/api/node` in place of `/api/row` in the last two lines,
the same commands blink bay C3's LED. Run against the simulated hub, the four lines answer with its status
document. `bayctl` signs for you: [Rows and the rack's page](../use/rack-page.md#with-bayctl).
