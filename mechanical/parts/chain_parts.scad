// Drag-chain hardware for the drawer cable (7×7 mm chain lying flat in the plenum).
//
//   -D 'PART="foot"'    drawer foot: tongue in the drawer's groove, fin for the moving end
//   -D 'PART="anchor"'  fixed-end block, screwed to the tray (2 × M3 into inserts)
//   -D 'PART="link"'    optional printable link if you don't buy a chain
//   -D 'PART="bar"'     its removable bar (one per link): slide it out to lay the cable in
//
// The reference chain (Olimex DRAG-CHAIN-7X7, links open on both sides) ends in two end
// pieces with a tab flush with the outer face of the U and two holes 8 mm apart along the
// chain (config/rack.yaml › chain.end_holes).  Each tab screws to the inner face of the anchor
// or of the foot's fin with 2 × PT 2.6 × 8 (thread-forming, or M2.5 × 8 self-tapping) and washers
// (the tab holes may be up to 4.3 mm).  Screw the end pieces on at the bench, then fit the anchor and the foot.
// Print: anchor and bar as modelled, foot on its fin, link on its fixed bar; PETG, no supports.
include <../lib/carrier.scad>

PART = "foot";
TONGUE = [6, 10];                     // X × Y of the tongue in the drawer's foot groove
TONGUE_H = 2.1;                       // the groove is 2.3 deep
PILOT = 2.2;                          // PT 2.6 / M2.5 self-tapping pilot

// ------------------------------------------------------------------ foot
// Foot coordinates: origin on the moving run's axis, at the chain's mouth (y), on the drawer's
// underside (z = CARRIER_PLENUM in the tray).  The fin stands outside the moving run, 1 mm clear
// of the right ledge, along the end piece; a bridge over the chain joins it to the tongue, which
// sits LOCK behind the mouth, under the drawer's rear bay (its lock screw goes in from there).
// The extension leaves the mouth forwards and curls back over the end piece, left of the
// bridge, into the rear bay's cable window.
LOCK = CHAIN_FOOT_Y - CHAIN_MOVING_Y;
FIN_X = [CHAIN_H / 2, CARRIER_W - (DRAWER_X0 + 4) - CHAIN_MOVING_X - 1];
FIN_Y = [-TONGUE[1] / 2, max(chain_end_holes(0)[1] + 6, LOCK + TONGUE[1] / 2)];
FIN_Z0 = CARRIER_BOTTOM + 4 - CARRIER_PLENUM;           // 1 mm above the tray's chain rails
BRIDGE_Z0 = CHAIN_Z + CHAIN_W / 2 + 2 - CARRIER_PLENUM; // 2 mm above the chain
module foot() {
    difference() {
        union() {
            // tongue, its +x edge chamfered (printed on the fin, that edge is underneath)
            translate([0, LOCK - TONGUE[1] / 2, 0]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(TONGUE[1])
                polygon([[-TONGUE[0] / 2, 0], [TONGUE[0] / 2, 0], [TONGUE[0] / 2 - TONGUE_H, TONGUE_H], [-TONGUE[0] / 2, TONGUE_H]]);
            translate([-TONGUE[0] / 2, LOCK - TONGUE[1] / 2, BRIDGE_Z0]) cube([FIN_X[1] + TONGUE[0] / 2, TONGUE[1], -BRIDGE_Z0]);
            translate([FIN_X[0], FIN_Y[0], FIN_Z0]) cube([FIN_X[1] - FIN_X[0], FIN_Y[1] - FIN_Y[0], -FIN_Z0]);
        }
        // lock screw (PT 2.6 × 8, down from the drawer's rear bay)
        translate([0, LOCK, TONGUE_H - 8]) cylinder(d = PILOT, h = 9);
        // the end piece's tab holes
        for (y = chain_end_holes(0)) translate([FIN_X[0] - EPS, y, CHAIN_Z - CARRIER_PLENUM]) rotate([0, 90, 0]) cylinder(d = PILOT, h = 10);
    }
}

// ------------------------------------------------------------------ anchor
// Anchor coordinates: origin on the fixed run's axis, at the chain's mouth (y), on top of
// the tray's insert bosses.  The block's inner face is the fixed run's outer face.  Its underside stays
// 3 mm over the tray's floor (ANCHOR_BASE: the end piece's pilots keep their wall below), the bosses
// standing 2 mm up into two pockets in it
ANCHOR_BASE = CARRIER_BOTTOM + 3;
module anchor() {
    o = [CHAIN_FIXED_RUN_X, CHAIN_FIXED[1], ANCHOR_Z0];
    h = CHAIN_Z + CHAIN_W / 2 - ANCHOR_BASE;
    difference() {
        translate([ANCHOR_X1 - ANCHOR[0], ANCHOR_Y0, ANCHOR_BASE] - o) rbox([ANCHOR[0], ANCHOR[1], h], r = 1.5);
        // M3 × 8 into the tray's inserts, heads sunk to leave 3 mm under them
        for (b = ANCHOR_BOSSES) translate(concat(b, [ANCHOR_Z0]) - o) {
            translate([0, 0, ANCHOR_BASE - ANCHOR_Z0 - EPS]) cylinder(d = 7.5 + 0.4, h = ANCHOR_Z0 - ANCHOR_BASE + EPS);
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = h + 2 * EPS);
            translate([0, 0, 3]) cylinder(d = M3_HEAD[0] + 0.4, h = h);
        }
        for (y = chain_end_holes(CHAIN_FIXED[1])) translate([ANCHOR_X1 + EPS, y, CHAIN_Z] - o) rotate([0, -90, 0]) cylinder(d = PILOT, h = 7);
    }
}

