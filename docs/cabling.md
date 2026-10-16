# Cabling

Three rules drove the design: **no loose cable spans between bays**, **a
board stays connected while you work on it**, and **each cable is as short
as it can be without ever being taut**.

## The DUT cable path (per bay)

```
bay node (plenum)                              drawer
 ┌──────────┐  30 cm USB-C male→panel female   ┌────────────────────────────┐
 │ DUT port ├──────┐                           │ [DATA]◀── 10–15 cm ──▶ board │
 └──────────┘      │  ┌─ drag chain 7×7 R18 ─┐ │   ▲ panel-mount female      │
                   └─▶│ fixed end   moving end├─┼─▶ up through the foot slot  │
                      └──────────────────────┘ └────────────────────────────┘
```

1. **Node → drawer: one off-the-shelf extension.**  A 30 cm USB-C male →
   panel-mount USB-C female (M3 ears) plugs into the node's DUT receptacle,
   runs ~6 cm in the plenum to the chain's fixed end, through the drag chain,
   up through the deck slot beside the drawer foot, and is screwed into the
   drawer's rear port wall.  It never needs to be touched again.
2. **The drag chain lies flat in the plenum** and bends in the horizontal
   plane (7 × 7 mm, R18, ≈ 160 mm).  Its fixed end is screwed to the carrier
   base, its moving end to the drawer foot.  Open the drawer 140 mm and the
   U-bend rolls forward 70 mm: the cable never drags, kinks or snags.
3. **Drawer → board: a short cable that belongs to the board.**  10–15 cm,
   USB-C on the drawer side, whatever the board needs on the other: C,
   micro-B or mini-B (right-angle versions keep it tidy).  The board's plate
   orients its debug USB towards the DATA port and has two hooks for the
   spare length.  Swapping boards = swapping plate + cable; the bay doesn't care.

**USB-C or micro-B in every bay?**  Yes — the bay's port is always USB-C and
the short cable adapts.  Recommended kit: a few C↔C (Adafruit right-angle
100 mm), C↔micro-B (Delock 15 cm) and one C↔mini-B for older ST-LINKs.

**Classic mode, no cable juggling.**  Plug a laptop into the bay's front
**PC** port and the node's mux hands the board's USB data to the laptop
automatically (VBUS from the laptop is only sensed, never used: the board
stays powered — and current-monitored — by the shelf).  Unplug and it's back
on USB/IP.  Or simply unplug the short cable from the drawer port and use
your own.

**AUX.**  For boards without a USB serial bridge or to drive RESET/BOOT:
the node's JST-SH 6 (GND, 3V3 ref, TX, RX, RESET, BOOT) can follow the same
path through the chain (a 6-wire SH lead fits alongside the USB cable) to
the drawer's AUX slot, then flying leads to the board.

## Two-cable boards

i.MX EVKs and friends often want a debug cable *and* a power/OTG cable.  They
live in **double-width bays**, which have two nodes and two drawers — so two
DATA ports, each with its own switched, current-limited, metered VBUS.

## 24 V

* **Bay to bay:** JST VH 2-pin jumpers, 0.75 mm², 120 mm, plugged into the
  node's left (IN) and right (OUT) connectors through notches in the carrier
  side walls, at the front of the plenum where the chain never goes.
* **Hub to row:** one VH feed per row from the power hub (base, rear) up the
  rear-left post, held in the extrusion slot with printed `slot_cable_clip`s,
  into the first bay's left notch.
* **Cameras:** a JST-PH lead from the node above, down through the hole in
  the carrier's bottom plate to the pod.

## Mains

IEC C13 cord → rear inlet panel.  Inside the base: inlet → PSU AC terminals
under the printed mains cover; PSU DC → hub terminal (1.5 mm², ferrules); PE
bonded to the PSU and the frame.  See [power.md](power.md).
