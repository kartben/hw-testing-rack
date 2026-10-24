# One rack's Wi-Fi in ns-3: capacity, latency, limits

**Status (2026-10-24): a simulation study, nothing changed in the design or the firmware.**  A
reviewer holds that Wi-Fi in a rack is a bad idea; the user keeps it for now and asked for the risk
in numbers: airtime, latency, retransmissions and USB/IP goodput, and when one channel stops being
enough.  How the rack's Wi-Fi disturbs the DUTs' BLE radios is another study (BabbleSim, the firmware
session).  Wired options for later: W5500 Ethernet, 10BASE-T1S.

The scenario, the sweep, the run script and the result CSVs are in
[`tools/ns3-wifi-capacity/`](../tools/ns3-wifi-capacity/README.md).

## In short

- **One channel carries 8 simultaneous USB/IP flashes at full speed.**  Each node gets its 362 kB/s,
  airtime is at 70 %, and control requests stay under 15 ms at p95.  Between 8 and 12 the channel
  saturates at about 3.2 MB/s (26 Mbit/s) of USB/IP in all.  At 12 a node gets about 268 kB/s, at
  16 about 166 kB/s, and control latency is 10–15× higher (p95 125–200 ms).
- **What fills the channel is contention, not bytes.**  Every flashing node keeps TCP ACKs, URB
  replies and console bytes queued, so 17 stations collide.  MAC retransmissions reach one per
  delivered MPDU at 12+ nodes.  TCP never sees them.
- **Cameras are cheap**: about 4 % of airtime each.  Sixteen streams alone fit at 69 %, and 1–3 of
  them fit beside 8 flashes.  Only on top of a saturated channel do they collapse (16 flashes and 16
  cameras: 2.4 frames/s, 66 kB/s per flash).
- **The real risk is foreign traffic on the rack's channel.**  4 DUTs with their own Wi-Fi plus a
  neighbour, 18 Mbit/s in all, take half the airtime.  Then 8 flashes get 160 kB/s each and control
  requests take 275 ms at p95.
- **Channel choice repairs part of it, if the in-bay DUTs stay on the rack's channel.**  A neighbour's
  BSS belongs on the other channel.  A DUT 3 cm from its node, on the other channel, makes that node's
  control requests take seconds (near-field pass).  On the rack's channel they take turns, and 8
  flashes get 258 kB/s each.  Receiver blocking, not modelled, can only make the neighbouring channel
  worse.
- **TX power (8–20 dBm) and AP distance (1–3 m) change nothing** at this range: every link is at the
  top MCS.  The 11b beacons cost 2–3 % of airtime.  A larger ESP32 block-ack window gains at most 7 %,
  because the node's TCP window is the limit.
- **Per DUT** (up to 32 DUTs with 8 bays, 64 with 16, on DATA ×4 boards):
  - 8 bays: all 32 DUTs can flash at once at ≈ 90 kB/s each.  There the nodes' USB full-speed buses
    are the limit, not Wi-Fi.
  - 16 bays: about 32 DUTs at that speed.  All 64 at once get ≈ 43 kB/s each.
  - Details: "The two rack sizes, per DUT".
- **Wi-Fi stops being enough** when CI flashes more than about 8 nodes at once per channel, or when
  the rack's channel is shared with busy foreign traffic.

## The model

ns-3.49 (2026-10-06), one C++ scenario (`rack-wifi.cc`), one run per point of the sweep, 20 s
measured after 5 s of association and warm-up, 3–4 seeds per point (up to 10 in the channel pass),
605 runs in all, 19 of them aborted by ns-3 (below, "Simulator artefacts").

