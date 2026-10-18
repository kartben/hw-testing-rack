// Power box — the power hub's enclosure, in the base cell under row A.
//
//   openscad -D 'PART="base"' -o power_box_base.stl parts/power_box.scad
//   openscad -D 'PART="lid"'  -o power_box_lid.stl  parts/power_box.scad
//   openscad -D 'PART="labels"'     -o power_box_labels.stl     parts/power_box.scad   (optional inlays)
//   openscad -D 'PART="lid_labels"' -o power_box_lid_labels.stl parts/power_box.scad
//
// Inside: the power hub v0.5 (USB-C PD sink, an eFuse per row, the rack controller: ESP32-S3 / CAN
// master) on four standoffs.  Its USB-C PD input looks out of the rear wall: the rack's only
// supply is a USB PD 3.1 charger outside it, on a 5 A cable, so there is no mains anywhere in the
// rack.  The hub's 6-pin row connectors reach into cut-outs in the left wall (out through the base
// ladder's window); its status LEDs and console USB-C look out of the front wall.
//
// The box stands inside the floor plate's tray, against the cell's left side: sockets under its
// floor drop over the plate's insert bosses that fall under it (an M3 through each socket screws
// it down if wanted).  Nothing overhangs the hub: it drops straight in.  It sits on four standoffs
// with heat-set inserts; an M3 male-female hex spacer through each of its holes holds it down, and
// the lid screws into the spacers' tops (4 × M3×6).
//
// Box coordinates: origin at the front-left-bottom outer corner, X right, Y back, Z up.
// Print: base upright, lid top face down; PETG, no supports.  The labels are engraved; the two
// *_labels parts fill the engravings exactly, flush with the faces: load each with its part as one
// object (two parts) and give it a light filament on the H2D's second nozzle, for contrast.
include <../lib/panels.scad>

PART = "base";      // base | lid | labels | lid_labels | preview
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
STANDOFF_D = 8;                     // 2 mm of wall around the Ø4 insert
SPACER = [12, 3.2];                 // M3 male-female hex spacer: length (PCB top -> lid), hex circumradius
ROW_CUT = [16, 6.6];                // row plug window in the left wall, around the 16 × 5.6 mm receptacle: width (Y), height (Z)
ROW_NAMES = ["A", "B", "C", "D"];
LED_PAIR = 6;                       // ON / FAULT spacing (the first 4 entries of HUB_LEDS are pairs)
LED_HOLE = 2.6;
LED_Z = 0.8;                        // side-view LED centre above the PCB top
// USB-C openings sized for the plug's overmold (USB-IF reference: up to 12.35 × 6.5 mm), not the
// shell: the receptacles sit 3–4 mm behind the walls' outer faces, deeper than a plug reaches
// past its overmold.  Width, height, centre above the PCB top.
USB_CUT = [12.4, 7.0, 1.6];
USB_BOTTOM = HUB_TOP + USB_CUT[2] - USB_CUT[1] / 2;
TEXT = [5.5, 0.8];                  // labels: size (cap height 5.25 mm, strokes 1.1 mm), engraving depth
assert(abs(HB - HUB_TOP - SPACER[0]) < 0.01, "the spacers must reach the lid: HB - HUB_TOP = spacer length");

// ---------------------------------------------------------------- lid screws: into the hub's spacers
LID_SCREWS = [for (h = HUB_HOLES) hub_xy(h)];

// ---------------------------------------------------------------- RESET / BOOT through the lid
// A pin (paper clip, SIM tool) goes through a hole in the lid and down a guide tube that ends just
// above the hub's top-actuated button (TS-1187A, 1.5 mm tall): the box stays closed to recover the
// controller.  The console USB-C on the front wall already flashes it with the box closed.
BUTTON_TOP = HUB_TOP + 1.5;
BUTTON_PIN = [2.2, 5.0, 1.0];       // hole Ø, guide tube OD, gap above the button
BUTTON_NAMES = ["RESET", "BOOT"];

