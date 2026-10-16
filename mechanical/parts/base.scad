// Power base — a closed 2020 box under the first row: bottom beams at
// z 0–20, top beams just under row A's front edge.  It houses the fanless
// Mean Well UHP-200-24 (194 × 55 × 26 mm), the Schurter DD11 C14 inlet
// (fuse + 2-pole switch) and the power-hub PCB.  Every side is closed with
// printed panels: mains is only reachable with a tool.
//
//   -D 'PART="plate"'        floor plate on the bottom beams (×4), M3 insert grid
//   -D 'PART="psu_saddle"'   PSU saddle, zip-tie or M3 strap (×2)
//   -D 'PART="inlet_panel"'  rear panel with the DD11 cut-out + Power-DIN option (×1)
//   -D 'PART="side_panel"'   left/right closure panel, vented (×2)
//   -D 'PART="front_panel"'  front closure panel, vented, logo (×4; rear blanks reuse it)
//   -D 'PART="hub_mount"'    standoff frame for the power hub PCB (×1)
//   -D 'PART="mains_cover"'  hood over the PSU AC terminals and inlet tabs (×1)
//
// Use V-0 rated PETG/ASA/PC around mains parts; never PLA.  See docs/power.md.
include <../lib/carrier.scad>

PART = "plate";
PSU = [194, 55, 26];               // Mean Well UHP-200-24
BASE_INNER_H = FRAME_BASE_H - 2 * FRAME_PROFILE;   // between the bottom and top base beams
PANEL_T = 3;
INLET_CUT = [47.1, 28.1, 1.0];     // Schurter DD11 cut-out W × H, corner radius
INLET_SCREWS = 56;                 // Ø3.4 holes, pitch
DIN_HOLE = 18.5;                   // Kycon KPJX-PM-4S panel jack (fallback brick input)
GRID = 20;

module plate() {
    difference() {
        rbox([CARRIER_W, CARRIER_D, 3], r = 3);
        for (y = [FRAME_PROFILE / 2, CARRIER_D - FRAME_PROFILE / 2], x = [26, CARRIER_W - 26])
            translate([x, y, -EPS]) rslot(12, M5_CLEAR, 4);
        for (x = [GRID : GRID : CARRIER_W - GRID / 2], y = [FRAME_PROFILE + 15 : GRID : CARRIER_D - FRAME_PROFILE - 10])
            translate([x, y, -EPS]) cylinder(d = INSERT_M3[0] - 0.6, h = 4);   // M3 self-tapping grid
        for (x = [GRID * 1.5 : GRID * 2 : CARRIER_W - GRID], y = [FRAME_PROFILE + 25 : GRID * 2 : CARRIER_D - FRAME_PROFILE - 20])
            translate([x, y, -EPS]) cylinder(d = 11, h = 4, $fn = 6);         // airflow
    }
}

module psu_saddle() {
    w = PSU[1] + 2 * 3; h = 14;
    difference() {
        translate([-w / 2, 0, 0]) cube([w, 18, h]);
        translate([-PSU[1] / 2 - 0.3, -EPS, 3]) cube([PSU[1] + 0.6, 18 + 2 * EPS, h]);
        for (x = [-w / 2 + 4, w / 2 - 4]) translate([x, 9, -EPS]) cylinder(d = M3_CLEAR, h = 4);
        // zip-tie / strap slots
        for (x = [-w / 2 - EPS, w / 2 - 3 - EPS]) translate([x, 6, 3]) cube([3 + 2 * EPS, 6, 2.5]);
    }
}

module vent_slots(w, h, margin = 10) {
    for (x = [margin : 7 : w - margin]) translate([x, -EPS, margin]) cube([2.5, PANEL_T + 2 * EPS, h - 2 * margin]);
}

module panel_blank(w, h) {
    // vertical panel in XZ, tabs top and bottom with M5 slots into the beam slots
    difference() {
        union() {
            cube([w, PANEL_T, h]);
            for (z = [-8, h]) translate([0, 0, z]) cube([w, PANEL_T, 8]);
        }
        for (x = [w * 0.25, w * 0.75], z = [-4, h + 4]) translate([x, -EPS, z]) rotate([-90, 0, 0])
            hull() for (dx = [-3, 3]) translate([dx, 0, 0]) cylinder(d = M5_CLEAR, h = PANEL_T + 1);
    }
}