| Part | Model | From |
|---|---|---|
| Stations | the bay nodes (8, or 16 with rows C and D) and the power hub: 802.11n 1×1 HT20, MCS 0–7, long guard interval, no power save | `firmware/README.md` › Wi-Fi in the rack |
| AP | one, 1–3 m in front of the rack's face, channel 6, 20 MHz, 20 dBm | same |
| PHY | Yans, one channel.  The channel-choice passes use the spectrum PHY, where a transmission leaks into the next channel through the 802.11 transmit mask | `channel`, `channel_near` sweeps |
| Near zone | in the near-field pass: free space below 1 m plus 5 dB (BabbleSim's model), the DUTs 3 cm from their nodes; the calibrated law from 1 m on | `--nearLoss`, `--dutCm` |
| Placement | 4 columns 165.8 mm apart, rows 165 mm apart (`config/rack.yaml`); every node hears every other: no hidden station | rack geometry |
| Propagation | log-distance, exponent 3, 46.7 dB at 1 m (free space at 2.437 GHz) + 13 dB, so that the AP gives −49 dBm at 2 m, as the bench XIAO measured | bench RSSI |
| Node TX power | 11 dBm (default), 8 and 20 dBm in the sweep | `CONFIG_HWTR_NET_TX_POWER_DBM` |
| Aggregation | A-MPDU of at most 6 MPDUs both ways: the ESP32's block-ack window (`ESP32_WIFI_TX_BA_WIN` and `_RX_BA_WIN`, default 6, at most 32); 16 and 32 in one sweep | Zephyr's `drivers/wifi/esp32/Kconfig.esp32` |
| Rate control | ns-3's ideal (SNR-driven) manager: Minstrel-HT left some stations of a 16-node BSS unreachable even idle, a simulator artefact | below, "Simulator artefacts" |
| Beacons, broadcasts | 102.4 ms beacons at 1 Mbit/s DSSS (11b on, the default) or 6 Mbit/s OFDM (11b off); broadcasts at the same rate | the sweep |
| TCP | NewReno, 1448-byte segments.  Node: 21 KB send buffer (Zephyr's `NET_BUF_TX_COUNT` note), 12 KB receive.  PC: 256 KB | `firmware/bay-node/Kconfig` |
| Lab server | a wired PC behind the AP (1 Gbit/s) | |

Traffic per bay:

| Flow | Model |
|---|---|
| USB/IP, flashing (CI) | PC → node, 4 KB URBs at 362 kB/s, what one node's USB full-speed side feeds at best (255–362 kB/s measured); the URB replies the other way (48 B each).  With a DATA ×4 the four DUTs share that one USB bus: the per-node cap stays |
| USB/IP, reads | the same, node → PC (`ci_up` sweep) |
| DUT console | node → PC, 64 B every 32 ms (2 kB/s) |
| Camera (MJPEG) | node → PC, 5 frames/s of 30–60 KB; a frame is skipped while the previous one is still queued |
| Status page / API | the PC opens a TCP connection, sends 200 B, reads 600 B, closes; every 1 s on average (exponential) per node.  Its latency is the "HTTP" metric: connect to last byte |
| Prometheus | `/metrics` every 15 s per node and the hub, 150 B request, 2 KB answer |
| mDNS | a query to the subnet every 10 s, each node and the hub answer with a 300 B broadcast after 20–120 ms; the AP repeats each broadcast at the beacon rate |
| Ping | from the PC to every node, every 500 ms (the "ping" metric) |
| Harsh case | 4 DUTs with their own Wi-Fi on the same channel, 2 Mbit/s each (half each way) to their own lab AP at 2 m, at 20 dBm; and a neighbour's BSS through a wall, 12 m away (≈ −72 dBm at the rack: heard, deferred to), 2 stations at 5 Mbit/s each |

Metrics:
- **Airtime:** the share of time a silent station at the rack's centre finds the channel busy
  (receiving or carrier sense).
- **Latency:** the HTTP transaction's p50 / p95 / p99, and the ping's.
- **Retransmissions:** 802.11 MPDU retransmissions over delivered MPDUs (`WifiTxStatsHelper`), and
  TCP retransmissions over TCP data segments.
- **USB/IP goodput:** per node, over the 362 kB/s it offers; its worst node.
- **Saturation:** where the nodes stop getting what they offer.

## Results

Means over the seeds (3–4 per point, fewer where a run was left out: `results/summary.md` says how
many).  Defaults unless stated: nodes at 11 dBm, AP at 2 m, 11b beacons, A-MPDU of 6.

### Idle (scenario 1)

| Bays | Beacons | Airtime % | Ping p95 ms | HTTP p95 ms |
|---|---|---|---|---|
| 8 | 1 Mbit/s DSSS | 2.6 | 0.31 | 0.9 |
| 8 | 6 Mbit/s OFDM | 1.1 | 0.31 | 0.8 |
| 16 | 1 Mbit/s DSSS | 3.6 | 0.31 | 1.1 |
| 16 | 6 Mbit/s OFDM | 1.9 | 0.31 | 1.0 |

The background (polls, scrapes, mDNS, pings) costs about 1 % of airtime per 8 nodes; the AP's 11b
beacons cost 1.5 % more.  ns-3's beacons are short (about 160 bytes on air).  A real AP's beacon,
with its HT, WMM, RSN and vendor elements, is 250–400 bytes: at 1 Mbit/s that is 2.2–3.4 ms every
102.4 ms, 2–3 % of airtime per AP heard, against 0.4–0.6 % at 6 Mbit/s.

### Flashing (scenario 2): how many at once

| Active nodes | Airtime % | USB/IP kB/s per node (worst) | Rack total MB/s | Ping p95 ms | HTTP p50 / p95 / p99 ms | MAC retx % |
|---|---|---|---|---|---|---|
| 1 | 11 | 362 (362) | 0.36 | 1.0 | 0.8 / 2 / 2 | 3 |
| 2 | 20 | 362 (362) | 0.72 | 1.3 | 0.8 / 2 / 4 | 7 |
| 4 | 36 | 362 (362) | 1.45 | 2.5 | 1.1 / 4 / 5 | 33 |
| 6 | 53 | 362 (362) | 2.17 | 3.1 | 2.1 / 6 / 12 | 38 |
| 8 | 70 | 362 (362) | 2.90 | 7.8 | 6.1 / 15 / 29 | 65 |
| 12 | 81 | 268 (259) | 3.21 | 68 | 87 / 125 / 148 | 100 |
| 16 | 79 | 166 (158) | 2.65 | 104 | 124 / 199 / 271 | 97 |

- **Up to 8 simultaneous flashes, every node gets what its USB side feeds (362 kB/s)**, at 70 % of
  airtime, with control requests under 15 ms at p95.
- **The channel saturates between 8 and 12**, at about 3.2 MB/s (26 Mbit/s) of USB/IP in all.  At 12,
  each node gets about 268 kB/s, at the bottom of the measured 255–362 kB/s.  At 16 it gets 166 kB/s.
  Control latency is then 10–15× higher (p95 125–200 ms, p99 up to 270 ms).
- Each flash costs about 9 % of airtime.  The cost is contention more than bytes: 17 stations each
  keep TCP ACKs, URB replies and console bytes queued.  So MAC retransmissions reach one per delivered
  MPDU at 12+ nodes.  TCP sees none: the MAC retries hide every loss.

Reads (node → PC, `ci_up`) behave the same up to 8 nodes.  Beyond that the nodes get a little more,
298 kB/s at 12 and 210 kB/s at 16 (3.4–3.6 MB/s in all), because the stations' own A-MPDUs carry
the data.  Latency is worse (HTTP p95 199 ms at 12, 268 ms at 16).

### Cameras (scenario 3)

| Flashes | Cameras | Airtime % | USB/IP kB/s per node | Camera fps (of 5) | Frames skipped % | HTTP p95 ms |
|---|---|---|---|---|---|---|
| 0 | 1 | 7 | – | 5.0 | 0 | 2 |
| 0 | 4 | 19 | – | 5.0 | 0 | 7 |
| 0 | 8 | 34 | – | 5.0 | 0 | 16 |
| 0 | 16 | 69 | – | 5.0 | 0 | 57 |
| 4 | 2 | 43 | 362 | 5.0 | 0 | 8 |
| 4 | 8 | 68 | 362 | 5.0 | 0 | 35 |
| 8 | 1 | 74 | 362 | 5.0 | 0 | 31 |
| 8 | 3 | 81 | 362 | 5.0 | 0 | 57 |
| 8 | 8 | 87 | 270 | 5.0 | 1 | 134 |
| 16 | 1 | 79 | 155 | 4.6 | 8 | 216 |
| 16 | 16 | 84 | 66 | 2.4 | 51 | 490 |

- **A camera stream is cheap**: about 225 kB/s in large frames, which aggregate well.  It costs about
  4 % of airtime, under half a flash.  Sixteen streams alone fit, at 69 %.
- **What hurts is cameras on top of a saturated channel.**  With 8 flashes, 1–3 streams keep everything
  at full rate.  With 8 streams the flashes drop to 270 kB/s and control requests to 134 ms at p95.
  With 16 flashes and 16 streams nothing works: 66 kB/s per flash, 2.4 frames/s, half a second of
  latency.

### A busy channel (scenario 4)

Four DUTs with their own Wi-Fi on the rack's channel (2 Mbit/s each, half each way, to their own
lab AP) and a neighbour's BSS heard through a wall (2 stations at 5 Mbit/s): 18 Mbit/s of foreign
traffic.  It is constant-rate UDP, which does not back off.

| Flashes | Airtime % | USB/IP kB/s per node (clean channel) | HTTP p95 / p99 ms (clean) | Foreign traffic delivered |
|---|---|---|---|---|
| 1 | 59 | 362 (362) | 7 / 14 (2 / 2) | 8 + 10 Mbit/s, all of it |
| 4 | 82 | 362 (362) | 83 / 136 (4 / 5) | all |
| 8 | 83 | 160 (362) | 275 / 408 (15 / 29) | all |
| 16 | 82 | 40 (166) | 829 / 1117 (199 / 271) | all |

- **Foreign traffic on the same channel halves the rack's capacity.**  The 18 Mbit/s of DUT and
  neighbour traffic, in small UDP frames that aggregate poorly, take about half of the airtime by
  themselves (59 % with a single flash).
- Then 4 flashes still run at full rate, but control latency is already 20× (p95 83 ms).  8 flashes
  get 160 kB/s each, below the node's floor, and 16 get 40 kB/s with second-long control requests.
- 11b or OFDM beacons hardly matter here (the same rows with 6 Mbit/s beacons: 362 / 163 / 41 kB/s).

### Channel choice in the busy case

The neighbour's BSS stays on channel 6.  The rack moves to 11, and the DUTs' lab AP either stays on
6 or moves with the rack.
- These runs use ns-3's spectrum PHY.  With it, a transmission leaks into the next channel through
  the 802.11 transmit mask (Yans isolates channels perfectly).
- The all-on-6 reference was run again on the spectrum PHY.  It matches the Yans runs within a few
  per cent.

| Flashes | All on 6 | Rack on 11; DUTs and neighbour on 6 | Rack and DUTs on 11; neighbour on 6 |
|---|---|---|---|
| 1 | 59 % airtime, HTTP p95 8 ms | 33 %, 3 ms | 36 %, 4 ms |
| 4 | 362 kB/s, p95 80 ms | 362 kB/s, 6 ms | 362 kB/s, 11 ms |
| 8 | 155 kB/s, p95 282 ms | **339 kB/s, 107 ms** | 256 kB/s, 148 ms |
| 16 | 37 kB/s, p95 916 ms | 107 kB/s, 311 ms | 74 kB/s, 456 ms |

- **Moving the rack off the neighbour's channel gives most of the capacity back.**  At 8 flashes a
  node gets 339 kB/s instead of 155; a clean channel gives 362.  At 4 flashes, control latency is
  back to the clean channel's (p95 6 ms instead of 80).
- **Not all of it, because the DUTs sit a few centimetres from the nodes.**  Four DUT radios at
  20 dBm leak into the adjacent channel, about −28 to −40 dB at 25 MHz from the transmit mask.  With a
  single flash, the rack's channel is still 33 % busy (11 % on a clean channel).
- In this first pass, the DUTs' own Wi-Fi seemed to do less harm on the other channel than on the
  rack's (339 against 256 kB/s at 8 flashes).  **The near-field pass below reverses that for DUTs in
  the bays.**
- ns-3 aborted 9 of the 72 runs itself, all with the rack and the neighbour on different channels:
  the spectrum PHY's internal "Invalid WifiPhy state RX".  Every point keeps 3–10 runs.

### Channel choice with the DUTs 3 cm from their nodes (near field)

The first pass underrated the coupling inside the rack.
- Its log-distance law was calibrated on the AP's link and stops at 1 m: 59.7 dB at any shorter
  distance.
- Its DUTs sat 9.4 cm from their nodes.
- In the rack the DUT boards sit 25–32 mm over the node's antenna (architecture.md).

This pass (`channel_near`, `--nearLoss=1 --dutCm=3`) changes two things:
- **The loss below 1 m** is free space between small antennas plus 5 dB, the BabbleSim study's model:
  about 15 dB from a DUT 3 cm away and 30 dB between neighbouring nodes.  From 1 m on, the calibrated
  law is kept.
- **The DUTs** sit 3 cm from their nodes.

The same three layouts, on the spectrum PHY:

| Flashes | All on 6 | Rack on 11; DUTs (3 cm) and neighbour on 6 | Rack and DUTs on 11; neighbour on 6 |
|---|---|---|---|
| 1 | 362 kB/s, HTTP p95 7 ms | 357 kB/s, **606 ms** | 362 kB/s, 4 ms |
| 4 | 363 kB/s, p95 87 ms | 307 kB/s (worst node 233), **1.2 s** | 362 kB/s, 12 ms |
| 8 | 156 kB/s, p95 283 ms | 161 kB/s (worst node 25), **3.0 s** | **258 kB/s, 150 ms** |
| 16 | 39 kB/s, p95 909 ms | 118 kB/s (one node 0), **3.1 s** | 76 kB/s, 442 ms |

- **A DUT in the bay on the other channel breaks its node.**  At 3 cm the DUT's transmit mask alone
  puts −23 to −35 dBm into the node's channel, against the AP's −49 dBm.  So every one of the node's
  receptions that overlaps a DUT frame fails, and nothing makes them take turns, since neither hears
  the other.  Control requests then take seconds, TCP retransmits, and some nodes starve.
- **On the rack's channel they share by carrier sense**, as architecture.md says: at 8 flashes
  258 kB/s per node and 150 ms at p95, with every node served.
- **Moving the rack away from the neighbour's BSS still helps.**  The neighbour is 12 m away, and its
  leakage is negligible.
- Scenario 2 with the near-zone loss (`ci_near`) gives the same results as the main sweep (8 flashes:
  362 kB/s, p95 17 ms; 12: 270; 16: 168).  Stronger coupling between nodes changes nothing on one
  channel: they already heard each other.
- **Receiver blocking is still not modelled.**  A DUT 3 cm away puts about +5 dBm on the node's
  antenna, where a receiver's front end compresses.  ns-3 counts only the transmit mask's leakage.
  The real effect of a neighbouring channel is at least as bad as this table.
- ns-3 aborted 10 of these 64 runs (the same assertion).  The middle column keeps 2–5 runs per point.

### TX power and AP distance

At 8 flashes, node TX power (8, 11, 20 dBm) and AP distance (1, 2, 3 m) change nothing: 362 kB/s
everywhere, airtime 67–71 %, HTTP p95 12–19 ms.  Every link sits at the top MCS with 25+ dB of
margin, and every node hears every other: the power does not move the contention.  At 16 flashes
one cell stands out: 8–11 dBm with the AP at 1 m gives 215 kB/s per node instead of 160.  That is
ns-3's SINR-based reception surviving some collisions where the AP is nearer some nodes than others.
It is a sensitivity of the model, not something to design on.  So TX power is for the DUTs' sake (the
BabbleSim study), not for capacity: 8 dBm costs nothing here.

