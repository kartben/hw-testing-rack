// Review proto (not a part): a peg's plug (hexgrid.scad peg_plug) in its hole, the plate cut away round it
// (grey, translucent), seen from below.  Today: spring skins 0.7 thick over SKIN_H 2.6, their slot stopping
// 0.35 mm short of the flat's end: a 3.0 mm cantilever, 2.3 % for the nub's 0.2 mm, allowed 1.5 % for
// repeated use.  Proposed (accent: the skins): SKIN_H 3.4, the slot run to the flat's end: 3.7 mm, 1.5 %.
// docs/printed-parts-review.md › Pegs.
//
//   openscad -D 'VIEW="today"' -o peg_skin_today.png mechanical/review/proto/peg_skin.scad
include <_review.scad>
VIEW = "today";
PLATE_T = 5; HEX_AF = 7.2; HEX_U = 0.4; HEX_CLEAR = 0.1; HEX_UNDER_H = 1.4;
PLUG_AF = HEX_AF - 2 * HEX_CLEAR; PLUG_L = PLUG_AF / sqrt(3);
SKIN = 0.7; SKIN_SLOT = 0.5; NUB = 0.3; EPS = 0.01;
function hexpts(af) = [for (k = [0:5]) let (a = 90 + 60 * k) (af / sqrt(3)) * [cos(a), sin(a)]];
module hex2d(af) polygon(hexpts(af));
Z0 = -PLATE_T + 0.1;
ZL = -PLATE_T + HEX_UNDER_H; ZA = ZL + HEX_U + HEX_CLEAR - NUB;

module skin_cuts(skin_h, to_end) for (k = [0, 2, 4]) rotate(60 * k) translate([0, 0, Z0 - 1]) linear_extrude(skin_h + 1) {
    translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, -PLUG_L / 2 + (to_end ? -0.5 : 0.35)]) square([SKIN_SLOT, PLUG_L + (to_end ? 0.5 : 0)]);
    translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, PLUG_L / 2 - SKIN_SLOT]) square([SKIN + SKIN_SLOT + 1, 2]);
}
module nub(k) rotate(60 * k) translate([PLUG_AF / 2, PLUG_L / 2 - SKIN_SLOT - 0.8, 0]) rotate([90, 0, 0]) linear_extrude(1.2, center = true)
    polygon([[-EPS, Z0 + 0.05], [NUB, Z0 + 0.05 + NUB * 1.7], [NUB, ZA], [-EPS, ZA + NUB]]);
module body(skin_h, to_end) difference() { translate([0, 0, Z0]) linear_extrude(PLATE_T - 0.1 + EPS) hex2d(PLUG_AF); skin_cuts(skin_h, to_end); }
module flange() linear_extrude(1.2) circle(d = 9.6);
// a skin: the 0.7 wall left outside the slot, from the slot's start to the cross-slot, over the spring height
module skin_box(k, skin_h, to_end) rotate(60 * k) translate([PLUG_AF / 2 - SKIN, -PLUG_L / 2 + (to_end ? -0.5 : 0.35), Z0 - 0.5]) cube([SKIN + 0.5, PLUG_L - SKIN_SLOT - (to_end ? -0.5 : 0.35), skin_h + 0.5]);
module skin_piece(k, skin_h, to_end) rotate(60 * k) translate([PLUG_AF / 2 - SKIN, -PLUG_L / 2 + (to_end ? -0.5 : 0.35), Z0]) cube([SKIN, PLUG_L - SKIN_SLOT - (to_end ? -0.5 : 0.35), skin_h]);
// the plate round the hole: waist, undercut, 45° ledge (lib/hexgrid.scad hex_hole), 18 mm of plate
module plate_ring() mate(0.35) translate([0, 0, -PLATE_T]) difference() {
    translate([-9, -9, 0]) cube([18, 18, PLATE_T]);
    translate([0, 0, -1]) linear_extrude(HEX_UNDER_H + 1) hex2d(HEX_AF + 2 * HEX_U);
    hull() { translate([0, 0, HEX_UNDER_H - EPS]) linear_extrude(EPS) hex2d(HEX_AF + 2 * HEX_U); translate([0, 0, HEX_UNDER_H + HEX_U]) linear_extrude(EPS) hex2d(HEX_AF); }
    translate([0, 0, HEX_UNDER_H]) linear_extrude(PLATE_T) hex2d(HEX_AF);
}

if (VIEW == "today") { part() { body(2.6, false); for (k = [0, 2, 4]) nub(k); flange(); } plate_ring(); }
else {
    part() { difference() { body(3.4, true); for (k = [0, 2, 4]) skin_box(k, 3.4, true); } flange(); }
    changed() for (k = [0, 2, 4]) { skin_piece(k, 3.4, true); nub(k); }
    plate_ring();
}