module inlet_panel() {
    w = CARRIER_W; h = BASE_INNER_H;
    difference() {
        panel_blank(w, h);
        // DD11 inlet (panel is only 40 mm tall: the inlet straddles it with the top beam slot free)
        translate([w * 0.35, -EPS, h / 2]) rotate([-90, 0, 0]) {
            linear_extrude(PANEL_T + 1) offset(r = INLET_CUT[2]) square([INLET_CUT[0] - 2, INLET_CUT[1] - 2], center = true);
            for (dx = [-INLET_SCREWS / 2, INLET_SCREWS / 2]) translate([dx, 0, 0]) cylinder(d = 3.4, h = PANEL_T + 1);
        }
        // optional Power-DIN jack for the external-brick variant (knock-out: 0.6 mm skin)
        translate([w * 0.78, 0.6, h / 2]) rotate([-90, 0, 0]) cylinder(d = DIN_HOLE, h = PANEL_T);
        translate([w * 0.78, -EPS, h / 2 + 15]) rotate([90, 0, 0]) mirror([0, 0, 1])
            linear_extrude(0.6) text("24V DC", size = 4, halign = "center", font = "Liberation Sans:style=Bold");
        translate([w * 0.35, -EPS, h - 6]) rotate([90, 0, 0]) mirror([0, 0, 1])
            linear_extrude(0.6) text("100-240V~ 2A", size = 4, halign = "center", font = "Liberation Sans:style=Bold");
    }
}

module side_panel() {
    w = FRAME_D - 2 * FRAME_PROFILE; h = BASE_INNER_H;
    difference() { panel_blank(w, h); vent_slots(w, h); }
}

module front_panel() {
    w = CARRIER_W; h = BASE_INNER_H;
    difference() {
        panel_blank(w, h);
        vent_slots(w * 0.45, h);
        translate([w * 0.72, -EPS, h / 2 - 3]) rotate([90, 0, 0]) mirror([0, 0, 1])
            linear_extrude(0.8) text("hw-testing-rack", size = 6, halign = "center", font = "Liberation Sans:style=Bold");
    }
}

module hub_mount() {
    s = HUB_SIZE;
    difference() {
        union() {
            difference() {
                rbox([s[0] + 8, s[1] + 8, 3], r = 3);
                translate([10, 10, -EPS]) rbox([s[0] - 12, s[1] - 12, 4], r = 3);
            }
            for (h = HUB_HOLES) translate([h[0] + 4, s[1] - h[1] + 4, 0]) cylinder(d = 8, h = 9);
        }
        for (h = HUB_HOLES) translate([h[0] + 4, s[1] - h[1] + 4, 9]) insert_hole(INSERT_M3);
        for (x = [12, s[0] - 4], y = [6, s[1] + 2]) translate([x, y, -EPS]) cylinder(d = M3_CLEAR, h = 4);
    }
}

module mains_cover() {
    // hood over the PSU's AC terminal end: open towards the PSU body, cable gland at the rear
    w = PSU[1] + 8; d = 40; h = PSU[2] + 8;
    difference() {
        rbox([w, d, h], r = 3);
        translate([2, -EPS, -EPS]) rbox([w - 4, d - 2, h - 2], r = 2);
        translate([w / 2, d - 3, h / 2]) rotate([-90, 0, 0]) cylinder(d = 9, h = 5);   // cable entry
        for (x = [5, w - 5]) translate([x, d / 2, -EPS]) cylinder(d = M3_CLEAR, h = 4);
    }
    for (x = [0, w - 6]) translate([x, d / 2 - 6, 0]) difference() {
        cube([6, 12, 3]);
        translate([3, 6, -EPS]) cylinder(d = M3_CLEAR, h = 4);
    }
}

if (PART == "plate") plate();
else if (PART == "psu_saddle") psu_saddle();
else if (PART == "inlet_panel") rotate([90, 0, 0]) inlet_panel();
else if (PART == "side_panel") rotate([90, 0, 0]) side_panel();
else if (PART == "front_panel") rotate([90, 0, 0]) front_panel();
else if (PART == "hub_mount") hub_mount();
else if (PART == "mains_cover") rotate([180, 0, 0]) mains_cover();
