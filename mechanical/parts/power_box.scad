// Power box — the rack's 24 V supply in one printed box, in the base cell under row A.
//
//   openscad -D 'PART="base"'   -o power_box_base.stl   parts/power_box.scad
//   openscad -D 'PART="lid"'    -o power_box_lid.stl    parts/power_box.scad
//   openscad -D 'PART="cradle"' -o power_box_cradle.stl parts/power_box.scad   (for power_box.brick)
//
// Inside: a certified 24 V desktop brick (Mean Well GST60A24, power_box.brick in config/rack.yaml)
// lying in a printed cradle on the right, its IEC C14 inlet in a window of the rear wall, so the
// only mains part is the brick's own closed case; and the power hub v0.4 (eFuse per row + the rack
// controller, ESP32-S3 / CAN master) on four standoffs on the left.  The hub's 7-pin row
// connectors reach into cut-outs in the left wall, reached from the rack's left side through
// the base ladder's window; its status LEDs and USB-C look out of the front wall.
//
// The box stands inside the floor plate's tray: four sockets under its floor drop over four of
// the plate's insert bosses (an M3 through each socket screws it down if wanted).  The lid holds
// the brick down through two ribs (2 mm foam pad on the brick) and closes with 4 M3 screws into
// heat-set inserts in the walls.  The brick bay takes the largest brick listed in
// power_box.bricks: changing bricks only means printing another cradle.
//
// Box coordinates: origin at the front-left-bottom outer corner, X right, Y back, Z up.
// Print: base upright, lid top face down, cradle upright; PETG, no supports.
include <../lib/panels.scad>

PART = "base";      // base | lid | cradle | preview
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
BOX_X0 = PANEL_T + PANEL_CLEAR + PBOX_COLUMN * PANEL_PITCH + (CARRIER_W - W) / 2;   // frame position
BOX_Y0 = FRAME_ROW_Y0;
BOX_Z0 = BOSS_TOP - SOCKET[1];
GX = grid_lines(CARRIER_W);
GY = grid_lines(FLOOR_D);
// the four corner bosses under the box, in box coordinates
SOCKETS = [for (gx = [GX[0], GX[len(GX) - 1]], gy = [GY[0], GY[len(GY) - 1]])
           [gx - (CARRIER_W - W) / 2, FLOOR_Y0 + gy - BOX_Y0]];
SOCKET_PAD = [16, SOCKET[1] + 1.2];   // floor pad around a socket: Ø, thickness

// ---------------------------------------------------------------- hub v0.4 (pcb.power_hub)
HUB_FRONT_Y = T + HUB_FRONT_GAP;
function hub_xy(k) = [HUB_X0 + k[0], HUB_FRONT_Y + (HUB_SIZE[1] - k[1])];   // KiCad -> box
HUB_TOP = HUB_Z + HUB_T;
STANDOFF_D = 7;
ROW_CUT = [19, 8];                  // row connector cut-out in the left wall: width (Y), height (Z)
ROW_NAMES = ["A", "B", "C", "D"];
LED_PAIR = 5;                       // ON / FAULT spacing (the first 4 entries of HUB_LEDS are pairs)
LED_HOLE = 3.0;
LED_Z = 0.8;                        // side-view LED centre above the PCB top
USB_CUT = [9.6, 3.8, 1.6];          // as the tray fascia: width, height, centre above the PCB top

// ---------------------------------------------------------------- brick bay and cradle
CR_WALL = 1.2;
CR_FLOOR = 1.6;
CR_H = 10;                          // cradle side walls
CR_FIT = 0.4;                       // brick <-> cradle, total
CR_OUT = [PBOX_BAY[1] + CR_FIT + 2 * CR_WALL, PBOX_BAY[0] + CR_FIT / 2 + CR_WALL];   // cradle W x L
BAY_CLEAR = 0.25;
BAY = [W - T - CR_OUT[0] - 2 * BAY_CLEAR, D - T - CR_OUT[1] - BAY_CLEAR];   // bay front-left corner
BAY_RAIL = [1.2, 5];                // rails on the floor along the bay's open sides
BRICK_Z = T + CR_FLOOR;             // brick bottom
CORD_NOTCH = 12;
PAD = 2;                            // foam pad on the brick (the lid ribs press it)
C14_WIN = [36, 28];                 // rear-wall window around the C14 inlet (W x H, 45-degree roof above)

// ---------------------------------------------------------------- lid screws: bosses in the walls
LID_SCREWS = [[W - 34, 5], [74, D - 5], [5, D - 22], [W - 5, 22]];   // front, rear, left, right (insert 5 mm in)
LID_BOSS_D = 8;

module rounded(size, r = R) rbox(size, r);

module shell_2d(inset) offset(r = max(R - inset, 0.5)) offset(delta = -R) translate([inset, inset])
    square([W - 2 * inset, D - 2 * inset]);

