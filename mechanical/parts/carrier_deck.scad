// Bay carrier — deck (one per bay).
//
// The removable floor of a bay.  The two drawer guides screw through it into
// the carrier base walls, so the same three screws per side hold guide, deck
// and base together.  A long slot lets the drawer's foot reach the drag
// chain in the plenum below; a magnet pocket gives the drawer a soft
// "closed" detent.  Vent slots sit over the bay node's buck converter.
// Print: flat, top face up, PETG/ASA, no supports.
include <../lib/carrier.scad>

module carrier_deck() {
    difference() {
        rbox([CARRIER_W, CARRIER_D, CARRIER_DECK], r = 3);
        // side screws: button-head through the guide, or flat-head (countersunk) on the
        // inner seam of a double-width bay where there is no guide
        for (b = side_screws()) translate([b[0], b[1], 0]) {
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = CARRIER_DECK + 1);
            translate([0, 0, CARRIER_DECK - 1.9]) cylinder(d1 = M3_CLEAR, d2 = 6.6, h = 1.9 + EPS);
        }
        // pillar screws, countersunk flush (the drawer slides over them)
        for (b = deck_pillars()) translate([b[0], b[1], 0]) {
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = CARRIER_DECK + 1);
            translate([0, 0, CARRIER_DECK - 1.9]) cylinder(d1 = M3_CLEAR, d2 = 6.6, h = 1.9 + EPS);
        }
        // drawer foot slot
        translate([DECK_SLOT[0], (DECK_SLOT[1] + DECK_SLOT[2]) / 2, -EPS])
            rotate([0, 0, 90]) rslot(DECK_SLOT[2] - DECK_SLOT[1], 10, CARRIER_DECK + 2 * EPS);
        // closed-position detent magnet, flush with the top
        translate([DETENT_DECK[0], DETENT_DECK[1], CARRIER_DECK]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1] - 0.6);
        // drawer stop pins (an M2.5×8 screw dropped through the guide lip bites here)
        for (x = [STOP_PIN_X, CARRIER_W - STOP_PIN_X])
            translate([x, STOP_Y, -EPS]) cylinder(d = 2.1, h = CARRIER_DECK + 1);
        // vent slots above the buck converter (front-left of the node)
        for (i = [0 : 5]) translate([NODE_X0 + 8 + i * 7, NODE_FRONT_Y + 12, -EPS])
            rotate([0, 0, 90]) rslot(22, 2.6, CARRIER_DECK + 2 * EPS);
        // service window over the node's RESET / BOOT buttons, closed by the drawer when shut
        translate([NODE_X0 + NODE_SIZE[0] / 2, NODE_REAR_Y - 12, -EPS]) rslot(30, 7, CARRIER_DECK + 2 * EPS);
        // low-friction texture: shallow grooves along Y under the drawer path
        for (x = [DRAWER_X0 + 12 : 10 : DRAWER_X0 + DRAWER_W - 12])
            if (abs(x - DECK_SLOT[0]) > 9)
                translate([x - 0.6, GUIDE_Y0 + 4, CARRIER_DECK - 0.5]) cube([1.2, CARRIER_D - GUIDE_Y0 - 14, 0.5 + EPS]);
    }
}

carrier_deck();