// ------------------------------------------------------------------ link
// Lying as in the rack: chain axis X, pins vertical (Z), a side plate of (outer - inner) / 2 at
// the bottom and at the top.  At a joint the plates overlap at half thickness: the pin on the
// inner half of one link snaps into the outer half of the next.  One bar belongs to the link;
// the other slides into two pockets from the outside (PART = "bar").  No bend stops: in the
// plenum the two runs and the rails hold the U.
LINK_P = CHAIN_PITCH;
LINK_R = CHAIN_H / 2;                             // rounded plate ends around the pins
LINK_T = (CHAIN_W - CHAIN_INNER[1]) / 2;          // side plate
LINK_B = (CHAIN_H - CHAIN_INNER[0]) / 2;          // bar
LINK_C = 0.3;                                     // joint clearance
LINK_MID = [LINK_R + LINK_C, LINK_P - LINK_R - LINK_C];   // x span of the full-thickness middle
POCKET = 1;                                       // bar pocket depth in each plate

module link_plate_2d(half) {      // "outer": female end + middle, "inner": middle + male end
    hull() {
        translate([LINK_MID[0], -LINK_R]) square([LINK_MID[1] - LINK_MID[0], 2 * LINK_R]);
        translate([half == "outer" ? 0 : LINK_P, 0]) circle(r = LINK_R);
    }
}
module link_plate() {             // bottom plate, z = 0 .. LINK_T
    difference() {
        union() {
            linear_extrude(LINK_T / 2) link_plate_2d("outer");
            translate([0, 0, LINK_T / 2]) linear_extrude(LINK_T / 2) link_plate_2d("inner");
            translate([LINK_P, 0, 0.1]) cylinder(d1 = 2.2, d2 = 2.6, h = LINK_T / 2 - 0.1 + EPS);   // pin, tip chamfered
        }
        translate([0, 0, -EPS]) cylinder(d = 2.9, h = LINK_T / 2 + 2 * EPS);                      // the previous link's pin
        translate([LINK_MID[0] - EPS, LINK_R - LINK_B - 0.15, LINK_T - POCKET]) cube([LINK_MID[1] - LINK_MID[0] + 2 * EPS, LINK_B + 0.15 + EPS, POCKET + EPS]);
    }
}
module link() {
    link_plate();
    translate([0, 0, CHAIN_W]) mirror([0, 0, 1]) link_plate();
    translate([LINK_MID[0], -LINK_R, LINK_T - EPS]) cube([LINK_MID[1] - LINK_MID[0], LINK_B, CHAIN_W - 2 * LINK_T + 2 * EPS]);
}
module bar() cube([LINK_MID[1] - LINK_MID[0] - 0.2, CHAIN_INNER[1] + 2 * POCKET - 0.1, LINK_B]);

if (PART == "foot") rotate([0, 90, 0]) foot();
else if (PART == "anchor") anchor();
else if (PART == "bar") bar();
else rotate([90, 0, 0]) link();
