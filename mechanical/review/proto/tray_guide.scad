// Review proto (not a part): a tray's left guide, the first 60 mm behind the fascia, today and proposed.
// Today the lip's underside is a flat 2.5 mm shelf in the air along the whole tray, and the ledge's first
// 48 mm have no gusset (the row cable's window skips the ones at y 5 and 29): both print badly.
// Proposed: the lip's underside at 45° from its tip (which keeps the flange's 0.4 mm), the fascia raised
// under the ledge's front end, a gusset at y 10 (behind the tie strap, in front of the plug).
// docs/printed-parts-review.md › Tray.
//
//   openscad -D 'VIEW="both"' -o tray_guide.png mechanical/review/proto/tray_guide.scad
VIEW = "both";
WALL = 2; LEDGE_X = 12; LEDGE_T = 2.5; LEDGE_Z = 23.1;
GUIDE_WALL_T = 4.5; LIP_Z = 3.4; LIP_T = 2.0; LIP_X = 7;
WALL_H = 20.1; FASCIA = 2.5; L = 60;        // the slice: 60 mm from the fascia
GUSSET_T = 2; EPS = 0.01;
FLANGE = [3, 3];
OVER = LIP_X - GUIDE_WALL_T;                // the lip's overhang beyond the guide wall: 2.5

module gusset(y) translate([0, y, LEDGE_Z - LEDGE_T]) rotate([90, 0, 0]) mirror([0, 0, 1])
    linear_extrude(GUSSET_T) polygon([[WALL - EPS, 0], [LEDGE_X, 0], [WALL - EPS, -(LEDGE_X - WALL)]]);
module jumper_window() translate([-1, 3.5, 7.5]) cube([WALL + 2, 26, LEDGE_Z - LEDGE_T - 7.5]);
module flange() color("#e8e8e8") translate([GUIDE_WALL_T + 0.5, 22, LEDGE_Z]) cube([FLANGE[0], 20, FLANGE[1]]);

module common(raised_fascia) {
    cube([WALL, L, LEDGE_Z - LEDGE_T + EPS]);                                   // side wall up to the ledge
    cube([30, FASCIA, WALL_H]);                                                 // 30 mm of fascia
    if (raised_fascia) translate([0, 0, WALL_H - EPS]) cube([LEDGE_X, FASCIA, LEDGE_Z - LEDGE_T - WALL_H + EPS]);
    translate([0, FASCIA + 1, LEDGE_Z - LEDGE_T]) cube([LEDGE_X, L - FASCIA - 1, LEDGE_T]);   // the ledge
    gusset(53);
}

module today() difference() {
    union() {
        common(false);
        translate([0, FASCIA + 1, LEDGE_Z]) cube([GUIDE_WALL_T, L - FASCIA - 1, LIP_Z + LIP_T]);   // guide wall
        translate([0, FASCIA + 1, LEDGE_Z + LIP_Z]) cube([LIP_X, L - FASCIA - 1, LIP_T]);          // flat lip
    }
    jumper_window();
}

module proposed() difference() {
    union() {
        common(true);
        gusset(10);
        translate([0, FASCIA + 1, LEDGE_Z]) cube([GUIDE_WALL_T, L - FASCIA - 1, LIP_Z + LIP_T + OVER]);
        // the lip: its section a wedge, underside rising at 45° from the tip (z LIP_Z at x LIP_X) to the wall
        translate([GUIDE_WALL_T - EPS, FASCIA + 1, LEDGE_Z]) rotate([90, 0, 90]) linear_extrude(OVER + EPS)
            polygon([[0, LIP_Z + OVER], [L - FASCIA - 1, LIP_Z + OVER], [L - FASCIA - 1, LIP_Z + OVER + LIP_T], [0, LIP_Z + OVER + LIP_T]]);
        translate([GUIDE_WALL_T - EPS, FASCIA + 1, LEDGE_Z + LIP_Z]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(L - FASCIA - 1)
            polygon([[0, 0], [OVER + EPS, OVER + EPS], [OVER + EPS, OVER + LIP_T], [0, OVER + LIP_T]]);
    }
    jumper_window();
}

if (VIEW == "today" || VIEW == "both") { color("#a9c4e4") today(); flange(); }
if (VIEW == "proposed" || VIEW == "both") translate([VIEW == "both" ? 26 : 0, 0, 0]) { color("#a9c4e4") proposed(); flange(); }