### Beacons under load, and the block-ack window

| Flashes | Setting | USB/IP kB/s per node | HTTP p95 ms | Airtime % |
|---|---|---|---|---|
| 8 | 11b beacons / OFDM beacons | 362 / 362 | 15 / 13 | 70 / 69 |
| 16 | 11b beacons / OFDM beacons | 165 / 170 | 202 / 183 | 79 / 79 |
| 12 | A-MPDU 6 / 16 / 32 MPDUs | 267 / 278 / 278 | 126 / 116 / 116 | 81 / 84 / 84 |
| 16 | A-MPDU 6 / 16 / 32 MPDUs | 165 / 177 / 177 | 202 / 214 / 214 | 79 / 83 / 83 |

- **11b off** saves the 1.5–2 % of airtime the beacons take in the model, 2–3 % per AP with
  real-size beacons, and speeds up every broadcast (mDNS).  It is worth having, but it is not what
  decides the capacity.
- **A larger block-ack window** (`ESP32_WIFI_TX_BA_WIN` / `_RX_BA_WIN` 16 or 32 instead of 6) gives
  nothing below saturation and 4–7 % at 12–16 flashes.  16 and 32 are identical: the node's 12 KB TCP
  receive window already holds a flow to about 8 segments in flight.  The extra Wi-Fi RX buffers
  are not worth their RAM.

