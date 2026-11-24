# Power hub HTTP API

The power hub serves HTTP on TCP port 80, at `rack.local` or `rack-<id>.local`. Anyone may read its state.
Every action needs a request signed with the hub's admin key.

| Route | Who | Body, and what comes back |
|---|---|---|
| `GET /api/status` | anyone | the whole state ([field by field](#api-status-field-by-field)) |
| `GET /api/events` | anyone | the recent events, newest first |
| `GET /metrics` | anyone | Prometheus text ([Network ports and metrics](network.md)) |
| `POST /api/row` | admin | `{"row": "B", "action": "on" \| "off" \| "cycle", "ms": 2000}` |
| `POST /api/pd` | admin | `{"pref": "20v" \| "epr"}` |
| `POST /api/enumerate` | admin | `{}` |
| `POST /api/node` | admin | `{"id": 35, "action": "identify" \| "reset" \| "bootloader" \| "power-on" \| "power-off" \| "power-cycle" \| "reboot"}` |
| `GET /api/access/nonce` | anyone | `{"nonce": "<hex>"}`, for one signed request |
| `POST /api/access/claim` | anyone | `{}` or `{"key": "<64 hex>"}`, then `{"ticket": "<hex>"}` |
| `POST /api/access/check` | admin | `{}`: 200 with the right key, else 403 |
| `GET /api/update` | anyone | the running firmware and the state of an update |
| `POST /api/update/begin`, `POST /api/update?ticket=…` | admin, then the ticket | an update over the network |

Source: [firmware/power-hub/src/web.c](../../firmware/power-hub/src/web.c) and
[update_http.c](../../firmware/common/web/update_http.c).

## Answers and signatures

The answers are JSON. An action that succeeds returns 200 with the whole status document. A refusal is
`{"error": "<text>"}` ([below](#status-codes-and-their-texts)). A body may be at most 128 bytes.

An admin request carries the header `X-Bay-Auth: <nonce>:<signature>`, signed as for the
[bay nodes](node-api.md#the-admin-signature): the HMAC-SHA256, in lower-case hex, of the nonce, the method,
the path and the body, one per line.

```text
<nonce>\nPOST\n/api/row\n{"row":"B","action":"cycle"}
```

To use one key for the hub and the bays, see [Control who can use the rack](../use/access.md).

## /api/status, field by field

| Field | Holds |
|---|---|
| `hostname`, `ip`, `version`, `uptime_s` | the hub's name without `.local`, its address, its firmware, seconds since it started |
| `access` | `claimed` (it has an admin key), `claim_pending` (a claim waits for BOOT) |
| `pd` | the charger, below |
| `rows` | four objects, A to D, below |
| `budget` | what the rows may draw, below |
| `can` | the rack bus, below |
| `firmware` | as `GET /api/update`, on a build that takes updates over the network |

### pd

| Field | Holds |
|---|---|
| `state` | `usb` (no charger: the controller runs from its console USB-C), `starting`, `spr`, `epr` |
| `pref` | what the hub asks for: `20v` or `epr` |
| `final` | the contract is final: 15 V or more, held 500 ms. The rows wait for it |
| `contract` | `{"mv", "ma", "epr", "pdo"}`, or `null` |
| `vbus_mv`, `rows_ma` | VBUS on the controller's ADC; the rows' summed current |
| `asked_mv`, `granted_ma` | the voltage asked for (0: none yet, the sink's own 9 V); the current the charger grants |
| `pg` | the sink's power good |
| `epr_refused` | 28 V was asked and VBUS did not follow: 20 V until the charger changes |
| `pdos` | the charger's offers: `index`, `type` (`fixed`, `pps`, `avs`), `mv`, `mv_min`, `ma`, `epr`, `w` for AVS. `selected: true` on the one in use, `refused: "above 28 V"` on those the hub never takes |
| `max_mw` | the largest offer |

### rows

| Field | Holds |
|---|---|
| `name` | `A` to `D` |
| `state` | `on`, `off`, `waiting`, `shed`, `cycling`, `absent`, or `fault` while the eFuse reports one ([what each means](states-and-messages.md)) |
| `on`, `wanted`, `fault` | switched on now; wanted on (false once switched off by hand); a fault now |
| `faults` | faults since the hub started |
| `ma`, `mw` | the row's current, and its power at the contract's voltage. 0 while off |
| `nodes` | the bays on the row, below |

### rows[].nodes

| Field | Holds |
|---|---|
| `id`, `pos` | the node id as a number (C3 is 35), and the place, `"C3"` |
| `ip`, `mac`, `version` | the node's address (`"0.0.0.0"` until it has one), its MAC, its firmware |
| `state` | `attached`, `enumerated`, `usbip`, `off`, `fault`, `classic`, `service`, `lost`, `failed`, `incompatible` ([what each means](states-and-messages.md)) |
| `camera` | `none`, `ready`, or `active` while someone watches |
| `dut_mv`, `dut_ma` | the DATA lead's voltage and current |
| `grant_mw` | the last grant sent to the bay, in mW. `null` before the first |
| `waiting` | the bay's ports waiting for power |
| `seen_s` | seconds since the node was last heard |
| `name` | always `""` |

### budget

| Field | Holds |
|---|---|
| `contract_mw` | the contract's power |
| `limit_mw`, `limit_ma` | what the rows may draw: the contract's current, or the cap's if lower, less the margin |
| `used_mw`, `total_ma` | what the rows that are on draw |
| `margin_pct`, `cap_mw` | the margin; the cap, 0 for none |
| `shed`, `sheds`, `shed_order` | the rows shed now (`"C"`), how many sheds since the hub started, the order (`"DCBA"`) |

### can

| Field | Holds |
|---|---|
| `state` | `error-active`, `error-warning`, `error-passive`, `bus-off`, `stopped` |
| `bitrate` | 250000 |
| `nodes`, `lost` | bays on the bus; bays gone silent |
| `rx_fps` | frames received per second |
| `errors` | the controller's receive and transmit error counters now, not a total |
| `tx_errors`, `bus_off` | send failures and bus-off events since the start |
| `enumerating`, `enumerated_s`, `enumerations` | numbering now; seconds since the last numbering (-1: never); how many |

Source: `respond_status()` in [web.c](../../firmware/power-hub/src/web.c).

## Rows, the contract and the bays

- `POST /api/row`: the hub keeps `on` and `off` after a restart. `cycle` works only on a row that is on. It
  keeps the row off for `ms`, from 100 to 60000, 2000 by default
  ([The rack's page](../use/rack-page.md)).
- `POST /api/pd` with `20v` makes the hub renegotiate at 20 V. The hub stays at 20 V: `epr` changes nothing,
  and the answer is still 200.
- `POST /api/enumerate` renumbers the bays on the rack bus.
- `POST /api/node` sends a command to one bay over the rack bus. `id` is 16 times the row's index (A is 0),
  plus the column number: B3 is 19, C3 is 35. The answer comes back before the bay has acted. The bay's
  reply arrives later as an event, such as `node C3: command 0x04 done`. A reserved bay refuses every
  action except `identify`.

## Events

`GET /api/events` returns up to 32 events, newest first. A restart of the hub clears them.

```json
[{"age_s":3,"kind":"row","text":"row B power cycle (2000 ms off)"}]
```

`kind` is `pd`, `row`, `fault`, `can`, `node` or `firmware`. [States and messages](states-and-messages.md)
lists every text.

## Claim the hub and check a key

1. `POST /api/access/claim` with `{}` asks for a new key, or with `{"key": "<64 hex>"}` offers the rack's key.
   It returns `{"state": "pending", "ticket": "<hex>", "remaining_s": 60}`, and the CTL LED flickers.
2. Within 60 s, press the hub's BOOT button, or type `hub access claim` on its console.
3. From the same address, poll with `{"ticket": "<hex>"}` until the answer is
   `{"state": "done", "key": "<64 hex>"}`.

A signed `POST /api/access/check` tells you whether you hold the right key. If you have lost the key, see
[Recover a node or the hub](../use/recover.md).

## Firmware update

An update takes the same two requests as on a [bay node](node-api.md#firmware-update). The hub's `id` is
`power-hub/power_hub`. [Update the firmware](../use/update-firmware.md) says how to run an update.

## Status codes and their texts

| Code | Text | When |
|---|---|---|
| 200 | the status document | an action done |
| 400 | `bad JSON` | the body is not JSON |
| 400 | `row and action needed`, `row must be A-D`, `action must be on, off or cycle` | `/api/row` |
| 400 | `row not fitted` | a row the hub does not have |
| 400 | `row is not on` | a `cycle` of a row that is off |
| 400 | `failed` | the row could not be switched |
| 400 | `pref must be epr or 20v` | `/api/pd` |
| 400 | `id (a node id) and action needed`, `unknown action` | `/api/node` |
| 400 | `rack bus busy` | the command could not be queued: try again |
| 400 | `key: 64 hex digits` | a claim with a malformed key |
| 403 | `admin only: unlock with the hub's admin key` | unsigned, or signed with another key |
| 403 | `admin only: claim the hub first (its BOOT button)` | the hub has no key yet |
| 404 | `nobody pressed BOOT in time`, `no such claim from this address` | polling a claim |
| 409 | `already claimed: unlock with the admin key, or reset the hub` | a claim of a hub that has a key |
| 413 | `body too large` | a body over 128 bytes |

Source: [web.c](../../firmware/power-hub/src/web.c).

## Examples with curl

Read the state and the events:

```console
$ curl -s rack.local/api/status | python3 -m json.tool
$ curl -s rack.local/api/events
```

To cycle row B, sign the request with `openssl`. Put the admin key (64 hex digits) in `KEY` first:

```console
$ NONCE=$(curl -s rack.local/api/access/nonce | python3 -c 'import json,sys; print(json.load(sys.stdin)["nonce"])')
$ BODY='{"row":"B","action":"cycle"}'
$ SIG=$(printf '%s\nPOST\n/api/row\n%s' "$NONCE" "$BODY" | openssl dgst -sha256 -mac HMAC -macopt hexkey:$KEY -r | cut -d' ' -f1)
$ curl -s -X POST rack.local/api/row -H "X-Bay-Auth: $NONCE:$SIG" -d "$BODY"
```

To blink bay C3's LED, use `BODY='{"id":35,"action":"identify"}'` and `/api/node` in the last two lines.
`bayctl` signs for you ([bayctl](bayctl.md#hub)).
