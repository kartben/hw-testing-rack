// Power box — the power hub's enclosure, in the base cell under row A.
//
//   openscad -D 'PART="base"' -o power_box_base.stl parts/power_box.scad
//   openscad -D 'PART="lid"'  -o power_box_lid.stl  parts/power_box.scad
//
// Inside: the power hub v0.5 (USB-C PD sink, an eFuse per row, the rack controller: ESP32-S3 / CAN
// master) on four standoffs.  Its USB-C PD input looks out of the rear wall: the rack's only
// supply is a USB PD 3.1 charger outside it, on a 5 A cable, so there is no mains anywhere in the
// rack.  The hub's 6-pin row connectors reach into cut-outs in the left wall (out through the base
// ladder's window); its status LEDs and console USB-C look out of the front wall.
//
// The box stands inside the floor plate's tray, against the cell's left side: sockets under its
// floor drop over the plate's insert bosses that fall under it (an M3 through each socket screws
// it down if wanted).  The lid closes with 4 M3 screws into heat-set inserts in corner lugs that
// hang above the hub (45-degree undersides: no supports).
//
// Box coordinates: origin at the front-left-bottom outer corner, X right, Y back, Z up.
// Print: base upright, lid top face down; PETG, no supports.
include <../lib/panels.scad>

PART = "base";      // base | lid | preview
SHOW_LID = false;   // preview only

W = PBOX_SIZE[0];
D = PBOX_SIZE[1];
H = PBOX_SIZE[2];
T = PBOX_WALL;                      // walls, floor and lid
R = 4;                              // outer corner radius
LID_T = T;
HB = H - LID_T;                     // base height (the lid sits on the walls)
RIM = [1.2, 3.0];                   // lid rim inside the walls: thickness, depth
RIM_CLEAR = 0.3;

// ---------------------------------------------------------------- where it stands
// The floor plate's boss grid (tray.scad, tie_plate): 30 mm pitch, centred on the plate.
function grid_lines(len) = [for (k = [-10 : 10]) let (v = len / 2 + CAM_MOUNT[2] / 2 + k * CAM_MOUNT[2])
                            if (v > 13 && v < len - 13) v];
FLOOR_Y0 = PF + 1;                  // ladder.scad
FLOOR_D = PR - 2 - FLOOR_Y0;
BOSS_TOP = CARRIER_BOTTOM + 4;      // floor plate boss top (tray.scad: tie_plate)
SOCKET = [8.3, 3.2];                // socket under the floor: Ø, depth (drops over a Ø7.5 boss)
SOCKET_PAD = [16, SOCKET[1] + 1.2];   // floor pad around a socket: Ø, thickness
BOX_X0 = PANEL_T + PANEL_CLEAR + PBOX_COLUMN * PANEL_PITCH + PBOX_X;   // frame position
BOX_Y0 = FRAME_ROW_Y0;
BOX_Z0 = BOSS_TOP - SOCKET[1];
// the bosses that fall under the box (clear of its walls), in box coordinates
GX = [for (g = grid_lines(CARRIER_W)) let (x = g - PBOX_X) if (x > SOCKET_PAD[0] / 2 + T && x < W - SOCKET_PAD[0] / 2 - T) x];
GY = [for (g = grid_lines(FLOOR_D)) let (y = FLOOR_Y0 + g - BOX_Y0) if (y > SOCKET_PAD[0] / 2 + T && y < D - SOCKET_PAD[0] / 2 - T) y];
SOCKETS = [for (gx = [GX[0], GX[len(GX) - 1]], gy = [GY[0], GY[len(GY) - 1]]) [gx, gy]];

// ---------------------------------------------------------------- hub v0.5 (pcb.power_hub)
HUB_FRONT_Y = T + HUB_FRONT_GAP;
function hub_xy(k) = [HUB_X0 + k[0], HUB_FRONT_Y + (HUB_SIZE[1] - k[1])];   // KiCad -> box
HUB_TOP = HUB_Z + HUB_T;
STANDOFF_D = 7;
ROW_CUT = [19, 8];                  // row connector cut-out in the left wall: width (Y), height (Z)
ROW_NAMES = ["A", "B", "C", "D"];
LED_PAIR = 6;                       // ON / FAULT spacing (the first 4 entries of HUB_LEDS are pairs)
LED_HOLE = 3.0;
LED_Z = 0.8;                        // side-view LED centre above the PCB top
USB_CUT = [9.6, 3.8, 1.6];          // as the tray fascia: width, height, centre above the PCB top