### The two rack sizes, per DUT

**With DATA ×4 boards, a rack holds up to 32 DUTs (8 bays) or up to 64 DUTs (16 bays).**

The `racks` sweep runs both sizes at the recommended setting:
- 8 dBm, channel 11, 11b off, the AP at 2 m, A-MPDU 6, and the near-zone loss;
- every bay's node and the hub associated, with their background traffic (polls, scrapes, mDNS,
  consoles), whether they flash or not;
- the busy channel: 4 DUTs with their own Wi-Fi on the rack's channel, 3 cm from their nodes, plus a
  neighbour's BSS on channel 6.

222 runs, none aborted, none with a dead station: 4 seeds per point at 8 bays, 5 at 16, and 6 for the
busy channel.  Each cell reads: USB/IP kB/s per flashing node (worst node) · HTTP p95 ms · airtime.

**8 bays** (8 nodes + hub, up to 32 DUTs):

| Flashing nodes | 0 | 1 | 2 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| CI | – · 1 · 1 % | 362 · 2 · 10 % | 362 · 2 · 18 % | 362 · 4 · 35 % | 362 · 5 · 52 % | 362 · 14 · 68 % |
| CI + 2 cameras | | 362 · 3 · 17 % | 362 · 5 · 25 % | 362 · 9 · 43 % | 362 · 18 · 59 % | 362 · 39 · 76 % |
| CI + 8 cameras (1 per bay) | | 362 · 12 · 40 % | 362 · 16 · 49 % | 362 · 36 · 66 % | 362 · 64 · 83 % | 280 (268) · 130 · 86 % |
| Busy channel | | 362 · 4 · 35 % | 362 · 5 · 44 % | 362 · 9 · 61 % | 362 · 67 · 79 % | 267 (258) · 137 · 81 % |

