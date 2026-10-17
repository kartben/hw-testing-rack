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
   up beside the drawer foot, and is screwed into the
   drawer's rear port wall — in the left or the right DATA position, whichever
   is farther from the board's USB, so the two plugs never meet.  It never
   needs to be touched again (unless a board with its USB on the other side
   moves in: two M3 screws).
2. **The drag chain lies flat in the plenum** and bends in the horizontal
   plane (7 × 7 mm, R18, ≈ 160 mm).  Its fixed end is screwed to the tray,
   its moving end to the drawer foot.  Open the drawer 140 mm and the
   U-bend rolls forward 70 mm: the cable never drags, kinks or snags.
3. **Drawer → board: a short cable that belongs to the board.**  10–15 cm,
   USB-C on the drawer side, whatever the board needs on the other: C,
   micro-B or mini-B, right-angle at both ends: with the socket on the
   opposite side, the cable makes a small arch over the board's rear edge.
   The board's plate turns its debug USB towards the port wall (or, for a
   board too long for a plug behind it like the F746G-DISCO, towards the
   right wall: give that one a 20 cm cable) and has two hooks for the spare
   length.  Swapping boards = swapping plate + cable; the bay doesn't care.

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
the node's JST PH 6 (GND, 3V3 ref, TX, RX, RESET, BOOT) can follow the same
path through the chain (a 6-wire PH lead fits alongside the USB cable) to
the drawer's AUX slot, then flying leads to the board.

## Two-cable boards

i.MX EVKs and friends often want a debug cable *and* a power/OTG cable.  The
aluminium frame gave them **double-width bays** (two nodes, two drawers, so two
DATA ports, each with its own switched, current-limited, metered VBUS); the
panel frame has no double bay yet (see [mechanical.md](mechanical.md)).

## 24 V

* **Bay to bay:** JST PH 2-pin jumpers, 24 AWG, 120 mm, plugged into the
  node's left (IN) and right (OUT) connectors through the windows in both tray
  walls and the shared ladder, at the front of the plenum where the chain
  never goes.
* **Power box to row:** one JST PH feed per row, ≈ 1 m, into the first bay's
  left window.  (The power box is not designed yet: see [power.md](power.md).)
* **Cameras:** a JST-PH lead from the node above, down through the hole in
  the tray's bottom to the pod.
