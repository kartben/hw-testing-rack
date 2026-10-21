# Standalone bays

One bay out of the rack, on a desk: the same boards as in the rack, unchanged, in a small printed box, fed by a
USB-C PD charger.  Two boxes and one accessory (`mechanical/parts/standalone.scad`):

| | Boards | Outside (W × D × H, on its feet) | Printed (H2D, 0.20 Standard, PETG, no supports) |
|---|---|---|---|
| **Solo** | the bay node + the single DATA port board | 106 × 95.5 × 33.6 mm | base + lid, one plate: 64 g, 2 h 22 |
| **Quad** | the bay node + the DATA ×4 v2 | 107 × 95.5 × 96.1 mm | base + shelf + lid, one plate: 136 g, 5 h 15 |
| **Desk frame** | the rack's honeycomb plate, the DUTs on its pegs | 142.8 × 190.8 × 8.5 mm | frame + plate, one plate: 85 g, 4 h 01 |

The bought parts and the hardware per unit: [bom/README.md › Standalone bays](../bom/README.md) (≈ €5 a unit
beyond its boards; optional, outside the rack's totals).

## Layout

- **Solo.**  The node lies on four insert bosses, its front edge on the front face: PC port (J3), the status LED's
  window and the SERVICE switch, as on the tray's fascia.  The DATA port board hangs under the lid over the
  node's front right, component face down (USB-C is reversible), its USB-C (the DUT's port) in the front face
  above the node's row.  Its lead (PH 8, 15 cm) goes from the node's J7 to the board's PH 8.
- **Quad.**  The DATA ×4 v2 stands behind the front face in two side slots on the floor, its four USB-C through
  the face, each 2 × 6 header under a window (a Dupont housing plugs in through it), its VBUS LEDs and D1 behind
  windows, the port numbers 1–4 debossed.  The node lies on a shelf over it, front edge forward: PC port, SERVICE
  and status at the top of the front face.  The shelf rests on the slots' rails and two 45° ledges, 0.5 over the
  v2's top edge, so the board can't lift out.
- **Both.**  At the back, the PD module's USB-C: the module (config/rack.yaml › standalone.pd_module) sits on a
  seat on the floor, its PCB's edge on the rear wall, a fence round its sides and far end, a 1 mm double-sided
  foam pad under it; a collar in the wall's inner 0.6 mm centres its USB-C's shell, whatever the board.  The rear
  wall is 1.2 mm thick over the node's antenna, nothing metal near it.  The lid: RESET / BOOT pin holes over guide
  tubes, a window over J6 (the camera's lead plugs in from above), vents over the node's buck.  AUX (J5): a slot
  for its lead at the right wall's top.  Four rubber bumpers under the box, in 0.5 mm pockets.
- **Desk frame.**  The rack's plate drops into its pocket on two pins, as in a drawer; the DUTs sit on its pegs as
  in the rack.  Behind it, at desk level, a 2 mm dock: either box's two front feet drop through its slots and
  stand on the desk, the box's front 0.5 off the frame.  Lift the box to undock it.

## Power

A USB-C PD trigger module, a CH224K one set to 20 V (a bought "decoy" board), feeds the node's J1: pin 1 VRACK
(red), pin 2 GND (black), a PHR-6 housing on two wires soldered to the module's output pads.  Any PD charger that
offers 20 V, 30 W or more: a bay draws 13 W at most; 15 V works too, 12 V and 9 V don't, and without the hub the
node never takes a rack address ([cabling.md](cabling.md)).  The bought board's size goes in
`config/rack.yaml › standalone.pd_module` (PCB length and width, thickness, the USB-C's axis over its underside):
the seat and the collar follow.  A seller's board up to 25 × 12.4 mm fits; its USB-C may stand 0.6–2 mm proud of
its PCB's edge.

## Assembly

**Solo**
1. Heat-set the inserts: 4 in the node's bosses, 4 in the corner bosses.
2. The PD module onto its seat on the foam pad, its USB-C into the rear wall's collar; its lead into the node's J1.
3. The node onto its bosses (4 × M3×8); the DATA lead into J7.
4. The DATA port board under the lid, component face down (2 × PT 2.3×8 up through it); its lead into its PH 8.
5. The lid on (4 × M3×8), the four bumpers under the base.

**Quad**
1. Heat-set the inserts: 4 in the shelf's bosses, 4 in the base's corner bosses.
2. The PD module onto its seat, as the Solo's.  The DATA lead into the v2's J1 first, then the v2 down into its
   side slots, USB-C forward.
3. The node onto the shelf (4 × M3×8); the PD lead into J1, the DATA lead into J7; the shelf onto its ledges.
4. The lid on (4 × M3×8), the four bumpers under the base.

**Desk frame**: the plate into the frame, its pegs and boards as in a drawer (`tools/plate_layout.py`); the box's
front feet into the dock's slots.

## Checks

SolidCraft, exact solids, every board in and every plug plugged (the PC cable, the DUT cables, the charger's, the
PH leads, the Dupont blocks): no overlap.  Closest: the USB-C overmolds 0.04 in their cuts (as on the rack's port
wall), the PD module's USB-C 0.17 in its collar, the Dupont blocks 0.6 in their windows, the lid 1.0 over the
node's C1 and its buttons' tubes 1.0 over the buttons, the docked box 0.5 off the frame and its feet 0.6 in the
dock's slots.  Bambu Studio: no supports; past 45° as printed only short bridges over the openings in the walls
(the longest 16.4, the Quad's header windows) and the lids' counterbore shoulders.

Not drawn yet: a camera mast for either box; a blank for the Quad's header windows.
