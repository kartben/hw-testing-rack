// Drag-chain hardware for the drawer cable (7×7 mm chain lying flat in the plenum).
//
//   -D 'PART="foot"'    drawer foot: tongue through the deck slot + moving-end tab
//   -D 'PART="anchor"'  fixed-end anchor screwed to the carrier base
//   -D 'PART="link"'    optional printable chain link (snap pins) if you don't buy a chain
//
// Both brackets take the usual 7×7 chain end pieces (M2.5 holes, check your
// chain: many have 10 mm hole pitch).  Print: on their sides, PETG.
include <../lib/carrier.scad>

PART = "foot";
END_HOLES = 10;                       // hole pitch of the chain end pieces
TONGUE = [6, 10];                     // X × Y of the tongue through the deck slot
DECK_TOP = CARRIER_PLENUM;            // deck surface above the carrier bottom

// ------------------------------------------------------------------ foot
// Drawer-foot coordinates: origin on the tongue axis at deck-surface height.
module foot() {
    top = FOOT_GROOVE_DEPTH - 0.2;            // tongue top, just inside the drawer groove
    bottom = CHAIN_Z - DECK_TOP - 1.5;         // tab underside, inside the plenum
    difference() {
        union() {
            translate([-TONGUE[0] / 2, -TONGUE[1] / 2, bottom]) cube([TONGUE[0], TONGUE[1], top - bottom]);
            // horizontal tab for the chain's moving end (towards the chain, i.e. +Y)
            translate([-6, -TONGUE[1] / 2, bottom]) cube([12, TONGUE[1] + END_HOLES + 8, 3]);
        }
        // lock screw (M2.5 self-tapping from the drawer's rear bay)
        translate([0, 0, top - 8]) cylinder(d = 2.2, h = 9);
        // chain end holes
        for (dy = [0, END_HOLES]) translate([0, TONGUE[1] / 2 + 3 + dy, bottom - EPS]) cylinder(d = 2.7, h = 4);
    }
}
FOOT_GROOVE_DEPTH = 2.3;

// ------------------------------------------------------------------ anchor
module anchor() {
    difference() {
        union() {
            translate([-12, -4, 0]) rbox([24, 8, 3], r = 1.5);
            // tab carrying the fixed end, at chain height, pointing back (+Y)
            translate([-6, 0, 0]) cube([12, END_HOLES + 12, 3]);
        }
        for (dx = [-8, 8]) translate([dx, 0, -EPS]) cylinder(d = M3_CLEAR, h = 4);
        for (dy = [0, END_HOLES]) translate([0, 6 + dy, -EPS]) cylinder(d = 2.7, h = 4);
    }
}

// ------------------------------------------------------------------ link
// A simple printable link: two side plates joined by top/bottom bars.
LINK_P = 9;                           // pitch
module link() {
    w = CHAIN_OUTER[0]; h = CHAIN_OUTER[1]; t = 1.6;
    difference() {
        union() {
            for (z = [0, w - t]) translate([0, 0, z]) hull() {
                cylinder(d = h, h = t);
                translate([LINK_P, 0, 0]) cylinder(d = h * 0.8, h = t);
            }
            translate([1, -h / 2, 0]) cube([2, h, w]);
            translate([LINK_P - 3, -h / 2, 0]) cube([1.6, 1.6, w]);
            translate([LINK_P - 3, h / 2 - 1.6, 0]) cube([1.6, 1.6, w]);
            translate([LINK_P, 0, t]) cylinder(d = 2.6, h = 0.8);   // snap pins
            translate([LINK_P, 0, w - t - 0.8]) cylinder(d = 2.6, h = 0.8);
        }
        translate([0, 0, -EPS]) cylinder(d = 2.9, h = w + 1);
    }
}

if (PART == "foot") rotate([0, 90, 0]) foot();
else if (PART == "anchor") anchor();
else link();
