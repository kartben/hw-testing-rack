// Geometry shared by the tray, drawer, plates, chain parts and the assembly.
// All positions are in CARRIER coordinates (origin = front-left-bottom of one
// bay's tray, X right, Y towards the back, Z up) unless stated otherwise.
include <common.scad>

WALL = CARRIER_WALL;
BOSS_D = 7.5;

// ---------------------------------------------------------------- bay node PCB
// KiCad coordinates on the node (y = 0 at the REAR edge) → carrier XY.
function node_xy(k) = [NODE_X0 + k[0], NODE_FRONT_Y + (NODE_SIZE[1] - k[1])];
NODE_REAR_Y = NODE_FRONT_Y + NODE_SIZE[1];
PWR_NOTCH_Y = node_xy([0, NODE_PWR_Y])[1];        // 24 V jumper (JST PH) between neighbouring nodes

// front wall of the tray: PC/classic USB-C port, status LED window, SERVICE switch
module fascia_cutouts() {
    // [kicad_x, width, height, z above PCB top]
    cuts = [
        [NODE_FRONT[0], 9.6, 3.8, 1.6, "usbc"],    // PC / classic USB-C
        [NODE_FRONT[1], 3.2, 3.2, 0.7, "round"],   // status LED window
        [NODE_FRONT[2], 7.4, 3.0, 1.4, "rect"],    // SERVICE switch
    ];
    for (c = cuts) {
        x = NODE_X0 + c[0];
        z = NODE_PCB_TOP + c[3];
        translate([x, -EPS, z]) rotate([-90, 0, 0]) {
            if (c[4] == "usbc") hull() for (dx = [-(c[1] - c[2]) / 2, (c[1] - c[2]) / 2])
                translate([dx, 0, 0]) cylinder(d = c[2], h = CARRIER_FASCIA + 2);
            else if (c[4] == "round") cylinder(d = c[1], h = CARRIER_FASCIA + 2);
            else translate([-c[1] / 2, -c[2] / 2, 0]) cube([c[1], c[2], CARRIER_FASCIA + 2]);
        }
    }
}

// ---------------------------------------------------------------- drawer & guides
DRAWER_Y0 = 0;                                     // closed drawer front face
DRAWER_INNER_W = DRAWER_W - 2 * DRAWER_WALL;
DRAWER_PORT_WALL_Y = DRAWER_D - DRAWER_REAR_BAY;   // inner wall carrying the USB-C ports (drawer coords)
GUIDE_Y0 = DRAWER_FRONT_T + 1;
GUIDE_LIP_Z = DRAWER_FLANGE[1] + 0.4;              // lip underside above the ledge
GUIDE_LIP_T = 2.0;
GUIDE_WALL_T = DRAWER_X0 - DRAWER_FLANGE[0] - 0.5;  // solid wall of the C-channel (inner face 0.5 from the flange)
STOP_PIN_X = DRAWER_X0 - DRAWER_FLANGE[0] / 2 - 0.2; // M2.5 stop screw, in the flange path
FLANGE_Y = [DRAWER_D - 26, DRAWER_D - 6];          // rear flange segment (drawer coords)
STOP_Y = FLANGE_Y[0] - DRAWER_TRAVEL - 4.5;        // stop pin position (carrier coords)

// port wall: two positions for the panel-mount USB-C DATA socket (it goes in the one farther
// from the board's USB, so the two plugs never meet) and a slot for the optional AUX pigtail
PORT_X = concat(DATA_PORT_X, [AUX_PORT_X]);        // from config/rack.yaml (drawer.data_ports, aux_port)
PORT_Z = DRAWER_BOTTOM + 7;
PORT_EARS = 26;                                    // M3 ear pitch of common panel-mount USB-C extensions

// board plate (drops into the drawer between front panel and port wall)
PLATE_W = DRAWER_INNER_W - 0.6;
PLATE_D = DRAWER_PORT_WALL_Y - DRAWER_FRONT_T - 0.6;
PLATE_X0 = DRAWER_WALL + 0.3;                      // drawer coords
PLATE_Y0 = DRAWER_FRONT_T + 0.3;
function plate_pins() = [[10, 10], [PLATE_W - 10, PLATE_D - 10]];   // 180°-symmetric locating pins

// ---------------------------------------------------------------- drag chain
CHAIN_W = CHAIN_OUTER[0];                          // vertical extent when lying flat
CHAIN_H = CHAIN_OUTER[1];                          // horizontal extent (X) of one run
CHAIN_Z = CARRIER_BOTTOM + CHAIN_W / 2 + 0.6;      // centre line height in the plenum
CHAIN_FIXED_RUN_X = CHAIN_FIXED[0];
DECK_SLOT = [CHAIN_MOVING_X, CHAIN_FOOT_Y - DRAWER_TRAVEL - 7, CHAIN_FOOT_Y + 7];  // x, y0, y1
FOOT_HOLE = [CHAIN_MOVING_X - DRAWER_X0, CHAIN_FOOT_Y];                           // drawer coords

// ---------------------------------------------------------------- camera pod
CAM_CENTER = [CAM_MOUNT[0], CAM_MOUNT[1]];
function cam_inserts() = [for (x = [-1, 1], y = [-1, 1]) CAM_CENTER + [x, y] * CAM_MOUNT[2] / 2];
CAM_CABLE_HOLE = node_xy(NODE_CAM) + [7, 0];          // camera 5 V lead goes down here