module label(t, size = 4.5, halign = "center")
    text(t, size = size, font = "Liberation Sans:style=Bold", halign = halign, valign = "center");

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
            // lid screw bosses, merged into the walls
            intersection() {
                for (p = LID_SCREWS) translate([p[0], p[1], 0]) cylinder(d = LID_BOSS_D, h = HB);
                rounded([W, D, HB]);
            }
            // brick bay rails (the right and rear walls close the other two sides)
            translate([BAY[0] - BAY_RAIL[0], BAY[1] - BAY_RAIL[0], 0])
                cube([BAY_RAIL[0], D - T - BAY[1] + BAY_RAIL[0], T + BAY_RAIL[1]]);
            translate([BAY[0] - BAY_RAIL[0], BAY[1] - BAY_RAIL[0], 0])
                cube([W - T - BAY[0] + BAY_RAIL[0], BAY_RAIL[0], T + BAY_RAIL[1]]);
            // cable-tie bridge for the brick's DC cord, in front of the bay
            translate([BAY[0] + 14, 28, 0]) tie_bridge();
        }
        // sockets (open downwards) with an M3 clearance hole each
        for (s = SOCKETS) translate([s[0], s[1], 0]) {
            translate([0, 0, -EPS]) cylinder(d = SOCKET[0], h = SOCKET[1] + EPS);
            translate([0, 0, -EPS]) cylinder(d = M3_CLEAR, h = SOCKET_PAD[1] + 2 * EPS);
        }
        // inserts: hub standoffs, lid bosses
        for (h = HUB_HOLES) translate(concat(hub_xy(h), HUB_Z)) insert_hole();
        for (p = LID_SCREWS) translate([p[0], p[1], HB]) insert_hole();
        // floor vents under the brick
        for (i = [0 : 4]) translate([BAY[0] + 9 + i * (CR_OUT[0] - 18) / 4, BAY[1] + 22, -EPS])
            hull() for (y = [0, CR_OUT[1] - 60]) translate([0, y, 0]) cylinder(d = 5, h = T + 2 * EPS);
        left_wall_cuts();
        front_wall_cuts();
        rear_wall_cuts();
    }
}

