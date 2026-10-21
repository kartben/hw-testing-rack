// The board plate's honeycomb and the plug every peg clips into it with (config/rack.yaml › plate_grid,
// generated/config.scad › HEX_*, PEG_*).  The clip stays inside the plate: a hole is HEX_AF across flats
// at its waist, wider by HEX_U per side over its bottom HEX_UNDER_H, with a 45° ledge between the two; a
// peg's plug has three spring skins (openGrid-style: each a cantilever along one flat, freed by a slot, so
// it bends in the print plane, not across layers) whose nubs snap under that ledge.  Nothing comes out
// under the plate: the drawer's floor, its magnet and the drag chain below never see a peg.
include <common.scad>

HEX_UNDER_H = 1.4;                  // the undercut's height, from the plate's bottom
HEX_LEADIN = 0.4;                   // the top edge's 45° lead-in
PLUG_AF = HEX_AF - 2 * HEX_CLEAR;   // a plug across flats
PLUG_L = PLUG_AF / sqrt(3);         // one of its flats
SKIN = 0.7;                         // a spring skin's thickness
SKIN_SLOT = 0.5;                    // the slot behind it
SKIN_H = 3.4;                       // the spring zone, from the plug's bottom up
SKIN_ROOT = 0.15;                   // the slot runs this far past the flat's corner: 3.7 free, 1.5 % (printed-parts-review)
NUB = 0.3;                          // a nub's reach past its flat: 0.2 over the waist going in, 0.2 under the ledge
FLANGE = [9.6, 1.2];                // the plug's flange on the plate's top: Ø, thickness
PCB_T = 1.6;                        // the boards' thickness the lips and cams are cut for

// stop and pin: the post's offset from the plug's axis, at `angle` from a flat's normal; 6 turns
STOP_E = PEG_STOP[0];
STOP_A = PEG_STOP[1];
NECK_D = PEG_STOP[2];
LEDGE_D = PEG_STOP[3];
LIP_D = PEG_STOP[4];
function stop_offset() = STOP_E * [cos(STOP_A), sin(STOP_A)];

function hexpts(af) = [for (k = [0:5]) let (a = 90 + 60 * k) (af / sqrt(3)) * [cos(a), sin(a)]];
module hex2d(af) polygon(hexpts(af));          // flats facing ±X (and ±60°), corners ±Y

// one hole's cutter, z = 0 on the plate's bottom
module hex_hole(t = PLATE_T) {
    translate([0, 0, -1]) linear_extrude(HEX_UNDER_H + 1) hex2d(HEX_AF + 2 * HEX_U);
    hull() {                                    // the 45° ledge the nubs catch
        translate([0, 0, HEX_UNDER_H - EPS]) linear_extrude(EPS) hex2d(HEX_AF + 2 * HEX_U);
        translate([0, 0, HEX_UNDER_H + HEX_U]) linear_extrude(EPS) hex2d(HEX_AF);
    }
    translate([0, 0, HEX_UNDER_H]) linear_extrude(t) hex2d(HEX_AF);
    hull() {                                    // lead-in
        translate([0, 0, t - HEX_LEADIN]) linear_extrude(EPS) hex2d(HEX_AF);
        translate([0, 0, t]) linear_extrude(1) hex2d(HEX_AF + 2 * HEX_LEADIN);
    }
}

// a peg's plug, z = 0 on the plate's top (the flange sits there), going down to 0.1 above the plate's bottom
module peg_plug() {
    z0 = -PLATE_T + 0.1;
    difference() {
        translate([0, 0, z0]) linear_extrude(PLATE_T - 0.1 + EPS) hex2d(PLUG_AF);
        // three skins, on the flats at 0°, 120°, 240°: a slot behind each, open at its free end, run to the
        // flat's far corner (and SKIN_ROOT past it: the plug's next flat still closes it)
        for (k = [0, 2, 4]) rotate(60 * k) translate([0, 0, z0 - 1]) linear_extrude(SKIN_H + 1) {
            translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, -PLUG_L / 2 - SKIN_ROOT]) square([SKIN_SLOT, PLUG_L + SKIN_ROOT]);
            translate([PLUG_AF / 2 - SKIN - SKIN_SLOT, PLUG_L / 2 - SKIN_SLOT]) square([SKIN + SKIN_SLOT + 1, 2]);
        }
    }
    // the nubs, near each skin's free end: a 30° lead-in below, and a 45° top on the hole's ledge when the
    // flange sits on the plate (the ledge's foot at zl, its face 1:1; the nub's corner HEX_U + HEX_CLEAR
    // - NUB inside the undercut's wall, so that much above the foot)
    zl = -PLATE_T + HEX_UNDER_H;
    za = zl + HEX_U + HEX_CLEAR - NUB;
    for (k = [0, 2, 4]) rotate(60 * k) translate([PLUG_AF / 2, PLUG_L / 2 - SKIN_SLOT - 0.8, 0])
        rotate([90, 0, 0]) linear_extrude(1.2, center = true)
            polygon([[-EPS, z0 + 0.05], [NUB, z0 + 0.05 + NUB * 1.7], [NUB, za], [-EPS, za + NUB]]);
}

module peg_flange(extra = undef) {              // on the plate's top; `extra`: a second circle to hull with
    linear_extrude(FLANGE[1]) hull() {
        circle(d = FLANGE[0]);
        if (extra != undef) translate(extra[0]) circle(d = extra[1]);
    }
}
