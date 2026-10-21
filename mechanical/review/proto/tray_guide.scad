// Review proto (not a part): a tray's left guide seen as a section (a 60 mm slice behind the fascia, front
// view), with the drawer's flange in it.  Today the lip's underside is a flat 2.5 mm shelf in the air along
// the whole tray, and the ledge's first 48 mm have no gusset (the row cable's window skips the ones at y 5
// and 29).  Proposed (accent): the lip's underside at 45° from its tip (the tip keeps the flange's 0.4 mm),
// a gusset at y 10, the fascia raised under the ledge.  docs/printed-parts-review.md › Tray.
//
//   openscad -D 'VIEW="today"' -o tray_guide_today.png mechanical/review/proto/tray_guide.scad
include <_review.scad>
VIEW = "today";
WALL = 2; LEDGE_X = 12; LEDGE_T = 2.5; LEDGE_Z = 23.1;
GUIDE_WALL_T = 4.5; LIP_Z = 3.4; LIP_T = 2.0; LIP_X = 7;
WALL_H = 20.1; FASCIA = 2.5; L = 60;
GUSSET_T = 2; EPS = 0.01;
FLANGE = [3, 3];
OVER = LIP_X - GUIDE_WALL_T;                // the lip's overhang beyond the guide wall: 2.5

module gusset(y) translate([0, y, LEDGE_Z - LEDGE_T]) rotate([90, 0, 0]) mirror([0, 0, 1])
    linear_extrude(GUSSET_T) polygon([[WALL - EPS, 0], [LEDGE_X, 0], [WALL - EPS, -(LEDGE_X - WALL)]]);
module jumper_window() translate([-1, 3.5, 7.5]) cube([WALL + 2, 26, LEDGE_Z - LEDGE_T - 7.5]);
module flange() mate(0.8) translate([GUIDE_WALL_T + 0.5, 22, LEDGE_Z]) cube([FLANGE[0], 20, FLANGE[1]]);   // the drawer's flange

module body() difference() {
    union() {
        cube([WALL, L, LEDGE_Z - LEDGE_T + EPS]);                                   // side wall up to the ledge
        cube([30, FASCIA, WALL_H]);                                                 // 30 mm of fascia
        translate([0, FASCIA + 1, LEDGE_Z - LEDGE_T]) cube([LEDGE_X, L - FASCIA - 1, LEDGE_T]);   // the ledge
        translate([0, FASCIA + 1, LEDGE_Z]) cube([GUIDE_WALL_T, L - FASCIA - 1, LIP_Z + LIP_T + (VIEW == "today" ? 0 : OVER)]);   // guide wall
        gusset(53);
    }
    jumper_window();
}
module lip_today() translate([GUIDE_WALL_T - EPS, FASCIA + 1, LEDGE_Z + LIP_Z]) cube([OVER + EPS, L - FASCIA - 1, LIP_T]);
// the lip rebuilt: 2 mm at the tip, its underside rising at 45° to the guide wall
module lip_45() translate([GUIDE_WALL_T - EPS, FASCIA + 1, LEDGE_Z + LIP_Z]) rotate([90, 0, 90]) linear_extrude(OVER + EPS)
    polygon([[0, OVER], [L - FASCIA - 1, OVER], [L - FASCIA - 1, OVER + LIP_T], [0, OVER + LIP_T]]);
module lip_45_wedge() translate([GUIDE_WALL_T - EPS, FASCIA + 1, LEDGE_Z + LIP_Z]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(L - FASCIA - 1)
    polygon([[0, 0], [OVER + EPS, OVER + EPS], [OVER + EPS, OVER + LIP_T], [0, OVER + LIP_T]]);
module fascia_raised() translate([0, 0, WALL_H - EPS]) cube([LEDGE_X, FASCIA, LEDGE_Z - LEDGE_T - WALL_H + EPS]);

if (VIEW == "today") { part() { body(); lip_today(); } flange(); }
else { part() body(); changed() { lip_45(); lip_45_wedge(); gusset(10); fascia_raised(); } flange(); }
