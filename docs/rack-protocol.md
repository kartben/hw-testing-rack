# Rack bus protocol

The messages the power hub (the rack controller) and the bay nodes exchange on
the rack's CAN bus.  The wiring, the star topology and the POS token's
circuit are the hardware contract in [can.md](can.md); this page is the
firmware contract on top of it.  Both firmwares use one header for it,
[`firmware/common/include/hwtr/rack_proto.h`](../firmware/common/include/hwtr/rack_proto.h).

> **Status: protocol version 1**, implemented in
> [`firmware/common/lib`](../firmware/common/lib/) (`rack_proto.c`, the hub's
> `rack_hub.c`, the node's `rack_node.c`) and tested on a simulated rack
> on native_sim ([`firmware/common/tests/rack_bus`](../firmware/common/tests/rack_bus/)):
> enumeration, a node rebooting, a late node, a dead node, a lost node, a
> lost HELLO, a retried command, a row switched off.  Not yet on hardware.

## Basics

| | |
|---|---|
| Bus | classic CAN 2.0A (11-bit identifiers), 250 kbit/s, 8-byte frames (the ESP32-S3's TWAI has no CAN FD) |
| Node id | `row × 16 + position`: rows A–D are 0–3, positions 1–15 from the hub outwards.  C3 → `0x23`.  `0x00` is the hub |
| Identifier | `function << 7 \| node id`, as CANopen does: a function's frames from every node share a range, lower ranges win arbitration |
| Byte order | little-endian; voltages in mV, currents in mA (`0xFFFF`: no reading) |
| Version | every frame that announces a node carries the protocol version (1); a hub ignores the STATUS frames of a node that speaks a newer major version and shows it as "incompatible" |

## Frames

| Identifier | Function | From → to | When |
|---|---|---|---|
| `0x000` | **BCAST**: rack-wide command | hub → all | on event |
| `0x080 + id` | **ALERT**: DUT fault | node → hub | on event |
| `0x100 + id` | **CMD**: command to one node | hub → node | on request |
| `0x180 + id` | **REPLY**: answer to a CMD | node → hub | after each CMD |
| `0x200` | **RACK**: the hub's state (contract, rows) | hub → all | every 1 s |
| `0x280 + id` | **STATUS**: node state, the heartbeat | node → hub | every 1 s |
| `0x300 + id` | **INFO**: IPv4, firmware version | node → hub | every 10 s and on change |
| `0x700`–`0x77F` | **ENUM_REQ**: a node without an address (low 7 bits from its MAC) | node → hub | enumeration |
| `0x780 + id` | **HELLO**: address taken | node → hub | enumeration |
| `0x7F0` | **ENUM_ASSIGN**: here is your address | hub → node | enumeration |

### BCAST `0x000`

| Byte | |
|---|---|
| 0 | opcode: `0x01` ADDR_RESET (every node forgets its address and lowers POS_OUT), `0x02` ENUM_POLL (a node with POS_IN high and no address sends ENUM_REQ now) |

### ENUM_REQ `0x700 + h`, ENUM_ASSIGN `0x7F0`, HELLO `0x780 + id`

`h` = `(MAC[3] ^ MAC[4] ^ MAC[5] ^ (MAC[2] >> 1)) & 0x7F`.  Only one node at
a time should be asking, but two nodes that reboot together in two rows
would otherwise send the same identifier with different data: CAN cannot
arbitrate that (endless bit errors).  With identifiers from the MAC the
lower one wins and the other retries.

| Byte | ENUM_REQ | ENUM_ASSIGN | HELLO |
|---|---|---|---|
| 0–5 | the node's MAC | the MAC it is for | the node's MAC |
| 6 | protocol version | node id | protocol version |
| 7 | why: 0 POS rose, 1 at boot, 2 poll, 3 retry | protocol version | 0 |

### STATUS `0x280 + id` (every second: the heartbeat)

| Byte | |
|---|---|
| 0 | flags: bit 0 DUT powered, 1 DUT fault (current limit or latched off), 2 SERVICE, 3 classic mode, 4 USB device enumerated, 5 USB/IP client attached, 6 network up, 7 a console client is connected |
| 1 | counter, +1 per STATUS (a reset shows as a jump) |
| 2–3 | DUT bus voltage, mV |
| 4–5 | DUT current, mA |
| 6 | flags: bit 0 the bay is reserved (access lease), 1 the bay has a camera, 2 someone is watching it (a stream or a snapshot under way); older nodes send 0, a hub ignores bits it does not know |
| 7 | 0 |

### INFO `0x300 + id`

| Byte | |
|---|---|
| 0–3 | IPv4 address, network order (0.0.0.0 without one) |
| 4 | protocol version |
| 5–7 | firmware version: major, minor, patch |

### ALERT `0x080 + id`

| Byte | |
|---|---|
| 0 | code: `0x01` DUT in current limit, `0x02` DUT switched off by a fault |
| 1–2 | DUT current, mA |

### CMD `0x100 + id` and REPLY `0x180 + id`

| Byte | CMD | REPLY |
|---|---|---|
| 0 | opcode | opcode |
| 1 | sequence number | the same |
| 2… | arguments | result: 0 done, 1 unknown opcode, 2 refused, 3 failed |
| 3–4 | | errno, when it failed |

| Opcode | | Arguments |
|---|---|---|
| `0x01` | DUT power | byte 2: 0 off, 1 on, 2 cycle; bytes 3–4: off time of a cycle, ms (0: the node's default) |
| `0x02` | DUT reset pulse | bytes 2–3: ms (0: default) |
| `0x03` | DUT into its bootloader | |
| `0x04` | identify: blink the node's LED | byte 2: seconds (0: stop) |
| `0x05` | reboot the node | |
| `0x06` | send INFO now | |

A node answers every CMD it receives, within 100 ms; the hub retries twice
without an answer, with the same sequence number (a node does not repeat an
action for a repeated sequence number).

### RACK `0x200` (every second, from the hub)

| Byte | |
|---|---|
| 0 | flags: bit 0 PD contract in place, 1 EPR, 2 rows shed for power |
| 1–2 | contract voltage, mV |
| 3–4 | contract current, mA |
| 5 | rows on (bit 0 = A) |
| 6 | rows in fault |
| 7 | counter |

## Enumeration

The POS token runs along each row (can.md › Addressing): a node sees POS_IN
high only once every node before it has an address, so only one node at a
time can be asking.

```
hub                                   node A1                  node A2
 │ rows off, POS low                   │                        │
 │ row A on (eFuse), wait 2 s          │ boots, POS_OUT low     │ boots, POS_OUT low
 │ POS_A high ───────────────────────► │ POS_IN high            │
 │ ◄──────────── ENUM_REQ (MAC, why 0) │                        │
 │ ENUM_ASSIGN (MAC, 0x01) ──────────► │                        │
 │ ◄─────────── HELLO 0x781 (MAC)      │ POS_OUT high ────────► │ POS_IN high
 │ ◄────────────────────────────────────────── ENUM_REQ (MAC)   │
 │ ENUM_ASSIGN (MAC, 0x02) ───────────────────────────────────► │
 │ ◄─────────────────────────────────────────── HELLO 0x782     │ POS_OUT high
 │ 200 ms, no ENUM_REQ: row A has 2 nodes; next row
```

**Node.**  It holds POS_OUT low from reset until it has an address.  It
sends ENUM_REQ when POS_IN rises (debounced, 2 ms), at boot when POS_IN is
already high, and on ENUM_POLL, but only while POS_IN is high and it has no
address; it repeats it every second until it is answered.  On an
ENUM_ASSIGN for its MAC it takes the id, sends HELLO from it, then raises
POS_OUT.  It keeps the address until ADDR_RESET or a reboot (not in flash:
the position is the truth).

**Hub.**  Rows are enumerated one after the other, with every POS low but
the row's own; POS goes up on every enumerated row at the end.  It waits
2 s after turning a row on (the nodes' boot), then 200 ms per position for
an ENUM_REQ, then sends ENUM_POLL and waits 200 ms more before it declares
the row done, and 50 ms for the HELLO after an ENUM_ASSIGN (three tries).
POS stays low on rows that are off: no current into an unpowered node.

**Re-enumeration.**  An ENUM_REQ outside an enumeration means a node
rebooted, or one was plugged in: the hub then lowers every POS, sends
ADDR_RESET and enumerates every powered row again.  Ids depend on positions
only, so every node gets its id back; the whole rack takes well under a
second.  The same happens when a row is turned on.

## Errors and timing

| Case | What happens |
|---|---|
| A node stops sending STATUS for 3.5 s | the hub marks it lost (power cut, crash, cable); it comes back through ENUM_REQ |
| No HELLO after three ENUM_ASSIGNs | the hub marks the position failed and stops that row: the nodes after it cannot get POS (as with a dead node, can.md) |
| A node without CAN firmware | it never asks and holds POS_OUT low: the row stops there |
| Two frames with the same identifier | per-node ranges have one owner each; two ENUM_REQs differ by their MAC-derived identifier (a 1-in-128 clash only if two nodes ask at the very same moment, and they retry with a MAC-derived jitter) |
| A STATUS from an address the hub did not give | the hub rebooted while the nodes kept theirs: it enumerates again |
| Bus off | the TWAI recovers by itself (128 × 11 recessive bits); both sides count it |
| CMD without REPLY | two retries 100 ms apart, then "no answer" to whoever asked |

Bus load: 16 nodes × (STATUS every second + INFO every 10 s) plus the RACK
frame is ≈ 20 frames per second, about 1 % of the bus at 250 kbit/s.
