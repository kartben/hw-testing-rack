# Assembly

Order of work for the default 14-bay build.  Quantities: [`bom/README.md`](../bom/README.md).

## 1. Print

`python tools/build.py stl` → `mechanical/stl/` (or grab the STL bundle
from the latest CI run).  Per carrier unit: `carrier_base`, `carrier_deck`,
`drawer_guide_left`, `drawer_guide_right`, `drawer`, `chain_foot`,
`chain_anchor`; one plate per board; tier brackets L/R per row + roof; base
parts once.  Press the heat-set inserts while the parts are on the bench:
carrier (4 node, 6 side, 3 pillar, 2 chain, 4 camera underneath), roof decks
(camera + accessory grid), plates.

## 2. Frame

1. Tap both ends of every row/roof beam M5.
2. Base box: 4 posts + 8 base beams with inside corner brackets; feet on the posts.
3. For each row, bottom to top: bolt the left/right **tier brackets** to the
   posts' inner slots (pre-load 4 drop-in T-nuts per post), then the two
   beams into the brackets' pockets (M5 into the tapped cores).  Leave the
   bracket screws slightly loose, square the row, tighten.
4. Roof: same bracket pair + beams, then the roof decks.

## 3. Base (mains — read [power.md](power.md) first)

1. Base plates on the bottom beams; PSU on its saddles (cable ties or M3 strap).
2. Inlet panel with the Schurter DD11; mains wiring with insulated 4.8 mm
   receptacles; PE to the PSU FG **and** to the frame (serrated washer).
3. Mains cover over the PSU AC terminals.  Hub on its mount, 16 AWG DC from
   the PSU to the hub's JST VH input.  Close the panels.
4. Before anything else is connected: power up, check 24 V at every hub
   output and that all five ON LEDs light.

## 4. Each bay

1. **Node** onto the carrier standoffs (4 × M3×6).
2. **Drag chain**: cut ≈ 160 mm (21 links of the common 7×7 R18); fixed end
   to the `chain_anchor` (screwed to the carrier), moving end to the
   `chain_foot`.  Lay the drawer extension cable in the chain (links snap open),
   plug its male end into the node's DUT port.
3. **Carrier** onto the row's beams (4 × M5 + T-nuts); JST PH jumper to the
   neighbour through the side notches (row feed into the first bay).
4. **Deck**: drop it on with the foot's tongue through the slot; M3 flat-heads
   into the three pillars.  **Guides** on top with the M3×12 side screws
   (through guide and deck into the carrier wall).  Magnet into the deck pocket.
5. **Drawer**: magnet underneath; screw the panel-mount female into the DATA
   port position **farther from the board's debug USB** (left or right; the
   viewer's bay panel says which: *DATA socket*), M3 ears; slide the drawer in from the front (its rear flange enters
   the guide channels), engage the foot in the rear groove, lock it with the
   M2.5 from inside the rear bay; drop the two M2.5 stop screws through the
   guide lips.
6. **Plate + board + short cable**, printed `bay_label` (or 12 mm tape) in the front recess.

Double bays: steps 1–5 for both units, then the two **bridge bars** across
the drawers, then the EVK on M3 standoffs.

## 5. Cameras (optional)

Mount under the ceiling (4 × M3), cradle on the M3×30 pivot, XIAO in the
cradle, PH lead to the node above (or the bay's own node for the top row).

## 6. Bring-up

Per node: SERVICE on → laptop on the PC port → flash → SERVICE off.  Then
`usbip list -r bay-<id>.local`.  See [firmware.md](firmware.md).
