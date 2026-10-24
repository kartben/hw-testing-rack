# The rack's Wi-Fi and the DUTs' Bluetooth: a simulation

How much do the nodes, the hub and the AP disturb a BLE link between two DUTs
in the rack, and which settings help?  This is a **BabbleSim model**: read it
as a comparison between settings, not as a measurement.  The scripts are in
[`tools/bsim-wifi-coex`](../tools/bsim-wifi-coex/README.md); the raw results
in its `results/`.  How much the rack's Wi-Fi itself carries is another study
([wifi-capacity-ns3.md](wifi-capacity-ns3.md), ns-3).

## In short

- **Host channel classification is the lever that works.** Zephyr's open
  link layer has no automatic channel assessment: it uses only the channel map
  the host gives it (`LE Set Host Channel Classification`,
  `bt_le_set_chan_map()`).  With the ~10 data channels under the rack's Wi-Fi
  channel marked bad, the link went back to its no-Wi-Fi throughput in every
  case, the stress case included.
- **Without it, a busy rack costs throughput, not the link.** Over 60 s of
  continuous notifications, no case dropped the connection (no supervision
  timeout) and no connection failed to be set up.  Throughput fell by up to
  9 % with the rack idle, 10–13 % while the DUTs' own node was being flashed,
  and 16–30 % under stress.  BLE loses only 1–2 % of its packets, but each loss
  ends the connection event, and the rest of the interval with it.
- **The node's TX power counts; the Wi-Fi channel hardly does.**
  - Idle, the node's power is the whole effect: 92 % of the throughput at
    20 dBm, 95 % at 11, 97–98 % at 8, 100 % at 2.
  - Under stress, 2 dBm brings 71–77 % up to 82–84 %.
  - Channels 1, 6 and 11 gave the same data throughput within the run-to-run
    noise (±3 points).  Each one covers the same quarter of the 37 data
    channels.
  - The channel matters for advertising only: 11 is the one that covers none
    of the three advertising channels.
- **The AP matters as much as the nodes.** A flash is mostly the AP's
  downlink: with the AP 1 m away the flashed bay's DUTs kept 79 % of their
  throughput, against 88 % at 2 or 3 m, whatever the nodes' power.
- **The number of nodes does not.** Going from 1 to 16 nodes on the air
  changed nothing measurable.  The DUTs' own node (10 cm away) and the AP set
  the level.
- **Discovery is robust.** Scan-to-connected stayed at 109–117 ms on average
  (worst 492 ms under stress on channel 1, against 415 ms without Wi-Fi), with
  11b beacons or not.

## Setup

- **The DUTs:** two `nrf52_bsim` boards running Zephyr's own host and
  controller (the open link layer), at 0 dBm, 10 cm apart in B2's drawer.
  - A central and a peripheral with default connection parameters: a 30–50 ms
    interval and a 4 s supervision timeout.
  - 1M PHY, data length and MTU raised.
  - **Flow:** the peripheral notifies 200-byte values as fast as the link
    takes them, for 60 s.
  - **Discovery:** advertising every 100 ms, passive scanning (60 ms interval,
    30 ms window), connect, disconnect after 100 ms, again (170–230
    connections a run).
- **The rack's Wi-Fi:** one BSS, modelled by BabbleSim's `WLAN_actmod`.
  - That is a single two-state (active/idle) occupancy process; the AP, the hub
    and the nodes are its ports, each with a share of the transmissions, so
    two stations never overlap.
  - A second, periodic process models the AP's beacons: every 102.4 ms,
    300 bytes, at 1 Mbps (11b rates on) or 6 Mbps (off).
  - 802.11g at 54 Mbps, HT20.
- **The positions:** from `config/rack.yaml`, columns 165.8 mm apart and rows
  165 mm.
  - The DUTs are in B2, and their own node's antenna is 10 cm from them.
  - The other nodes sit at their bays (19–48 cm), the hub under row A (38 cm),
    the AP 2 m away.
  - Up to 8 nodes in rows A and B, up to 16 with C and D.
- **The paths:** free space at 2.45 GHz, 40.2 dB at 1 m and 20 dB a decade,
  plus 5 dB for small PCB antennas and the enclosure.
  - DUT to DUT: 25 dB.
  - Own node: 25 dB, so −5 dBm at the DUT from a node at 20 dBm.
  - AP: 51 dB.
  - The AP transmits at 20 dBm; the nodes and the hub at the swept power.
