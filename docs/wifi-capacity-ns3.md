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
- **Channel choice repairs most of it.**  With the rack on 11 and that traffic on 6, 8 flashes get
  339 kB/s each again.  Some is lost to the DUTs leaking into the adjacent channel from a few cm.
- **TX power (8–20 dBm) and AP distance (1–3 m) change nothing** at this range: every link is at the
  top MCS.  The 11b beacons cost 2–3 % of airtime.  A larger ESP32 block-ack window gains at most 7 %,
  because the node's TCP window is the limit.
- **Wi-Fi stops being enough** when CI flashes more than about 8 nodes at once per channel, or when
  the rack's channel is shared with busy foreign traffic.

## The model

ns-3.49 (2026-10-06), one C++ scenario (`rack-wifi.cc`), one run per point of the sweep, 20 s
measured after 5 s of association and warm-up, 3–4 seeds per point (up to 10 in the channel pass),
307 runs in all, 9 of them aborted by ns-3 (below, "Simulator artefacts").

| Part | Model | From |
|---|---|---|
| Stations | the bay nodes (8, or 16 with rows C and D) and the power hub: 802.11n 1×1 HT20, MCS 0–7, long guard interval, no power save | `firmware/README.md` › Wi-Fi in the rack |
| AP | one, 1–3 m in front of the rack's face, channel 6, 20 MHz, 20 dBm | same |
| PHY | Yans, one channel.  The channel-choice pass uses the spectrum PHY, where a transmission leaks into the next channel through the 802.11 transmit mask | `channel` sweep |
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
- **The DUTs' own Wi-Fi does less harm on the other channel than on the rack's.**  Moved to 11 with
  the rack, it leaves 256 kB/s per node at 8 flashes; left on 6, next door, 339.
- ns-3 aborted 9 of the 72 runs itself, all with the rack and the neighbour on different channels:
  the spectrum PHY's internal "Invalid WifiPhy state RX".  Every point keeps 3–10 runs.

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

## Not modelled

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
    the 134 runs with 8 bays.
  - It depends on the seed: a change in timing, such as OFDM beacons, makes it go away.
  - `rack-wifi.cc` counts these stations (`dead`).  `summarize.py` leaves such runs out, and the
    tables say how many it dropped.
- **Spectrum PHY aborts.**  With BSSs on different channels, ns-3.49's spectrum PHY sometimes stops
  the run on an internal assertion ("Invalid WifiPhy state RX").  That was 9 of the 72 channel-choice
  runs.  `run.sh` lets the other runs go on, and the sweep adds seeds where points thinned out.

## Recommendations

1. **A dedicated AP for the rack, on its own channel: 6 or 11, never 1** (the hub PLL's harmonic sits
   at 2.400 GHz).  Pick the one where no neighbour is heard.  Keep the DUTs' own Wi-Fi tests off the
   rack's channel: rack on 6, the DUTs' lab AP on 11, or the reverse.  Of every setting studied, this
   one matters most.  The busy-channel case halves the capacity, and moving the rack to the other
   channel takes 8 flashes from 155 back to 339 kB/s each.
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
