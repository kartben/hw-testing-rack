// Tier bracket — holds one row's front and rear beams at the shelf tilt.
//
// One pair per row (and one pair for the roof): the bracket bolts to the
// inner face of the front and rear corner posts (2 × M5 + drop-in T-nut each)
// and the two 2020 beams of the row butt into shallow pockets, held by an M5
// screw into each beam's tapped core.  Changing `frame.tilt` in the config
// regenerates the pockets; tilt = 0 gives a plain flat-shelf bracket.
//
//   -D 'SIDE="left"' / -D 'SIDE="right"'
// Print: flat (it is a plate), PETG/ASA, 4 walls, 40 % infill — it carries a row.
include <../lib/carrier.scad>

SIDE = "left";
PRINT = false;                               // true: lay flat for printing
T = FRAME_BRACKET;
POCKET = 3;                                  // beam pocket depth
P = FRAME_PROFILE;

// row coords (y along slope, z normal) → frame (Y, Z relative to the row origin)
function tf(p) = [FRAME_ROW_Y0 + p[0] * cos(FRAME_TILT) - p[1] * sin(FRAME_TILT),
                  p[0] * sin(FRAME_TILT) + p[1] * cos(FRAME_TILT)];
FB = tf([P / 2, P / 2]);                     // front beam centre
RB = tf([CARRIER_D - P / 2, P / 2]);         // rear beam centre
FRONT_PAD = [[0, FB[1] - 24], [P, FB[1] + 24]];
REAR_PAD = [[FRAME_D - P, RB[1] - 24], [FRAME_D, RB[1] + 24]];

module outline2d() {
    hull() {
        translate(FRONT_PAD[0]) square(FRONT_PAD[1] - FRONT_PAD[0]);
        translate(FB) rotate(FRAME_TILT) square(P + 14, center = true);
    }
    hull() {
        translate(REAR_PAD[0]) square(REAR_PAD[1] - REAR_PAD[0]);
        translate(RB) rotate(FRAME_TILT) square(P + 14, center = true);
    }
    // web between the two beams, along the slope
    hull() {
        translate(FB) rotate(FRAME_TILT) square([P, P + 14], center = true);
        translate(RB) rotate(FRAME_TILT) square([P, P + 14], center = true);
    }
}

module lightening2d() {
    // slots in the web
    for (k = [0.3, 0.5, 0.7]) translate(FB + (RB - FB) * k) rotate(FRAME_TILT) offset(r = 2) square([18, 8], center = true);
}

module bracket_left() {
    // plate in the YZ plane, X = thickness (post side at X = 0, beam side at X = T)
    difference() {
        rotate([90, 0, 90]) linear_extrude(T) difference() { outline2d(); lightening2d(); }
        // beam pockets + M5 screw into the beam core
        for (c = [FB, RB]) translate([T - POCKET, c[0], c[1]]) rotate([FRAME_TILT, 0, 0]) {
            translate([0, -P / 2 - 0.2, -P / 2 - 0.2]) cube([POCKET + EPS, P + 0.4, P + 0.4]);
            translate([-T, 0, 0]) rotate([0, 90, 0]) cylinder(d = M5_CLEAR, h = 2 * T);
            translate([-T + POCKET - EPS, 0, 0]) rotate([0, 90, 0]) cylinder(d = 9.5, h = 3.2);   // head recess
        }
        // M5 into the posts' inner slots (post side)
        for (pad = [FRONT_PAD, REAR_PAD]) for (dz = [-14, 14])
            translate([-EPS, (pad[0][0] + pad[1][0]) / 2, (pad[0][1] + pad[1][1]) / 2 + dz]) rotate([0, 90, 0]) {
                cylinder(d = M5_CLEAR, h = T + 2 * EPS);
                translate([0, 0, T - 3.2]) cylinder(d = 9.5, h = 3.2 + 2 * EPS);
            }
    }
}

module bracket() { if (SIDE == "left") bracket_left(); else mirror([1, 0, 0]) bracket_left(); }
if (PRINT) rotate([0, SIDE == "left" ? -90 : 90, 0]) bracket(); else bracket();
