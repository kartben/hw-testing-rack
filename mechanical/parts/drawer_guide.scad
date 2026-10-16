// Drawer guide — left and right C-channel rails screwed on top of the deck.
//
//   openscad -D 'SIDE="left"'  -o drawer_guide_left.stl  parts/drawer_guide.scad
//   openscad -D 'SIDE="right"' -o drawer_guide_right.stl parts/drawer_guide.scad
//
// The lip captures the drawer's rear flange segment, so a drawer pulled out
// to its full 140 mm stroke cannot tip.  An M2.5×8 screw dropped through the
// lip hole near the front is the end stop; remove it to take the drawer out.
// The three M3×12 screws go guide → deck → carrier wall insert.
// Print: upside down (lip on the bed), PETG; POM-like "igus" filament if you have it.
include <../lib/carrier.scad>

SIDE = "left";
GUIDE_L = CARRIER_D - 2 - GUIDE_Y0;
GUIDE_H = GUIDE_LIP_Z + GUIDE_LIP_T;
LIP_X = DRAWER_X0 - 1.0;          // lip reaches over the flange, stops 1 mm short of the drawer side

module guide_left() {
    difference() {
        translate([0, GUIDE_Y0, 0]) union() {
            cube([GUIDE_WALL_T, GUIDE_L, GUIDE_H]);
            translate([0, 0, GUIDE_LIP_Z]) cube([LIP_X, GUIDE_L, GUIDE_LIP_T]);
        }
        // lead-in chamfer on the lip underside at the front
        translate([GUIDE_WALL_T, GUIDE_Y0 - EPS, GUIDE_LIP_Z - EPS])
            rotate([0, 0, 0]) hull() {
                cube([LIP_X - GUIDE_WALL_T + 1, EPS, 1.4]);
                translate([0, 6, 0]) cube([LIP_X - GUIDE_WALL_T + 1, EPS, EPS]);
            }
        // M3 screws with counterbore
        for (s = side_screws()) if (s[0] < CARRIER_W / 2) translate([s[0], s[1], -EPS]) {
            cylinder(d = M3_CLEAR, h = GUIDE_H + 1);
            translate([0, 0, GUIDE_H - 1.8]) cylinder(d = 6.2, h = 2);
        }
        // stop screw hole through the lip
        translate([STOP_PIN_X, STOP_Y, GUIDE_LIP_Z - 1]) cylinder(d = 2.8, h = GUIDE_LIP_T + 2);
    }
}

if (SIDE == "left") guide_left();
else translate([CARRIER_W, 0, 0]) mirror([1, 0, 0]) guide_left();
