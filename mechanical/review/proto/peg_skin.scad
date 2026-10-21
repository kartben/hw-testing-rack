// Review proto (not a part): a peg's plug (hexgrid.scad peg_plug) seen from below, today (spring skins 0.7
// thick over SKIN_H 2.6, their slot stopping 0.35 mm short of the flat's end: a 3.0 mm cantilever, 2.3 % at
// the 0.2 mm the nub must give) and proposed (SKIN_H 3.4, the slot run to the flat's end: 3.7 mm, 1.5 %).
// docs/printed-parts-review.md › Pegs.
//
//   openscad -D 'VIEW="today"' -o peg_skin_today.png mechanical/review/proto/peg_skin.scad
VIEW = "today";
PLATE_T = 5; HEX_AF = 7.2; HEX_U = 0.4; HEX_CLEAR = 0.1; HEX_UNDER_H = 1.4;
PLUG_AF = HEX_AF - 2 * HEX_CLEAR; PLUG_L = PLUG_AF / sqrt(3);
SKIN = 0.7; SKIN_SLOT = 0.5; NUB = 0.3; EPS = 0.01;
function hexpts(af) = [for (k = [0:5]) let (a = 90 + 60 * k) (af / sqrt(3)) * [cos(a), sin(a)]];
module hex2d(af) polygon(hexpts(af));

module plug(skin_h, to_end) {
    z0 = -PLATE_T + 0.1;
    difference() {
        translate([0, 0, z0]) linear_extrude(PLATE_T - 0.1 + EPS) hex2d(PLUG_AF);
        for (k = [0, 2, 4]) rotate(60 * k) translate([0, 0, z0 - 1]) linear_extrude(skin_h + 1) {
            translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, -PLUG_L / 2 + (to_end ? -0.5 : 0.35)]) square([SKIN_SLOT, PLUG_L + (to_end ? 0.5 : 0)]);
            translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, PLUG_L / 2 - SKIN_SLOT]) square([SKIN + SKIN_SLOT + 1, 2]);
        }
    }
    zl = -PLATE_T + HEX_UNDER_H;
    za = zl + HEX_U + HEX_CLEAR - NUB;
    for (k = [0, 2, 4]) rotate(60 * k) translate([PLUG_AF / 2, PLUG_L / 2 - SKIN_SLOT - 0.8, 0])
        rotate([90, 0, 0]) linear_extrude(1.2, center = true)
            polygon([[-EPS, z0 + 0.05], [NUB, z0 + 0.05 + NUB * 1.7], [NUB, za], [-EPS, za + NUB]]);
    linear_extrude(1.2) circle(d = 9.6);        // the flange
}
color("#a9c4e4") if (VIEW == "today") plug(2.6, false); else plug(3.4, true);
