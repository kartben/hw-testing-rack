// USB cable plugs and the drawer's panel-mount socket, for the 3D viewer and the renders only
// (nothing here is printed).  tools/webscene.py passes the dimensions (its USB_PLUGS table, the
// single source: the cable routing uses the same numbers) and packs every piece into parts.glb.
//
//   -D 'STYLE="straight"|"right"' -D 'PIECE="mold"|"shell"' + the plug's dimensions
//   -D 'STYLE="panel"' -D 'PIECE="mold"|"metal"'      the panel-mount female (QinMSY UC-138)
//
// Plug frame: +z = into the receptacle (the metal shell, z 0..SL, mostly hidden in it), x = the
// connector's width, y = its "up"; the overmold sits at z < 0.  A right-angle plug's body stands
// on the axis and its cable leaves upwards (+y), out of a tapered strain relief.
$fn = 32;

STYLE = "straight";
PIECE = "mold";
SHELL = "pill";            // pill (USB-C) | trap (micro-B, mini-B: wide side up)
SW = 8.3; SH = 2.5; SL = 6.65; SB = 0;   // shell width, height, length, trapezoid's narrow side
W = 12.4; H = 7.0; L = 20;               // overmold width, height (straight), length along the axis
D = 7.0; TOP = 15.5;                     // right-angle body: depth along the axis, top above the axis
REL = 8; RD = [5.4, 4.2];                // strain relief: length, diameters (at the body, at the cable)

module rrect(w, h, r) offset(r = r) square([w - 2 * r, h - 2 * r], center = true);

// a filleted slab: the outline `rrect(w, h, r)` from z0 to z1, edges rounded by f at both ends
module slab(w, h, r, z0, z1, f0 = 0.8, f1 = 0.8, taper = 1) {
    hull() {
        translate([0, 0, z0]) linear_extrude(0.01) rrect(w - 2 * f0, h - 2 * f0, max(r - f0, 0.3));
        translate([0, 0, z0 + f0]) linear_extrude(0.01) rrect(w, h, r);
        translate([0, 0, z1 - f1]) linear_extrude(0.01) scale(taper) rrect(w, h, r);
        translate([0, 0, z1 - 0.01]) linear_extrude(0.01) scale(taper) rrect(w - 2 * f1, h - 2 * f1, max(r - f1, 0.3));
    }
}

module relief(len, d0, d1) {                 // along +z from z = 0, with three shallow grooves
    difference() {
        cylinder(d1 = d0, d2 = d1, h = len);
        for (k = [0.35, 0.55, 0.75]) translate([0, 0, len * k]) rotate_extrude() translate([(d0 + (d1 - d0) * k) / 2, 0]) circle(d = 0.6, $fn = 8);
    }
}

module shell() {
    linear_extrude(SL) if (SHELL == "pill") hull() for (dx = [-1, 1] * (SW - SH) / 2) translate([dx, 0]) circle(d = SH);
        else polygon([[-SB / 2, -SH / 2], [SB / 2, -SH / 2], [SW / 2, SH * 0.1], [SW / 2, SH / 2], [-SW / 2, SH / 2], [-SW / 2, SH * 0.1]]);
}

module mold_straight() {
    r = min(H / 2 - 0.1, 3);
    mirror([0, 0, 1]) slab(W, H, r, 0, L, 0.6, 1.4, 0.93);              // face at z = 0, back at z = -L
    translate([0, 0, -L - REL + 0.01]) mirror([0, 0, 1]) translate([0, 0, -REL]) relief(REL, RD[0], RD[1]);
}

module mold_right() {
    r = min(D / 2 - 0.1, 3);
    hb = TOP + H / 2;                                                    // from H/2 under the axis to TOP
    translate([0, TOP - hb / 2, -D / 2]) rotate([-90, 0, 0]) slab(W, D, r, -hb / 2, hb / 2, 1.0, 1.4, 1);
    translate([0, TOP - 0.01, -D / 2]) rotate([-90, 0, 0]) relief(REL, RD[0], RD[1]);
}

// a 90° adapter (male into the board's socket, female facing up: a straight plug stands on it),
// the micro-B / mini-B boards' fix for non-reversible right-angle cables: its body is AW wide, AD
// deep along the axis, from H/2 under the axis to its female mouth ATOP above it
AW = 11.5; AD = 8; ATOP = 11.5;
module mouth(grow) {                          // the type's outline, seen from above (x wide, z thick)
    rotate([90, 0, 0]) linear_extrude(7, center = true) offset(delta = grow)
        if (SHELL == "pill") hull() for (dx = [-1, 1] * (SW - SH) / 2) translate([dx, 0]) circle(d = SH);
        else polygon([[-SB / 2, -SH / 2], [SB / 2, -SH / 2], [SW / 2, SH * 0.1], [SW / 2, SH / 2], [-SW / 2, SH / 2], [-SW / 2, SH * 0.1]]);
}
module adapter_mold() {
    hb = ATOP + H / 2;
    difference() {
        translate([0, ATOP - hb / 2, -AD / 2]) rotate([-90, 0, 0]) slab(AW, AD, 1.2, -hb / 2, hb / 2, 0.6, 0.6, 1);
        translate([0, ATOP, -AD / 2]) mouth(0.3);
    }
}
module adapter_metal() {                      // the female's shell, lining its mouth
    translate([0, ATOP - 0.6, -AD / 2]) intersection() {
        difference() { mouth(0.3); mouth(-0.1); }
        translate([-10, -1.3, -10]) cube([20, 1.2, 20]);
    }
}

// the panel-mount female end of the drawer extension: 25 mm flange with the receptacle's mouth,
// two pan-head screws 17 mm apart in front, the 20 mm body and its strain relief behind (+z)
module panel_mold() {
    difference() {
        translate([0, 0, 0]) slab(25, 9, 4.4, 0, 2.5, 0.5, 0.4);
        translate([0, 0, -0.01]) linear_extrude(1.6) hull() for (dx = [-1, 1] * 2.9) translate([dx, 0]) circle(d = 3.3);
        for (s = [-1, 1]) translate([s * 8.5, 0, -0.01]) cylinder(d = 3.2, h = 3);
    }
    slab(12.2, 6.8, 1.6, 2.5, 20, 0.2, 1.0);
    translate([0, 0, 20 - 0.01]) relief(7, 5.4, 4.4);
}
module panel_metal() {
    for (s = [-1, 1]) translate([s * 8.5, 0, 0]) difference() {
        mirror([0, 0, 1]) scale([1, 1, 0.55]) intersection() { sphere(d = 4.6); translate([0, 0, 0]) cylinder(d = 4.6, h = 3); }
        for (a = [0, 90]) rotate([0, 0, a]) translate([0, 0, -1.4]) cube([2.2, 0.5, 1.2], center = true);   // the Phillips cross
    }
    // the receptacle's shell lining the mouth
    translate([0, 0, 0.3]) linear_extrude(1.3) difference() {
        hull() for (dx = [-1, 1] * 2.9) translate([dx, 0]) circle(d = 3.3);
        hull() for (dx = [-1, 1] * 2.9) translate([dx, 0]) circle(d = 2.9);
    }
}

if (STYLE == "panel") { if (PIECE == "mold") panel_mold(); else panel_metal(); }
else if (STYLE == "adapter") { if (PIECE == "mold") adapter_mold(); else adapter_metal(); }
else if (PIECE == "shell") shell();
else if (STYLE == "right") mold_right();
else mold_straight();
