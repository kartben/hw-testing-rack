// Bridge bar — turns two neighbouring standard drawers into one double-width
// drawer for big EVKs (i.MX RT1170 / i.MX 8M-class boards).
//
// A double bay is just two standard bays side by side: two carriers, two
// drawers, two drag chains and one or two bay nodes (the second node gives
// the EVK its second USB cable — debug + power/OTG).  Two bridge bars, front
// and rear, sit on the drawers' walls, drop onto the drawers' plate pins and
// lock the two drawers together so they slide as one.  The EVK screws onto
// standard M3 standoffs anywhere along the bars' slots.
// Length ≈ 296 mm: print diagonally on a 250 × 210 bed. PETG, 4 walls.
include <../lib/carrier.scad>

PRINT = false;                                 // true: upside down for printing
BAR_W = 22;
BAR_T = 6;
// span from the left drawer's inner left wall to the right drawer's inner right wall
BAR_L = BAY_PITCH + DRAWER_INNER_W;
LEG_H = DRAWER_WALL_H - DRAWER_BOTTOM + 0.5;   // legs reach down to the drawer bottoms
// the two plate pins this bar drops onto (bar coordinates, x from the left inner wall)
PIN_DX = [plate_pins()[0][0] + 0.3, BAY_PITCH + plate_pins()[0][0] + 0.3];

module bridge_bar() {
    difference() {
        union() {
            translate([0, 0, LEG_H]) rbox([BAR_L, BAR_W, BAR_T], r = 3);
            for (x = PIN_DX) translate([x, BAR_W / 2, 0]) cylinder(d = 10, h = LEG_H + 0.1);
            // straddles the two adjacent drawer walls in the middle
            translate([DRAWER_INNER_W - 1, 0, LEG_H - 3]) cube([BAY_PITCH - DRAWER_INNER_W + 2, BAR_W, 3.1]);
        }
        for (x = PIN_DX) translate([x, BAR_W / 2, -EPS]) cylinder(d = 4.2, h = 3);
        // the drawers' walls pass through notches in the centre block
        translate([DRAWER_INNER_W - 0.3, -EPS, LEG_H - 3 - EPS]) cube([DRAWER_WALL + 0.6, BAR_W + 2 * EPS, 3]);
        translate([BAY_PITCH - DRAWER_WALL - 0.3, -EPS, LEG_H - 3 - EPS]) cube([DRAWER_WALL + 0.6, BAR_W + 2 * EPS, 3]);
        // M3 standoff slots along the bar
        for (seg = [[14, DRAWER_INNER_W - 14], [BAY_PITCH + 14, BAR_L - 14]])
            translate([(seg[0] + seg[1]) / 2, BAR_W / 2, LEG_H - EPS]) rslot(seg[1] - seg[0], M3_CLEAR, BAR_T + 1);
    }
}

if (PRINT) rotate([180, 0, 0]) bridge_bar(); else bridge_bar();
