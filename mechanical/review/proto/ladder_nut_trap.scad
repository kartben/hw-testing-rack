// Review proto (not a part): a ladder's rear post around one brace screw, cut in half along the screw's axis
// (the ladder's upper half removed), with the brace strap and its M3 × 8 against the rear edge.  Today: a
// heat-set M3 insert (copper) in a Ø4.0 × 6.2 hole along the 7.4 mm edge, 1.7 mm of wall on each face.
// Proposed (accent: the nut): a DIN 562 M3 square nut in a 5.9 × 5.9 × 2.2 pocket open to the top face,
// 2.2 mm from the edge, a plain Ø3.4 hole; SolidCraft: 0.2 mm round the nut and the screw.
// docs/printed-parts-review.md › Ladder.
//
//   openscad -D 'VIEW="today"' -o ladder_nut_trap_today.png mechanical/review/proto/ladder_nut_trap.scad
include <_review.scad>
VIEW = "today";
T = 7.4; POST = 8; H = 24; W = POST + 12;    // the post and 12 mm of the band it joins
NUT = [5.5, 5.5, 1.8]; NUT_CLEAR = 0.2; NUT_SET = 2.2;
INSERT = [4.0, 6.2];
$fn = 48;
module upper_half() translate([-5, -5, T / 2]) cube([W + 20, H + 10, T]);      // removed from everything: the section
module post_slice() cube([W, H, T]);
module insert_hole() translate([W + 0.01, H / 2, T / 2]) rotate([0, -90, 0]) { cylinder(d = INSERT[0], h = INSERT[1] + 0.01); cylinder(d1 = INSERT[0] + 0.8, d2 = INSERT[0], h = 1.4); }
module screw_hole() translate([W + 0.01, H / 2, T / 2]) rotate([0, -90, 0]) cylinder(d = 3.4, h = 14);
module pocket() translate([W - NUT_SET - NUT[2] - NUT_CLEAR, H / 2 - NUT[0] / 2 - NUT_CLEAR, T / 2 - NUT[0] / 2 - NUT_CLEAR]) cube([NUT[2] + 2 * NUT_CLEAR, NUT[0] + 2 * NUT_CLEAR, T]);
module nut() difference() { translate([W - NUT_SET - NUT[2], H / 2 - NUT[0] / 2, T / 2 - NUT[0] / 2]) cube([NUT[2], NUT[0], NUT[1]]);
    translate([W - NUT_SET - NUT[2] - 1, H / 2, T / 2]) rotate([0, 90, 0]) cylinder(d = 2.5, h = 5); upper_half(); }
module insert() color("#b87333") difference() { translate([W - INSERT[1], H / 2, T / 2]) rotate([0, 90, 0]) cylinder(d = 4.0, h = INSERT[1]);
    translate([W - INSERT[1] - 1, H / 2, T / 2]) rotate([0, 90, 0]) cylinder(d = 3, h = INSERT[1] + 2); upper_half(); }
module brace() mate(0.55) translate([W, H / 2 - 5.5, -3]) cube([3, 11, T + 6]);
module screw() color("#8d8d8d") difference() { translate([W + 3, H / 2, T / 2]) rotate([0, -90, 0]) { cylinder(d = 2.9, h = 11); cylinder(d = 5.6, h = 2); } upper_half(); }

if (VIEW == "today") { part() difference() { post_slice(); insert_hole(); upper_half(); } insert(); screw(); brace(); }
else { part() difference() { post_slice(); screw_hole(); pocket(); upper_half(); } changed() nut(); screw(); brace(); }
