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
   panel-mount USB-C female (25 mm flange, screw holes 17 mm apart) plugs into the node's DUT receptacle,
   runs ~6 cm in the plenum to the chain's fixed end, through the drag chain,
   out of its moving end (forwards, then curling back over the end piece,
   beside the drawer foot) and up through the rear bay's cable window, and is
   screwed into the drawer's rear port wall — in the left or the right DATA position, whichever
   is farther from the board's USB, so the two plugs never meet.  It never
   needs to be touched again (unless a board with its USB on the other side
   moves in: two M3 screws).
2. **The drag chain lies flat in the plenum** and bends in the horizontal
   plane: Olimex DRAG-CHAIN-7X7, 7 × 7 mm inside, 13.5 × 10.2 mm outside,
   R18, ≈ 180 mm with its two end pieces.  Its fixed end is screwed to the
   tray's anchor, its moving end to the drawer foot.  Open the drawer 140 mm
   and the U-bend rolls forward 70 mm: the cable never drags, kinks or snags.
   **Lay the cable in, don't thread it:** neither the extension's plug nor its
   panel-mount socket (with its flange) passes a 7 × 7 channel.  Open the
   links (their bars snap off on both sides), lay the cable in from the fixed
   end's mouth to the moving end's, with ~6 cm out of the fixed end for the
   node and the socket end out of the moving end, then snap the bars back.
3. **Drawer → board: a short cable that belongs to the board.**  USB-C on
   the drawer side, whatever the board needs on the other (C, micro-B or
   mini-B).  Two layouts, set by the board's plate:
   * **a small board** (Pico, ESP32 DevKitC, UNO R4: `orient: side`) turns
     its USB towards the right wall: a plain **straight** 15–20 cm cable
     leaves the right DATA socket forwards, bends once (≥ 10 mm radius) and
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
  the next node's left (IN) connectors through the 17 mm windows in both tray
  walls and the shared ladder, at the front of the plenum where the chain
  never goes.  Every OUT connector (the node's right one, the hub's row
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
* **Cameras:** a JST-PH lead from the node above, down through the hole in
  the tray's bottom to the pod.
