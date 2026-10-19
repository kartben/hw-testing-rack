// USB cable plugs, the micro-B / mini-B 90° adapters, the DATA port board and its PH plug, for the
// 3D viewer and the renders only
// (nothing here is printed).  tools/webscene.py passes the dimensions (its USB_PLUGS table, the
// single source: the cable routing uses the same numbers) and packs every piece into parts.glb.
//
//   -D 'STYLE="straight"|"right"' -D 'PIECE="mold"|"shell"' + the plug's dimensions
//   -D 'STYLE="adapter"' -D 'PIECE="mold"|"metal"'    a 90° adapter (+ AW, AD, ATOP)
//   -D 'STYLE="dataport"' -D 'PIECE="pcb"|"usb"|"ph"'  the DATA port board; STYLE="ph5" its lead's plug,
//   STYLE="ph8" the camera lead's
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

// the drawer's DATA port board (electronics/data-port, a stand-in): origin at its front-left corner on
// its bare underside, components up: x = KiCad x, y rearwards (KiCad y = BD - y), z up; the board from
// z = 0 to BT, its parts above.  BW BD BT HOLES USBX PHX from config/rack.yaml › pcb.data_port (or
// pcb.data_port_x4: NOTCH, its rear corner cut away, and PHY, the PH's mouth that far in from the rear)
BW = 40; BD = 17; BT = 1.6; HOLES = [[3, 8.5], [37.5, 4]]; USBX = 30.5; PHX = 17.5; PHN = 8; PHY = 0;
NOTCH = [0, 0, 0, 0];
module dataport_pcb() difference() {
    linear_extrude(BT) offset(r = 1.5) offset(delta = -1.5) square([BW, BD]);
    for (h = HOLES) translate([h[0], BD - h[1], -1]) cylinder(d = 2.7, h = BT + 2);
    if (NOTCH[2] > 0) translate([NOTCH[0], BD - NOTCH[1] - NOTCH[3], -1]) cube([NOTCH[2] + 1, NOTCH[3] + NOTCH[1] + 1, BT + 2]);
}
module dataport_usb() difference() {                     // GCT USB4105, its mouth on the front edge
    translate([USBX - 4.47, -0.28, BT]) cube([8.94, 7.78, 3.40]);
    translate([USBX, -0.3, BT + 1.63]) rotate([-90, 0, 0]) linear_extrude(4)
        hull() for (dx = [-1, 1] * 2.9) translate([dx, 0]) circle(d = 2.56);
}
module dataport_ph() translate([0, -PHY, 0]) difference() {   // JST S<PHN>B-PH-SM4-TB, side entry, its mouth to the rear
    w = 2 * (PHN - 1) + 6;
    union() {
        translate([PHX - w / 2, BD - 8.96, BT]) cube([w, 8.61, 5.58]);
        for (s = [-1, 1]) translate([PHX + s * (w / 2 + 0.5) - 0.5, BD - 8.96, BT]) cube([1, 3, 1.0]);
    }
    translate([PHX - w / 2 + 0.8, BD - 4, BT + 0.9]) cube([w - 1.6, 4.5, 4.0]);
}
// a JST PHR-n plug and its wires' first millimetres, in the plug frame (+z into the header)
module ph_plug(n) {
    translate([-n - 1, -2.25, -6]) cube([2 * n + 2, 4.5, 8.5]);
    for (k = [0 : n - 1]) translate([(k - (n - 1) / 2) * 2, 0, -9]) cylinder(d = 1.4, h = 3.2);
}

if (STYLE == "dataport") { if (PIECE == "pcb") dataport_pcb(); else if (PIECE == "usb") dataport_usb(); else dataport_ph(); }
else if (STYLE == "ph5") ph_plug(5);
else if (STYLE == "ph8") ph_plug(8);
else if (STYLE == "adapter") { if (PIECE == "mold") adapter_mold(); else adapter_metal(); }
else if (PIECE == "shell") shell();
else if (STYLE == "right") mold_right();
else mold_straight();