module rounded(size, r = R) rbox(size, r);

// the outline inset by `inset`, its corners rounded to follow the outer ones (shrink and grow by
// the same radius: the flat faces stay exactly `inset` in)
module shell_2d(inset) let (rr = max(R - inset, 0.5)) offset(r = rr) offset(delta = -rr)
    translate([inset, inset]) square([W - 2 * inset, D - 2 * inset]);

module label(t, size = TEXT[0], halign = "center")
    text(t, size = size, font = "Liberation Sans:style=Bold", halign = halign, valign = "center");

// a label engraved TEXT[1] deep into a wall's outer face (p: centre, on that face; rz: 0 front,
// -90 left, 180 rear), reading left to right from outside.  inlay: exactly the engraving's volume
module engrave(t, p, rz, inlay = false) translate(p) rotate([90, 0, rz]) translate([0, 0, -TEXT[1]])
    linear_extrude(TEXT[1] + (inlay ? 0 : 1)) label(t);

// every label of the base: row letters on the left wall, the LED and port labels on the front, the
// PD input's on the rear
module base_labels(inlay = false) {
    for (i = [0 : len(HUB_ROWS) - 1])
        engrave(ROW_NAMES[i], [0, hub_xy([0, HUB_ROWS[i]])[1], (HUB_TOP - 0.6 + ROW_CUT[1] + HB) / 2], -90, inlay);
    // row letters under their LED pairs, PD over its LED, CTL under the controller's LED and USB-C
    for (i = [0 : 3]) engrave(ROW_NAMES[i], [HUB_X0 + HUB_LEDS[i], 0, USB_BOTTOM - 4], 0, inlay);
    engrave("PD", [HUB_X0 + HUB_LEDS[4], 0, HB - 3.4], 0, inlay);
    engrave("CTL", [HUB_X0 + (HUB_LEDS[5] + HUB_USB) / 2, 0, USB_BOTTOM - 4], 0, inlay);
    engrave("PD IN", [HUB_X0 + HUB_PD, D, USB_BOTTOM - 4], 180, inlay);
}

// the lid's labels, in its top face (printed face down: the first layers): its name, and RESET / BOOT
// beside their pin holes
module lid_label(inlay = false) translate([0, 0, HB + LID_T - TEXT[1]]) linear_extrude(TEXT[1] + (inlay ? 0 : EPS)) {
    translate([W / 2, D / 2 - 8]) rotate(90) label("hw-testing-rack · power", 7);
    for (i = [0 : 1]) translate(hub_xy(HUB_BUTTONS[i]) + [BUTTON_PIN[1] / 2 + 1.5, 0]) label(BUTTON_NAMES[i], halign = "left");
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
        }
        // sockets (open downwards) with an M3 clearance hole each
        for (s = SOCKETS) translate([s[0], s[1], 0]) {
            translate([0, 0, -EPS]) cylinder(d = SOCKET[0], h = SOCKET[1] + EPS);
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = SOCKET_PAD[1] + 2 * EPS);
        }
        // inserts in the hub standoffs
        for (h = HUB_HOLES) translate(concat(hub_xy(h), HUB_Z)) insert_hole();
        left_wall_cuts();
        front_wall_cuts();
        rear_wall_cuts();
        base_labels();
    }
}

module left_wall_cuts() {
    // the plug windows; each row letter goes above its window (base_labels): the base ladder's window
    // shows this wall only from 0.3 mm under the PCB up, and the windows are too close for a letter between
    for (i = [0 : len(HUB_ROWS) - 1]) {
        y = hub_xy([0, HUB_ROWS[i]])[1];
        translate([-EPS, y - ROW_CUT[0] / 2, HUB_TOP - 0.6]) cube([T + 2 * EPS, ROW_CUT[0], ROW_CUT[1]]);
    }
}