The cameras keep 5 frames/s in every 8-bay case (4.9 at worst).

**16 bays** (16 nodes + hub, up to 64 DUTs):

| Flashing nodes | 0 | 1 | 2 | 4 | 8 | 12 | 16 |
|---|---|---|---|---|---|---|---|
| CI | – · 1 · 2 % | 362 · 2 · 11 % | 362 · 2 · 19 % | 362 · 3 · 36 % | 362 · 15 · 69 % | 274 (261) · 122 · 81 % | 172 (163) · 187 · 79 % |
| CI + 2 cameras | | 362 · 5 · 18 % | 362 · 6 · 26 % | 362 · 9 · 44 % | 362 · 41 · 77 % | 237 (222) · 142 · 81 % | 148 (138) · 217 · 80 % |
| CI + 16 cameras (1 per bay) | | 362 · 68 · 78 % | 347 · 142 · 88 % | 174 · 208 · 88 % | 121 · 275 · 87 % | 90 · 409 · 86 % | 70 · 486 · 85 % |
| Busy channel | | 362 · 4 · 36 % | 362 · 5 · 44 % | 362 · 11 · 62 % | 253 (243) · 142 · 80 % | 133 (126) · 259 · 79 % | 79 (74) · 421 · 78 % |

With 16 cameras, the camera rate falls with the flashes: 5 frames/s up to 2 flashes, 4.6 at 4, 3.7 at
8, and 2.5 at 16 (49 % of frames skipped).