- **The receiver:** BabbleSim's `BLE_simple` modem: the SNR from the
  interferers' spectrum (an 802.11 mask with shoulders out to ±30 MHz) through
  the BLE receive filter, then the bit error rate.
- **The traffic profiles**, as the BSS's share of the air, measured in the
  runs:

| profile | what | Wi-Fi on the air |
|---|---|---|
| idle | mDNS, ARP, polls from every node (54 Mbps), and the AP's beacons | 3.4 % with 11b beacons, 1.4 % without |
| flash | the DUTs' own node being flashed: AP downlink (80 %), its ACKs | 8.3 % |
| stress | 4 flashes and 2 cameras streaming at once | 36.7 % |

The ns-3 study puts 8 simultaneous flashes at about 70 % of the air: twice
this stress case, which a busy CI day can reach.

Each point is one 60 s run with one seed.  Three seeds of the stress case at
11 dBm moved its throughput by ±3 points: smaller differences are noise.

## Results

Throughput is the end-to-end measure: the peripheral's notifications the
central received, per second connected, against 158 kB/s without Wi-Fi.
"Lost" is the share of link-layer packets on the data channels that did not
arrive intact.  It is 1.2 % without Wi-Fi: the central cuts the last
packet of each connection event short.

### Data flow, by node TX power and Wi-Fi channel

**Idle** (16 nodes, 11b beacons):

| node TX power | channel 1 | channel 6 | channel 11 |
|---|---|---|---|
| 20 dBm | 92 % (1.9 % lost) | 91 % (1.9 %) | 93 % (1.8 %) |
| 11 dBm | 95 % (1.8 %) | 95 % (1.8 %) | 96 % (1.7 %) |
| 8 dBm | 98 % (1.6 %) | 97 % (1.6 %) | 98 % (1.6 %) |
| 5 dBm | 99 % (1.5 %) | 99 % (1.4 %) | 99 % (1.4 %) |
| 2 dBm | 100 % (1.3 %) | 100 % (1.3 %) | 100 % (1.3 %) |

**Flash** of the DUTs' own node (8 nodes):

| node TX power | channel 1 | channel 6 | channel 11 |
|---|---|---|---|
| 20 dBm | 88 % (1.9 % lost) | 87 % (2.0 %) | 88 % (1.9 %) |
| 11 dBm | 89 % (1.9 %) | 88 % (1.9 %) | 90 % (1.8 %) |
| 8 dBm | 90 % (1.8 %) | 89 % (2.0 %) | 90 % (1.7 %) |
| 5 dBm | 90 % (1.9 %) | 91 % (2.0 %) | 91 % (1.8 %) |
| 2 dBm | 93 % (1.9 %) | 94 % (1.9 %) | 93 % (1.9 %) |

**Stress** (8 nodes):

| node TX power | channel 1 | channel 6 | channel 11 |
|---|---|---|---|
| 20 dBm | 73 % (2.0 % lost) | 70 % (2.3 %) | 73 % (2.0 %) |
| 11 dBm | 75 % (2.1 %) | 71 % (2.2 %) | 77 % (2.1 %) |
| 8 dBm | 75 % (2.1 %) | 73 % (2.4 %) | 78 % (2.0 %) |
| 5 dBm | 76 % (2.2 %) | 75 % (2.6 %) | 79 % (2.0 %) |
| 2 dBm | 82 % (2.6 %) | 82 % (2.5 %) | 84 % (2.4 %) |

With seeds 2 and 3, the stress case at 11 dBm gave 74–76 % on channel 1,
74–75 % on 6 and 75 % on 11.  The channels are equal within the noise.

### The rest of the rack

| case (11 dBm, channel 6) | throughput |
|---|---|
| stress, 1 / 4 / 8 / 16 nodes on the air | 71 / 71 / 71 / 71 % |
| flash, AP 1 m / 2 m / 3 m away | 79 / 88 / 88 % |
| stress, AP 1 m / 2 m / 3 m away | 71 / 71 / 71 % |
| idle (16 nodes), 11b beacons / OFDM beacons, channel 6 | 95 / 95 % |
| idle (16 nodes), 11b beacons / OFDM beacons, channel 11 | 96 / 96 % |

### Host channel classification

The central marks bad the data channels within 11 MHz of the Wi-Fi
channel's centre (`-argstest wifi_ch=<n>`); the peripheral follows through
the link layer's channel map update.  8 nodes at 11 dBm:

