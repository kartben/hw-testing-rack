// Clip-in pegs for the honeycomb board plate (lib/hexgrid.scad; tools/plate_layout.py places them).
//
//   openscad -D 'PART="stop"' -D H=12 -o peg_stop_h12.stl parts/pegs.scad
//
// The stops place a board, the cams clamp it:
//   stop    an eccentric post on the plug (6 turns = 6 places in each hole): its ledge carries the PCB's
//           edge, its neck touches the edge, the 45° cone above (the lip) holds it down.  The plate's
//           layout says which turn (an arrow on the flange points to the post).  One stop between two
//           boards side by side holds both.
//   base    the cam's pivot: a column up to the PCB's underside less the cam's flange, a split pin
//   cam     on the base: a spiral (3 mm of travel), its band undercut 20° so that it presses the PCB's top
//           edge down as it closes, its flange under the edge.  Clockwise (seen from above) closes it;
//           further, it falls open.  Self-locking: the spiral rises less than friction holds
//   pin     an eccentric pin through one of the board's mounting holes, on a pad as wide as the hole's
//           copper ring (6 turns, like the stop): for a board whose edges are lined with headers
//   bobbin  the DUT cable's spare length loops round it, under its cap
// H: the board's standoff (plate top → PCB underside, boards.yaml › standoff); HOLE: a pin's hole Ø.
// Print: upright, flange down (the cam: flange down), PETG, 0.2 mm, no support; every overhang ≤ 45°
// but the flange's 1 mm rim.
include <../lib/hexgrid.scad>

PART = "stop";
H = 10;
HOLE = 3.2;
$fn = $preview ? 32 : 64;

CAM = PEG_CAM;                          // spiral r0 → r1 over arc°, its band's undercut (°)
CAM_FLANGE = 1.0;                       // under the PCB's edge
CAM_BAND = 2.0;                         // PCB_T + 0.4
CAM_GRIP = [11, 3.0, 1.8];              // the bar to turn it by
PIVOT_D = 3.4;                          // the base's pin, the cam's bore 3.6
PIVOT_HEAD = [3.9, 0.8];                // its snap head: Ø, height
CAM_RISE = 3.6;                         // the head's underside above the cam's own bottom
function spiral(r0, r1, arc, off = 0) = [for (k = [0:72]) let (t = arc * k / 72) (r0 + (r1 - r0) * k / 72 + off) * [cos(t), sin(t)]];

module arrow(l = 2.6, w = 1.8, h = 0.4) {   // engraved/raised mark, pointing +X
    linear_extrude(h) polygon([[0, -w / 2], [l, 0], [0, w / 2]]);
}

module stop(h) {
    o = stop_offset();
    peg_plug();
    difference() {
        peg_flange([o, LEDGE_D]);
        translate([-3.6, 0, FLANGE[1] - 0.4]) rotate(STOP_A) arrow();   // engraved: points to the post
    }
    translate(o) {
        cylinder(d = LEDGE_D, h = h);                                      // the ledge: the PCB rests on it
        cylinder(d = NECK_D, h = h + PCB_T + 0.1);                          // the neck: the PCB's edge touches it
        translate([0, 0, h + PCB_T + 0.1]) cylinder(d1 = NECK_D, d2 = LIP_D, h = (LIP_D - NECK_D) / 2);   // 45° lip
        translate([0, 0, h + PCB_T + 0.1 + (LIP_D - NECK_D) / 2]) cylinder(d = LIP_D, h = 0.8);
    }
}

module base(h) {
    peg_plug();
    peg_flange();
    cylinder(d1 = 8.5, d2 = 7.0, h = h - CAM_FLANGE);
    // the pivot: split so that its head snaps through the cam's bore
    difference() {
        union() {
            cylinder(d = PIVOT_D, h = h - CAM_FLANGE + CAM_RISE);
            translate([0, 0, h - CAM_FLANGE + CAM_RISE]) cylinder(d1 = PIVOT_HEAD[0], d2 = PIVOT_D - 0.6, h = PIVOT_HEAD[1]);
        }
        translate([-0.4, -5, h - CAM_FLANGE + CAM_RISE - 4.5]) cube([0.8, 10, 10]);
    }
}

module cam() {      // z = 0 on its flange's underside (the base's top)
    r0 = CAM[0]; r1 = CAM[1]; arc = CAM[2];
    grow = CAM_BAND * tan(CAM[3]);
    difference() {
        union() {
            linear_extrude(CAM_FLANGE) offset(r = 1.2) polygon(spiral(r0, r1, arc));
            translate([0, 0, CAM_FLANGE]) hull() {
                linear_extrude(EPS) polygon(spiral(r0, r1, arc));
                translate([0, 0, CAM_BAND]) linear_extrude(EPS) polygon(spiral(r0, r1, arc, grow));
            }
            translate([0, 0, CAM_FLANGE + CAM_BAND]) linear_extrude(CAM_GRIP[2])
                offset(r = 0.8) offset(delta = -0.8) square([CAM_GRIP[0], CAM_GRIP[1]], center = true);
        }
        translate([0, 0, -1]) cylinder(d = PIVOT_D + 0.2, h = 10);
        translate([0, 0, CAM_RISE - 0.1]) cylinder(d = PIVOT_HEAD[0] + 0.7, h = 3);      // the head's seat
        // "close" arrow on the grip: clockwise seen from above
        translate([CAM_GRIP[0] / 2 - 3.2, 0, CAM_FLANGE + CAM_BAND + CAM_GRIP[2] - 0.4]) rotate(-90) arrow(2.0, 1.6, 0.4 + EPS);
    }
}

module pin(h, hole) {
    o = stop_offset();
    pad = hole + 2.6;                                                      // ≈ a mounting hole's copper ring
    peg_plug();
    difference() {
        peg_flange([o, pad + 0.5]);
        translate([-3.6, 0, FLANGE[1] - 0.4]) rotate(STOP_A) arrow();
    }
    translate(o) {
        cylinder(d1 = pad + 1.5, d2 = pad, h = h);
        cylinder(d = hole - 0.3, h = h + PCB_T + 1.2);
        translate([0, 0, h + PCB_T + 1.2]) cylinder(d1 = hole - 0.3, d2 = hole - 1.1, h = 0.4);
    }
}

module bobbin() {
    peg_plug();
    peg_flange();
    translate([0, 0, FLANGE[1]]) cylinder(d1 = 9.6, d2 = 7, h = 1.3);         // flared foot
    cylinder(d = 7, h = 10);
    translate([0, 0, 10]) cylinder(d1 = 7, d2 = 15, h = 4);                   // 45° under the cap: no support
    translate([0, 0, 14]) cylinder(d = 15, h = 1.2);
    translate([0, 0, 15.2]) cylinder(d1 = 15, d2 = 13.8, h = 0.6);
}

if (PART == "stop") stop(H);
if (PART == "base") base(H);
if (PART == "cam") cam();
if (PART == "pin") pin(H, HOLE);
if (PART == "bobbin") bobbin();
