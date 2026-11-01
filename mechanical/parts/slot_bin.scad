// Slot bin — a dense bay's "porte-revues": one printed part in the board plate's place (population › plate: slots).
//
//   openscad -o slot_bin.stl parts/slot_bin.scad
//
// Its boards stand on edge in six equal lanes, USB to the port wall, lane k (from the left) for the DATA ×6's port k
// (config/rack.yaml › drawer.slot_bin).  The rack's tilt slides each board forwards to the front stop; a thin one leans
// on a divider.  Behind the dividers, a cable zone where each short straight cable fans in to its port.  It sits on the
// drawer floor in the plate's footprint: the plate's locating pins into its floor, the RESET/BOOT pin holes through it,
// the display lead's notch in its front right, the ports' plugs over recesses in its rear edge.  It does not turn
// round.  Plate coords (lib/carrier.scad): origin at its front-left on the drawer floor, y to the port wall.
// Print: as it stands, PETG, 2 walls, no support.
include <../lib/carrier.scad>

FLOOR = SLOT_BIN_FLOOR;
T = SLOT_BIN_WALL;
FRONT_Y = SLOT_BIN_FRONT[0] - PLATE_Y0;           // its front stop's front face, plate y
FRONT_H = SLOT_BIN_FRONT[1];
DIV_Y1 = SLOT_BIN_DIVIDERS[0] - PLATE_Y0;         // the dividers' rear end, plate y
DIV_H = SLOT_BIN_DIVIDERS[1];
EPS = 0.01;

function button_holes() = [for (k = [NODE_RESET, NODE_BOOT]) node_xy(k) - [DRAWER_X0 + PLATE_X0, PLATE_Y0]];
WALLS_X = concat([0], [for (l = SLOT_BIN_LANES) l[1]]);   // the end walls' and dividers' left faces

module slot_bin() {
    difference() {
        union() {
            rbox([PLATE_W, PLATE_D, FLOOR], r = 3);
            translate([0, FRONT_Y, FLOOR - EPS]) cube([PLATE_W, T, FRONT_H + EPS]);
            for (x = WALLS_X) translate([x, FRONT_Y, FLOOR - EPS]) cube([T, DIV_Y1 - FRONT_Y, DIV_H + EPS]);
        }
        // the drawer's locating pins (2.2 tall) into the floor
        for (p = plate_pins()) translate([p[0], p[1], -EPS]) cylinder(d = 4.2, h = FLOOR + 1);
        // pin holes over the node's RESET and BOOT, as in the plate
        for (q = button_holes()) translate(concat(q, [-EPS])) cylinder(d = 3.2, h = FLOOR + 1);
        // the DATA ports' plugs: the plate's recesses, shallower (tools/rackcfg.py › plate_port_recesses)
        for (r = PLATE_PORT_RECESSES) translate([r[0], r[1] - EPS, FLOOR - SLOT_BIN_RECESS])
            cube([r[2] - r[0], r[3] - r[1] + 2 * EPS, SLOT_BIN_RECESS + EPS]);
        // the front display's lead drops into its front-right corner (lib/carrier.scad › PLATE_NOTCH)
        if (HAS_DISPLAY) translate([PLATE_NOTCH[0], -1, -EPS]) cube([PLATE_W, PLATE_NOTCH[1] + 1, FLOOR + 2 * EPS]);
    }
}

slot_bin();