| case | channel | without | with |
|---|---|---|---|
| flash | 1 / 6 / 11 | 89 / 88 / 90 % | 100 / 100 / 100 % |
| stress | 1 / 6 / 11 | 75 / 71 / 77 % | 100 / 100 / 100 % |

With it, losses fell back to the no-Wi-Fi 1.2 %.  The interference sits on
the overlapping channels: the 802.11 shoulders the model keeps beyond them
cost nothing here.

### Discovery

Scan to connected: average, 90th percentile and worst of the 170–230
connections a run.  Without Wi-Fi: 109 / 112 / 415 ms.

- Idle and flash, at 11 or 2 dBm, on any channel, with 11b beacons or not:
  109 / 112 / 415 ms, as without Wi-Fi.
- Stress at 11 dBm:
  - channel 1: 117 / 113 / 492 ms;
  - channels 6 and 11: 111 / 112 / 415 ms;
  - the beacons' rate makes no difference.
- Stress at 2 dBm: 109–110 / 112 / 415 ms on all three channels.
- With host channel classification: 109 / 112 / 415 ms.

Channel 1 covers advertising channel 37 (2402 MHz) and channel 6 reaches
38 (2426 MHz).  11 leaves all three clear, which is why it is the slightly
better choice.  No connection failed to be set up.

## What it changes in our recommendations

Today's ([firmware/README.md › Wi-Fi in the rack](../firmware/README.md#wi-fi-in-the-rack)):
11 dBm, HT20, channel 6 or 11.  In the light of the model:

- **8 dBm by default: yes.** It brings idle from 95 to 97–98 % and does not
  hurt the stress case.  It costs the rack's own Wi-Fi nothing either: every
  link stays at the top rate (the ns-3 study), and on the bench the status page
  loaded no slower at 8 dBm.  The real gain is likely larger than modelled (see
  the limits).
- **Channel 11 by default: yes, weakly.** For data, 6 and 11 are equal.  11
  keeps the three advertising channels clear, which shows only in discovery
  under stress.  1 stays out for the USB hub's PLL harmonic.
- **A dedicated rack AP with 11b off: the AP's placement matters more than
  11b.**
  - Keep it 2–3 m from the drawers, not 1 m: the flash case lost 9 more points
    at 1 m.
  - A dedicated AP also keeps other people's traffic off the rack's channel,
    which none of these profiles includes.
  - 11b off cuts the beacons' airtime by 2 points of the air, with no effect
    measured here.  It's still worth doing, as multicast also goes at the
    basic rate.
- **Radio-quiet mode: worth building, with both halves.**
  - Dropping the node to 2 dBm recovers everything when the rack is idle.
  - Under stress the AP's and other nodes' traffic still costs 16 %.
  - So holding the bay's traffic (its other DUTs' USB/IP, a flash in progress)
    is the part that matters there.
- **For BLE tests that need the full link, the host's channel classification
  wins outright.**
  - It belongs to the DUT's firmware, not the rack's.
  - The rack can make it easy by publishing its Wi-Fi channel, for instance in
    the hardware map `bayctl hwmap` writes, so a test can call
    `bt_le_set_chan_map()` before it measures.

## Limits of the model

- **No blocking.** `BLE_simple` computes interference from spectral overlap
  only, with no receiver blocking, intermodulation or saturation.  A node at
  20 dBm 10 cm from a DUT (−5 dBm at its antenna) would desensitize a real
  receiver on every channel, so the model flatters high node power.  That
  argues for lower power, not against it.
- **Wi-Fi from a profile, not from traffic.**
  - The activity is BabbleSim's 802.11g occupancy model at 54 Mbps, set to a
    given share of the air.
  - The nodes' real HT20 frames at MCS 7 are shorter, and real traffic comes
    in bursts.
- **One free-space geometry.**
  - No reflections from the rack's metal or the room, no antenna patterns.
  - One pair of DUTs, in B2, 10 cm from their node.
- **One BLE setup.** Zephyr's open link layer only: a vendor controller with
  its own channel assessment would behave differently.  Default connection
  parameters, 1M PHY, a peripheral that sends as fast as it can.
- **802.15.4 is not simulated.**

## Rerunning it

See [`tools/bsim-wifi-coex/README.md`](../tools/bsim-wifi-coex/README.md):
the BabbleSim set-up runs in the Zephyr CI image (x86-64), and the sweep in
about an hour on 32 threads.  `summarize.py` prints the tables above from the
CSVs.