These runs match the earlier ones (11 dBm, channel 6, 11b on) within the 2–3 % that 11b off gives
back:

| Flashing nodes | Earlier | Now |
|---|---|---|
| 8 | 362 kB/s at 70 % airtime | 362 kB/s at 68 % |
| 12 | 268 kB/s | 274 kB/s |
| 16 | 166 kB/s | 172 kB/s |
| 8, busy channel (near field) | 258 kB/s | 267 kB/s |

**Per DUT.**  A node's 4 DUTs share its USB full-speed bus, about 362 kB/s.  Four simultaneous flashes
on one node get about 90 kB/s each.  Flash times below are for a 1 MB image.

| | 8 bays (32 DUTs) | 16 bays (64 DUTs) |
|---|---|---|
| At full speed (362 kB/s, ≈ 3 s) | 8 DUTs, one per node | 8 DUTs, one per node |
| At ≈ 90 kB/s (≈ 11 s), 4 per node | **all 32**: the nodes' USB is the limit, not Wi-Fi | 32 (8 nodes) |
| Everything at once | 32 at ≈ 90 kB/s; ≈ 67–70 kB/s with a camera per bay or the busy channel | 48 at ≈ 68 kB/s (12 nodes); all 64 at ≈ 43 kB/s (≈ 24 s), ≈ 37 with 2 cameras, ≈ 20 on the busy channel (≈ 50 s) |
| At ≥ 90 kB/s (a node's 4-DUT share) | all 32 | about 32 (36 at best: 12 nodes × 3) |

Control requests stay under 15 ms at p95 up to 8 flashing nodes, whatever the rack size.  Beyond 8,
they take 120–190 ms.

## Not modelled

- **Receiver blocking.**  A DUT 3 cm away puts about +5 dBm on its node's antenna.  ns-3 counts only
  the transmit mask's leakage into the node's channel, not the front end compressing.  So the
  neighbouring-channel results are a best case.

- **Near-field coupling.**  The nodes are 16.6 cm apart and their DUTs a few cm from them: the
  antennas, the DUT boards, the USB cables and the printed rack are not in the model.  Propagation is
  a log-distance law calibrated on one RSSI.
- **The ESP32's own MAC.**  Its rate control, its EDCA queue sizes, its block-ack timeouts and its
  retry limits are ns-3's defaults; only the block-ack window is the ESP32's.  The rack's results
  depend most on contention, which ns-3 models well, and least on rate control (every link is at the
  top MCS).
- **Zephyr's TCP.**  Its window and buffer limits are approximated by socket buffers; its own
  congestion behaviour is NewReno's here.
- **USB/IP's request pattern.**  Flashing is a steady 362 kB/s stream, not Linux's URB pipeline with
  its round trips; a real flash adds latency-bound phases (erase, verify) that use less airtime.
- **Other 2.4 GHz users**: Bluetooth (the DUTs' BLE, the BabbleSim study), microwave ovens, the USB
  hub PLL's harmonic at 2.400 GHz (channel 1, avoided).
- **The AP itself**: a real AP's CPU, queues and airtime fairness; here it serves every station
  equally through EDCA.

## Simulator artefacts

- **Minstrel-HT** (ns-3's rate control) left 4–5 of 16 stations unreachable even in the idle
  scenario, with 30+ dB of SNR.  The ideal manager does not; it is the right model for short static
  links at the top MCS.
- **Dead stations.**  In some runs, one or two stations send every MPDU into failure for the whole
  run, while they and the AP both hold the association.  Their HTTP probes all time out.
  - It happens only with 16 bays (17 stations), idle included: 29 of those 107 runs, against none of
    the 134 runs with 8 bays.  None of the 129 runs with 16 bays in the rack-size pass (11b off,
    near-zone loss) had one.
  - It depends on the seed: a change in timing, such as OFDM beacons, makes it go away.
  - `rack-wifi.cc` counts these stations (`dead`).  `summarize.py` leaves such runs out, and the
    tables say how many it dropped.
- **Spectrum PHY aborts.**  With BSSs on different channels, ns-3.49's spectrum PHY sometimes stops
  the run on an internal assertion ("Invalid WifiPhy state RX").  That was 9 of the 72 channel-choice
  runs, and 10 of the 64 near-field ones.  `run.sh` lets the other runs go on, and the sweeps add
  seeds where points thinned out.

## Recommendations

1. **A dedicated AP for the rack, on 6 or 11, never 1** (the hub PLL's harmonic sits at 2.400 GHz).
   - Pick the channel where no neighbour is heard.  Moving the rack off a neighbour's BSS is worth
     doing.
   - **The DUTs' Wi-Fi inside the bays goes on the rack's channel**, as architecture.md says.  At 3 cm
     a neighbouring channel leaks more into the node than the AP's signal, so neither side defers and
     the node's receptions fail: control requests take seconds (near-field pass).  On the same channel
     they take turns.
   - **DUT networks away from the rack** (the lab's AP for the DUTs, other benches) go on the other
     channel.
2. **Turn 11b off on that AP** (basic rates from 6 Mbit/s).  That is 2–3 % of airtime back, and
   faster broadcasts.  Cheap, but secondary.
3. **At most 8 simultaneous USB/IP flashes per channel.**  A rack-wide limit in bayctl's pre-script, a
   lease or a semaphore, as the drawer's probe lease.  Below it every session runs at the speed its
   USB bus allows and control stays under 20 ms at p95.  With 16 bays, either queue the ninth flash
   or give rows C–D a second AP on the other channel: two channels of 8 each run at full rate.
4. **Cameras on demand, as they are**: up to 3 streams while 8 flashes run, all 16 when little else does.
5. **TX power: 11 dBm, or 8, for the DUTs' sake**: capacity does not depend on it within 1–3 m (the
   BabbleSim study weighs the DUT side).
6. **Leave the ESP32's block-ack window at 6.**  16 or 32 gains at most 7 %, at saturation only, for
   RAM.
7. **When to wire.**  If CI regularly needs more than 8 simultaneous flashes per rack, or the room's
   2.4 GHz band is busy, the nodes need a cable.
   - Per-node Ethernet (W5500, about 10–15 Mbit/s each over SPI) carries every node's 362 kB/s at
     once.
   - 10BASE-T1S shares 10 Mbit/s per segment, about 1 MB/s of TCP.  That is about 3 full-speed flashes
     per segment, fewer than one Wi-Fi channel carries.  It suits control and consoles, not 16
     simultaneous flashes on one segment.