// ---------------------------------------------------------------- lid screws: corner lugs above the hub
LUG = [8, 4];                       // lug square (from the walls' inner faces), full-height block on top
LUG_SCREWS = [for (x = [T + LUG[0] / 2, W - T - LUG[0] / 2], y = [T + LUG[0] / 2, D - T - LUG[0] / 2]) [x, y]];
LUG_BOSS_D = 8;

module rounded(size, r = R) rbox(size, r);

module shell_2d(inset) offset(r = max(R - inset, 0.5)) offset(delta = -R) translate([inset, inset])
    square([W - 2 * inset, D - 2 * inset]);

module label(t, size = 4.5, halign = "center")
    text(t, size = size, font = "Liberation Sans:style=Bold", halign = halign, valign = "center");

// a lug in the inner corner (sx, sy: which walls), its underside at 45 degrees down to the walls
module lug(sx, sy) {
    cx = sx > 0 ? W - T : T;
    cy = sy > 0 ? D - T : T;
    hull() {
        translate([sx > 0 ? cx - LUG[0] : cx, sy > 0 ? cy - LUG[0] : cy, HB - LUG[1]]) cube([LUG[0], LUG[0], LUG[1]]);
        // a sliver in the corner, LUG[0] lower: the 45-degree underside
        translate([sx > 0 ? cx - EPS : cx, sy > 0 ? cy - EPS : cy, HB - LUG[1] - LUG[0]]) cube([EPS, EPS, EPS]);
        translate([sx > 0 ? cx - LUG[0] : cx, sy > 0 ? cy - EPS : cy, HB - LUG[1]]) cube([LUG[0], EPS, EPS]);
        translate([sx > 0 ? cx - EPS : cx, sy > 0 ? cy - LUG[0] : cy, HB - LUG[1]]) cube([EPS, LUG[0], EPS]);
    }
}

// ---------------------------------------------------------------- base
module base() {
    difference() {
        union() {
            difference() {
                rounded([W, D, HB]);
                translate([0, 0, T]) linear_extrude(HB) shell_2d(T);
            }
            // sockets' floor pads
            for (s = SOCKETS) translate([s[0], s[1], 0]) cylinder(d = SOCKET_PAD[0], h = SOCKET_PAD[1]);
            // hub standoffs
            for (h = HUB_HOLES) translate(concat(hub_xy(h), 0)) cylinder(d = STANDOFF_D, h = HUB_Z);
            // lid lugs, one per inner corner
            for (sx = [0, 1], sy = [0, 1]) lug(sx, sy);
        }
        // sockets (open downwards) with an M3 clearance hole each
        for (s = SOCKETS) translate([s[0], s[1], 0]) {
            translate([0, 0, -EPS]) cylinder(d = SOCKET[0], h = SOCKET[1] + EPS);
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = SOCKET_PAD[1] + 2 * EPS);
        }
        // inserts: hub standoffs, lid lugs
        for (h = HUB_HOLES) translate(concat(hub_xy(h), HUB_Z)) insert_hole();
        for (p = LUG_SCREWS) translate([p[0], p[1], HB]) insert_hole();
        left_wall_cuts();
        front_wall_cuts();
        rear_wall_cuts();
    }
}

module left_wall_cuts() {
    for (i = [0 : len(HUB_ROWS) - 1]) {
        y = hub_xy([0, HUB_ROWS[i]])[1];
        translate([-EPS, y - ROW_CUT[0] / 2, HUB_TOP - 0.6]) cube([T + 2 * EPS, ROW_CUT[0], ROW_CUT[1]]);
        translate([0.6, y, HUB_TOP + ROW_CUT[1] + 4]) rotate([90, 0, -90]) linear_extrude(1)
            label(ROW_NAMES[i], 5);
    }
}

