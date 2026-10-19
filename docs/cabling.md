# Cabling

Three rules drove the design: **no loose cable spans between bays**, **a
board stays connected while you work on it**, and **each cable is as short
as it can be without ever being taut**.

## The DUT cable path (per bay)

```
bay node (plenum)                                 drawer
 ┌──────────┐  DATA lead: JST PH 8-pin, ~40 cm    ┌────────────────────────────────────┐
 │ DATA J7  ├──────┐                              │ [DATA]◀── short cable ──▶ board    │
 └──────────┘      │  ┌─ drag chain 7×7 R18 ─┐    │   ▲ port board on the drawer floor │
                   └─▶│ fixed end   moving end├───┼─▶ up through the cable window      │
                      └──────────────────────┘    └────────────────────────────────────┘
```

1. **Node → drawer: a small port board and an 8-wire lead.**  The drawer's
   DATA port is our own 40 × 17 mm board ([electronics/data-port](../electronics/data-port/design.py)):
   a USB-C receptacle (a source: Rp 22k on CC1/CC2, USBLC6 ESD at the
   receptacle) screwed components up to the floor behind the port wall
   (2 × PT 2.6×8, one each end), its mouth behind a U in the wall: the
   board's short cable plugs into it.  A JST PH 8-pin lead (VBUS, GND, D−, D+, GND, then
   the node's I²C and INT, which the port board leaves open, for a later DATA ×4 board) plugs
   into the node's **DATA** header (J7, side entry on the node's right edge,
   facing the chain; the node's only DUT port), runs ~3 cm in the plenum to the
   chain's fixed end, through the drag chain, out of its moving end
   (forwards, then a U-turn in front of it, between the chain's runs, low
   over the tray floor) and up through the cable window into the port
   board's rear edge.  It never needs to be touched again.  (A sled or fixed
   bay has no chain: the lead runs from J7 back along the plenum, right of
   the node, under the sled, and up through the port block's window into its
   PH, its slack coiled in the plenum.)  It is the rack's
   camera's PH 8 lead type (pin n ↔ pin 9−n, both plugs the same face up: the
   port board's pinout is J7's mirrored), with 8 pins so a 6-pin row cable
   (VRACK, up to 28 V) cannot go in; twist D−/D+ (pins 3-4) by hand.  (A
   USB-C coupler with a 90° extension came first: two off-the-shelf parts
   whose sizes vary by seller, and a stiff cable to bend in the window.)
2. **The drag chain lies flat in the plenum** and bends in the horizontal
   plane: Olimex DRAG-CHAIN-7X7, 7 × 7 mm inside, 13.5 × 10.2 mm outside,
   R18, ≈ 180 mm with its two end pieces.  Its fixed end is screwed to the
   tray's anchor, its moving end to the drawer foot.  Open the drawer 140 mm
   and the U-bend rolls forward 70 mm: the lead never drags, kinks or snags.
   **Lay the lead in, don't thread it:** its PH plugs (12 mm wide) do not
   pass a 7 × 7 channel.  Open the links (their bars snap off on both
   sides), lay the lead in from the fixed end's mouth to the moving end's,
   with ~3 cm out of the fixed end for the node and the port board's end out
   of the moving end, then snap the bars back.
3. **Drawer → board: a short cable that belongs to the board.**  USB-C on
   the drawer side, whatever the board needs on the other (C, micro-B or
   mini-B).  Two layouts, set by the board's plate:
   * **a small board** (Pico, ESP32 DevKitC, UNO R4: `orient: side`) turns
     its USB towards the right wall: a plain **straight** 15–20 cm cable
     leaves the DATA port forwards, bends once (≥ 10 mm radius) and
     lies flat on the plate into the board's side;
   * **a long board** (Nucleo, nRF DK, FRDM) faces its USB to the port wall,
     17–23 mm away, too close for a straight plug: the cable leaves the
     socket through a **right-angle** USB-C and makes a small arch over the
     board's rear edge.  At the board, a USB-C port takes a right-angle plug
     too (a 15 cm C ↔ C bent at both ends); a micro-B or mini-B port takes a
     **90° adapter** (male → female, its female facing up) with the cable's
     straight plug standing on it (20 cm, 25 cm for the F746G-DISCO, whose
     mini-B faces the right wall).  A right-angle micro-B / mini-B plug is
     not reversible and sellers name "up" and "down" either way; the
     adapters come in up / down / left / right sets, so keep whichever one
     faces up.  The arch stays under ~105 mm above the row (a camera pod
     hangs down to 120): loop any spare length flat on the plate's two hooks,
     beside the board, not over it (the camera looks at it).
   Swapping boards = swapping plate + cable; the bay doesn't care.

**USB-C or micro-B in every bay?**  Yes — the bay's port is always USB-C and
the short cable adapts.  The BOM lists one per board type
([bom/README.md](../bom/README.md)); pick cables that state data (USB 2.0,
480 Mbps): many short ones are charge-only.

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

## Row power

The rack bus, **VRACK**, is 20 or 28 V: whatever the hub negotiated with the
USB-C PD charger ([power.md](power.md)).  The charger's 5 A e-marked cable
plugs into the power box's rear wall.

* **Bay to bay:** 6-pin JST PH jumpers, 24 AWG, 120 mm (VRACK, GND, CAN_H,
  CAN_L, GND, POS: [can.md](can.md)), plugged into the node's right (OUT) and
  the next node's left (IN) connectors through the windows in both tray walls
  and the shared ladder (from the plugs forward to the fascia).  From the
  node's OUT it heads for the tray's front right and crosses that side at
  y ≤ 9 mm, tied to the two anchors on the floor there: a drawer pulled out
  brings its chain foot to 12 mm from the front, right where the jumper used
  to run.  It turns back up to the next node's IN inside the ladder.  Every OUT connector (the node's right one, the hub's row
  outputs) has the IN pinout mirrored, so the jumper lies **flat, with no
  twist**: pin n ↔ pin 7−n, both plugs showing the same face when the cable
  lies on a table.  (The v0.4 nodes had 2-pin, 24 V-only jumpers.)
* **Power box to row:** one 6-pin JST PH feed per row, **the same cable** as
  the jumpers (pin n ↔ pin 7−n), ≈ 0.25 / 0.45 / 0.6 m for rows A / B / C.
  Each plugs into the power box's left wall, reached through the left base
  ladder's window.  It runs forward along that ladder's outer face, climbs the
  rack's left side tied to the ladders, and enters the first bay's left window
  to its node's IN connector.  Out to the left and back in from the left, it
  takes a half turn along the way.  Give the CAN pair 2–3 twists per 10 cm.
* **A node on the bench:** it runs only from its row, never from USB.  To
  flash or try one on a desk, give its IN connector 15–30 V (J1.1 +, J1.2 /
  J1.5 GND; e.g. a 19–24 V laptop or lab supply: the buck starts above
  13.5 V); the PC port then reaches the ESP32.
* **Cameras:** the bay's own node drives its camera (SPI) and light: a
  ready-made 50 cm JST-PH 8 lead, "Same direction" (≈ 45 cm routed between
  the plugs), up out of J6 (vertical, at the node's rear right; pins: CAM_5V,
  GND, SCK, GND, MOSI, MISO, CS, LED_K), straight back along the plenum, out
  of the tray's rear slot (a cable tie),
  straight up behind the tray's rear wall, forwards under the ceiling (cable
  ties through the ceiling's windows, right of the node above), down behind
  the pod and into the pod board's J1 from its right.  The board carries the
  LEDs; an XH → Dupont cable goes from the Mega's side to the board's J2.