module usb_cut(x, y0) {
    translate([x, y0, HUB_TOP + USB_CUT[2]]) rotate([-90, 0, 0])
        hull() for (dx = [-(USB_CUT[0] - USB_CUT[1]) / 2, (USB_CUT[0] - USB_CUT[1]) / 2])
            translate([dx, 0, 0]) cylinder(d = USB_CUT[1], h = T + 2 * EPS);
}

module front_wall_cuts() {
    // status LEDs: ON / FAULT per row, then PD (the AP33772S's own LED) and CTL (the controller's)
    for (i = [0 : len(HUB_LEDS) - 1]) {
        x = HUB_X0 + HUB_LEDS[i];
        for (dx = i < 4 ? [-LED_PAIR / 2, LED_PAIR / 2] : [0])
            translate([x + dx, -EPS, HUB_TOP + LED_Z]) rotate([-90, 0, 0]) cylinder(d = LED_HOLE, h = T + 2 * EPS);
    }
    // the controller's console USB-C, next to its LED
    usb_cut(HUB_X0 + HUB_USB, -EPS);
}

module rear_wall_cuts() {
    // the USB-C PD input, from the charger outside the rack
    usb_cut(HUB_X0 + HUB_PD, D - T - EPS);
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
            // guide tubes down to the buttons
            for (b = HUB_BUTTONS) translate(concat(hub_xy(b), BUTTON_TOP + BUTTON_PIN[2]))
                cylinder(d = BUTTON_PIN[1], h = HB - BUTTON_TOP - BUTTON_PIN[2] + EPS);
            // rim inside the walls, notched around the spacers
            translate([0, 0, HB - RIM[1]]) linear_extrude(RIM[1] + EPS) difference() {
                shell_2d(T + RIM_CLEAR);
                shell_2d(T + RIM_CLEAR + RIM[0]);
                for (p = LID_SCREWS) translate(p) circle(r = SPACER[1] + 1.3);
            }
        }
        for (p = LID_SCREWS) translate([p[0], p[1], HB]) screw_through(h = LID_T, counterbore = false);
        // the button pin holes, through tube and lid, with a lead-in on top
        for (b = HUB_BUTTONS) translate(hub_xy(b)) {
            translate([0, 0, BUTTON_TOP]) cylinder(d = BUTTON_PIN[0], h = HB + LID_T - BUTTON_TOP + EPS);
            translate([0, 0, HB + LID_T - 0.8]) cylinder(d1 = BUTTON_PIN[0], d2 = BUTTON_PIN[0] + 1.6, h = 0.8 + EPS);
        }
        // vents over the PD input and the buck (rear right), and along the eFuse column
        for (i = [0 : 5]) translate([W - 30 + i * 4, D - 60, HB - EPS])
            hull() for (y = [0, 40]) translate([0, y, 0]) cylinder(d = 2.4, h = LID_T + 2 * EPS);
        lid_label();
    }
}

// ---------------------------------------------------------------- preview: everything in place
module preview() {
    color("#1d1f23") base();
    color("#f2f1ec") base_labels(inlay = true);
    if (SHOW_LID) color("#1d1f23", 0.35) lid();
    color("#1d6b3d") translate([HUB_X0, HUB_FRONT_Y, HUB_Z]) cube([HUB_SIZE[0], HUB_SIZE[1], HUB_T]);
    color("#c9a227") for (p = LID_SCREWS) translate([p[0], p[1], HUB_TOP]) cylinder(r = SPACER[1], h = SPACER[0], $fn = 6);
}

module lid_labels() lid_label(inlay = true);

if (PART == "base") base();
else if (PART == "lid") translate([0, D, HB + LID_T]) rotate([180, 0, 0]) lid();
else if (PART == "labels") base_labels(inlay = true);
else if (PART == "lid_labels") translate([0, D, HB + LID_T]) rotate([180, 0, 0]) lid_labels();
else if (PART == "preview") preview();