module usb_cut(x, y0) {
    translate([x, y0, HUB_TOP + USB_CUT[2]]) rotate([-90, 0, 0])
        hull() for (dx = [-(USB_CUT[0] - USB_CUT[1]) / 2, (USB_CUT[0] - USB_CUT[1]) / 2])
            translate([dx, 0, 0]) cylinder(d = USB_CUT[1], h = T + 2 * EPS);
}

module front_wall_cuts() {
    // status LEDs: ON / FAULT per row, then PD (the AP33772S's own LED) and CTL; the console USB-C
    for (i = [0 : len(HUB_LEDS) - 1]) {
        x = HUB_X0 + HUB_LEDS[i];
        for (dx = i < 4 ? [-LED_PAIR / 2, LED_PAIR / 2] : [0])
            translate([x + dx, -EPS, HUB_TOP + LED_Z]) rotate([-90, 0, 0]) cylinder(d = LED_HOLE, h = T + 2 * EPS);
        // row letters and PD below the LEDs, CTL above (no room for both below)
        translate([x, 0.6, i == 5 ? HUB_TOP + LED_Z + 5 : HUB_TOP - 5.5]) rotate([90, 0, 0]) linear_extrude(1)
            label(i < 4 ? ROW_NAMES[i] : (i == 4 ? "PD" : "CTL"), i < 4 ? 4.5 : 3.0);
    }
    usb_cut(HUB_X0 + HUB_USB, -EPS);
    translate([HUB_X0 + HUB_USB, 0.6, HUB_TOP - 5.5]) rotate([90, 0, 0]) linear_extrude(1) label("USB", 3.0);
}

module rear_wall_cuts() {
    // the USB-C PD input, from the charger outside the rack
    usb_cut(HUB_X0 + HUB_PD, D - T - EPS);
    translate([HUB_X0 + HUB_PD, D - 0.6, HUB_TOP - 5.5]) rotate([90, 0, 180]) linear_extrude(1)
        label("USB-C PD", 3.0);
    // vents behind the hub's controller (the PD input's right of them)
    for (i = [0 : 3]) translate([14 + i * 9, D - T - EPS, HUB_TOP + 2.5]) rotate([-90, 0, 0])
        hull() for (z = [0, -5]) translate([0, z, 0]) cylinder(d = 3.5, h = T + 2 * EPS);
}

// ---------------------------------------------------------------- lid
module lid() {
    // modelled in place (box coordinates), then turned top face down for printing
    difference() {
        union() {
            translate([0, 0, HB]) rounded([W, D, LID_T]);
            // rim inside the walls, clear of the corner lugs
            translate([0, 0, HB - RIM[1]]) linear_extrude(RIM[1] + EPS) difference() {
                shell_2d(T + RIM_CLEAR);
                shell_2d(T + RIM_CLEAR + RIM[0]);
                for (p = LUG_SCREWS) translate(p) square(LUG[0] + 2 * RIM_CLEAR + 2, center = true);
            }
        }
        for (p = LUG_SCREWS) translate([p[0], p[1], HB]) screw_through(h = LID_T, counterbore = false);
        // vents over the PD input and the buck (rear right), and along the eFuse column
        for (i = [0 : 5]) translate([W - 30 + i * 4, D - 60, HB - EPS])
            hull() for (y = [0, 40]) translate([0, y, 0]) cylinder(d = 2.4, h = LID_T + 2 * EPS);
        // name, engraved in the top face (printed face down: the first layers)
        translate([W / 2, D / 2, HB + LID_T - 0.6]) rotate([0, 0, 90]) linear_extrude(0.6 + EPS)
            label("hw-testing-rack · power", 6);
    }
}

// ---------------------------------------------------------------- preview: everything in place
module preview() {
    color("#4b515c") base();
    if (SHOW_LID) color("#4b515c", 0.35) lid();
    color("#1d6b3d") translate([HUB_X0, HUB_FRONT_Y, HUB_Z]) cube([HUB_SIZE[0], HUB_SIZE[1], HUB_T]);
}

if (PART == "base") base();
else if (PART == "lid") translate([0, D, HB + LID_T]) rotate([180, 0, 0]) lid();
else if (PART == "preview") preview();
