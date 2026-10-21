// Review proto (not a part): the drawer's closed-position detent on a slice of the tray's left ledge, the
// drawer's floor above it (grey, translucent).  Today: a Ø6 × 3 magnet CA-glued in a pocket of the ledge's
// widened pad, its twin in a boss under the drawer.  Proposed (accent): a spring tab cut in the ledge,
// 20 × 2.5 with a 0.6 mm bump, 0.56 % in the print plane, ≈ 3 N; a notch under the drawer catches it.
// docs/printed-parts-review.md › Drawer.
//
//   openscad -D 'VIEW="today"' -o detent_today.png mechanical/review/proto/detent.scad
include <_review.scad>
VIEW = "today";
LEDGE_X = 12; LEDGE_T = 2.5; L = 40; WALL = 2; LZ = 9.5;
TAB = [2.5, 20]; TX = LEDGE_X - 4.7; TY = L / 2 - 9.2;        // the tab: width (x), length (y); its corner
$fn = 48;
module ledge() union() { cube([WALL, L, LZ + LEDGE_T]); translate([0, 0, LZ]) cube([LEDGE_X, L, LEDGE_T]); }
module pad() translate([0, L / 2 - 5, LZ]) cube([LEDGE_X + 4, 10, LEDGE_T]);
module pocket() translate([LEDGE_X + 1, L / 2, LZ + LEDGE_T - 3.2]) cylinder(d = 6.25, h = 4);
module magnet() color("#777") translate([LEDGE_X + 1, L / 2, LZ + LEDGE_T - 3.1]) cylinder(d = 6, h = 3);
// the slits round the tab (0.8), open at its free end (towards the front, -y)
module tab_cuts() { for (x = [TX - 0.8, TX + TAB[0]]) translate([x, TY - 0.8, LZ - 0.5]) cube([0.8, TAB[1] + 0.8, 4]); translate([TX - 0.8, TY - 0.8, LZ - 0.5]) cube([TAB[0] + 1.6, 0.8, 4]); }
module tab_box() translate([TX, TY, LZ - 0.5]) cube([TAB[0], TAB[1], 4]);
module tab_piece() { translate([TX, TY, LZ]) cube([TAB[0], TAB[1], LEDGE_T]);
    translate([TX, TY + 1.2, LZ + LEDGE_T - 0.01]) rotate([90, 0, 90]) linear_extrude(TAB[0]) polygon([[0, 0], [0.6, 0.6], [2.4, 0.6], [3, 0]]); }   // the bump, 45° both ways
// the drawer's floor over the ledge (its outer 4 mm ride on the ledge), with the magnet boss or the notch
module drawer_floor(notch) mate(0.4) translate([WALL + 1, -2, LZ + LEDGE_T + 0.3]) difference() {
    union() { cube([14, L + 4, 2.5]); if (!notch) translate([LEDGE_X + 1 - WALL - 1, L / 2 + 2, -1]) cylinder(d = 8, h = 1); }
    if (notch) translate([TX - WALL - 1, TY + 1.2 + 2, -0.01]) cube([TAB[0], 3, 0.7]);
}

if (VIEW == "today") { part() difference() { union() { ledge(); pad(); } pocket(); } magnet(); drawer_floor(false); }
else {
    part() difference() { ledge(); tab_cuts(); tab_box(); }
    changed() tab_piece();
    drawer_floor(true);
}