module tie_bridge() {
    // a loop for a 3-4 mm cable tie, flat on the floor
    difference() {
        translate([-6, -3, 0]) cube([12, 6, T + 4]);
        translate([-4.5, -4, T]) cube([9, 8, 2]);
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

module front_wall_cuts() {
    // status LEDs: ON / FAULT per row, then 24V and STATUS; the controller's USB-C
    for (i = [0 : len(HUB_LEDS) - 1]) {
        x = HUB_X0 + HUB_LEDS[i];
        for (dx = i < 4 ? [-LED_PAIR / 2, LED_PAIR / 2] : [0])
            translate([x + dx, -EPS, HUB_TOP + LED_Z]) rotate([-90, 0, 0]) cylinder(d = LED_HOLE, h = T + 2 * EPS);
        // row letters and 24V below the LEDs, CTL above (no room for both below)
        translate([x, 0.6, i == 5 ? HUB_TOP + LED_Z + 5 : HUB_TOP - 5.5]) rotate([90, 0, 0]) linear_extrude(1)
            label(i < 4 ? ROW_NAMES[i] : (i == 4 ? "24V" : "CTL"), i < 4 ? 4.5 : 3.0);
    }
    translate([HUB_X0 + HUB_USB, -EPS, HUB_TOP + USB_CUT[2]]) rotate([-90, 0, 0])
        hull() for (dx = [-(USB_CUT[0] - USB_CUT[1]) / 2, (USB_CUT[0] - USB_CUT[1]) / 2])
            translate([dx, 0, 0]) cylinder(d = USB_CUT[1], h = T + 2 * EPS);
    translate([HUB_X0 + HUB_USB, 0.6, HUB_TOP - 5.5]) rotate([90, 0, 0]) linear_extrude(1) label("USB", 3.0);
    // name plate, right of the hub
    translate([(HUB_X0 + HUB_SIZE[0] + W - R) / 2 + 2, 0.6, HB * 0.62]) rotate([90, 0, 0]) linear_extrude(1)
        label("24 V", 7);
    translate([(HUB_X0 + HUB_SIZE[0] + W - R) / 2 + 2, 0.6, HB * 0.36]) rotate([90, 0, 0]) linear_extrude(1)
        label("hw-testing-rack", 3.6);
}

module rear_wall_cuts() {
    // C14 window, centred on the brick's end face, with a 45-degree roof (no bridge to print)
    cx = BAY[0] + CR_OUT[0] / 2;
    cz = BRICK_Z + PBOX_BAY[2] / 2;
    translate([cx, D - T - EPS, cz]) rotate([-90, 0, 0]) linear_extrude(T + 2 * EPS)
        polygon([[-C14_WIN[0] / 2, C14_WIN[1] / 2], [C14_WIN[0] / 2, C14_WIN[1] / 2],
                 [C14_WIN[0] / 2, -C14_WIN[1] / 2 + 4], [C14_WIN[0] / 2 - 10, -C14_WIN[1] / 2 - 6],
                 [-C14_WIN[0] / 2 + 10, -C14_WIN[1] / 2 - 6], [-C14_WIN[0] / 2, -C14_WIN[1] / 2 + 4]]);
    // vents behind the hub
    for (i = [0 : 5]) translate([12 + i * 10, D - T - EPS, 14]) rotate([-90, 0, 0])
        hull() for (z = [0, -16]) translate([0, z, 0]) cylinder(d = 4, h = T + 2 * EPS);
}

// ---------------------------------------------------------------- lid
module lid() {
    // modelled in place (box coordinates), then turned top face down for printing
    difference() {
        union() {
            translate([0, 0, HB]) rounded([W, D, LID_T]);
            // rim inside the walls
            translate([0, 0, HB - RIM[1]]) linear_extrude(RIM[1] + EPS) difference() {
                shell_2d(T + RIM_CLEAR);
                shell_2d(T + RIM_CLEAR + RIM[0]);
            }
            // ribs on the brick (through the foam pad)
            rib_z = BRICK_Z + PBOX_BAY[2] + PAD;
            for (y = [BAY[1] + 30, D - T - 30]) translate([BAY[0] + 6, y - 1.5, rib_z])
                cube([CR_OUT[0] - 12, 3, HB - rib_z + EPS]);
        }
        // the rim stays clear of the wall bosses
        for (p = LID_SCREWS) translate([p[0], p[1], HB - RIM[1] - 1]) cylinder(d = LID_BOSS_D + 2, h = RIM[1] + 1);
        for (p = LID_SCREWS) translate([p[0], p[1], HB]) screw_through(h = LID_T, counterbore = false);
        // vents over the brick
        for (i = [0 : 4]) translate([BAY[0] + 9 + i * (CR_OUT[0] - 18) / 4, BAY[1] + 40, HB - EPS])
            hull() for (y = [0, CR_OUT[1] - 75]) translate([0, y, 0]) cylinder(d = 4, h = LID_T + 2 * EPS);
    }
}

// ---------------------------------------------------------------- cradle (one per brick)
module cradle() {
    bl = PBOX_BRICK[0] + CR_FIT / 2;            // pocket, against the rear (open) end
    bw = PBOX_BRICK[1] + CR_FIT;
    py = CR_OUT[1] - bl;
    px = (CR_OUT[0] - bw) / 2;
    difference() {
        cube([CR_OUT[0], CR_OUT[1], CR_FLOOR + CR_H]);
        translate([px, py, CR_FLOOR]) cube([bw, bl + EPS, CR_H + EPS]);
        // free space in front of a shorter brick, for its DC cord's strain relief
        translate([CR_WALL, CR_WALL, CR_FLOOR]) cube([CR_OUT[0] - 2 * CR_WALL, py - CR_WALL + EPS, CR_H + EPS]);
        // cord notch in the front wall
        translate([CR_OUT[0] / 2 - CORD_NOTCH / 2, -EPS, CR_FLOOR + 2]) cube([CORD_NOTCH, CR_WALL + 2 * EPS, CR_H]);
        // floor window (air from below; clears the box's socket pads)
        translate([8, 8, -EPS]) linear_extrude(CR_FLOOR + 2 * EPS)
            offset(r = 4) offset(delta = -4) square([CR_OUT[0] - 16, CR_OUT[1] - 16]);
    }
}

// ---------------------------------------------------------------- preview: everything in place
module preview() {
    color("#4b515c") base();
    if (SHOW_LID) color("#4b515c", 0.35) lid();
    color("#e8e8ea") translate([BAY[0] + BAY_CLEAR, BAY[1], T]) cradle();
    cx = BAY[0] + BAY_CLEAR + (CR_OUT[0] - PBOX_BRICK[1]) / 2;
    color("#18181b") translate([cx, D - T - PBOX_BRICK[0], BRICK_Z]) cube([PBOX_BRICK[1], PBOX_BRICK[0], PBOX_BRICK[2]]);
    color("#1d6b3d") translate([HUB_X0, HUB_FRONT_Y, HUB_Z]) cube([HUB_SIZE[0], HUB_SIZE[1], HUB_T]);
}

if (PART == "base") base();
else if (PART == "lid") translate([0, D, HB + LID_T]) rotate([180, 0, 0]) lid();
else if (PART == "cradle") cradle();
else if (PART == "preview") preview();
