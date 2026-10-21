// Review proto (not a part): a ladder's rear post around one brace screw, today (a heat-set insert in the
// 7.4 mm edge: 1.7 mm of wall each side) and proposed (a DIN 562 M3 square nut in a pocket cut from the
// ladder's top face, the screw through a plain Ø3.4 hole).  Printed flat as the ladder is, the pocket is
// open upwards: nothing to bridge.  docs/printed-parts-review.md › Ladder.
//
//   openscad -D 'VIEW="both"' -o ladder_nut_trap.png mechanical/review/proto/ladder_nut_trap.scad
VIEW = "both";          // today | proposed | both
T = 7.4;                // ladder thickness (printed flat: Z)
POST = 8;               // rear post width (frame Y)
H = 24;                 // slice height along the post
NUT = [5.5, 5.5, 1.8];  // DIN 562 M3 square nut
NUT_CLEAR = 0.2;        // per side in the pocket
NUT_SET = 2.2;          // the nut's rear face from the rear edge: the wall the brace's preload pulls on
INSERT = [4.0, 6.2];    // today's insert hole Ø, depth
$fn = 48;

module post_slice() cube([POST + 12, H, T]);     // +12: the band the post joins

module today() difference() {
    post_slice();
    translate([POST + 12 + 0.01, H / 2, T / 2]) rotate([0, -90, 0]) {
        cylinder(d = INSERT[0], h = INSERT[1] + 0.01);
        cylinder(d1 = INSERT[0] + 0.8, d2 = INSERT[0], h = 1.4);
    }
}

module proposed() difference() {
    post_slice();
    // the screw's plain hole from the rear edge
    translate([POST + 12 + 0.01, H / 2, T / 2]) rotate([0, -90, 0]) cylinder(d = 3.4, h = 14);
    // the nut pocket, open to the top face (printed flat: the top face is the last layers, no bridge)
    translate([POST + 12 - NUT_SET - NUT[2] - NUT_CLEAR, H / 2 - NUT[0] / 2 - NUT_CLEAR, T / 2 - NUT[0] / 2 - NUT_CLEAR])
        cube([NUT[2] + 2 * NUT_CLEAR, NUT[0] + 2 * NUT_CLEAR, T]);
}

module nut() color("#c9a227") translate([POST + 12 - NUT_SET - NUT[2], H / 2 - NUT[0] / 2, T / 2 - NUT[0] / 2])
    difference() { cube([NUT[2], NUT[0], NUT[1]]); translate([-1, NUT[0] / 2, NUT[1] / 2]) rotate([0, 90, 0]) cylinder(d = 2.5, h = 5); }
module screw() color("#888") translate([POST + 12 + 3, H / 2, T / 2]) rotate([0, -90, 0]) { cylinder(d = 3, h = 11); cylinder(d = 5.6, h = 2); }
module insert() color("#b87333") translate([POST + 12 - INSERT[1], H / 2, T / 2]) rotate([0, 90, 0]) difference() { cylinder(d = 4.0, h = INSERT[1]); cylinder(d = 3, h = INSERT[1] + 1); }

if (VIEW == "today" || VIEW == "both") { color("#a9c4e4") today(); insert(); screw(); }
if (VIEW == "proposed" || VIEW == "both") translate([0, VIEW == "both" ? H + 10 : 0, 0]) { color("#a9c4e4") proposed(); nut(); screw(); }
