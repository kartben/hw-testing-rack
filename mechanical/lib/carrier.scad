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
PWR_NOTCH_Y = node_xy([0, NODE_PWR_Y])[1];        // row cable (JST PH 6) between neighbouring nodes
NODE_RESET = [7.5, 21.5];                          // SW1 RESET, TS-1187A (KiCad, electronics/bay-node/design.py)
NODE_BOOT = [15.5, 21.5];                          // SW2 BOOT, beside it

// Opening for a USB-C plug's overmold: the USB-C stadium, scaled up.  The USB-IF reference
// overmold is at most 12.35 × 6.5 mm; this one also passes squarer overmolds (corner radius
// ≥ 2 mm).  A receptacle behind a wall's outer face needs it, not a shell-sized cut, or the
// overmold stops on the wall before the plug seats.  Width, height.
USBC_PLUG_CUT = [13.4, 7.8];
module usbc_plug_cut(h)         // centred on the plug axis, extruded along +Z
    hull() for (dx = [-1, 1] * (USBC_PLUG_CUT[0] - USBC_PLUG_CUT[1]) / 2) translate([dx, 0, 0]) cylinder(d = USBC_PLUG_CUT[1], h = h);

// front wall of the tray: PC/classic USB-C port, status LED window, SERVICE switch.  The node's
// USB-C receptacle (J3, GCT USB4105) has its face 0.275 mm proud of the PCB edge, i.e. 2.7 mm
// behind the fascia's outer face: the plug's overmold has to enter the fascia.
module fascia_cutouts() {
    // [kicad_x, width, height, z above PCB top]
    cuts = [
        [NODE_FRONT[0], 0, 0, 1.6, "usbc"],         // PC / classic USB-C (usbc_plug_cut)
        [NODE_FRONT[1], 3.2, 3.2, 0.7, "round"],   // status LED window
        [NODE_FRONT[2], 7.4, 3.0, 1.4, "rect"],    // SERVICE switch
    ];
    for (c = cuts) {
        x = NODE_X0 + c[0];
        z = NODE_PCB_TOP + c[3];
        translate([x, -EPS, z]) rotate([-90, 0, 0]) {
            if (c[4] == "usbc") usbc_plug_cut(CARRIER_FASCIA + 2);
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
// The guide lips' screws (the drawer's end stop, a sled bay's locks): PT 2.3 × 8 pan head (or M2.3 × 8
// self-tapping), [shank, the largest head, pilot, the lip's clearance hole].  Its axis keeps a Ø4.5 head
// 0.35 mm off the drawer's (sled's, block's) wall, the shank 1.6 mm into the flange path; the guide wall
// is relieved round the shank (tray.scad).  SolidCraft, 2026-10-19: a PT 2.6's Ø5 head at the old x 6.3
// overlapped the wall by 0.8 mm.
LIP_SCREW = [2.3, 4.5, 1.9, 2.6];
STOP_PIN_X = DRAWER_X0 - LIP_SCREW[1] / 2 - 0.35;  // 5.4
FLANGE_Y = [DRAWER_D - 26, DRAWER_D - 6];          // rear flange segment (drawer coords)
// A bay holds a drawer, or a sled and a port block (config/rack.yaml › population › mount): the drawer
// cut 1 mm in front of its port wall.  The sled (its front) slides on the same ledges with no chain;
// the block (its rear bay, the DATA port) is locked by two PT 2.3 × 8 through the guide lips into the
// ledges, at BLOCK_LOCK_Y; a fixed bay's sled takes two more at SLED_LOCK_Y.
SPLIT = DRAWER_D - DRAWER_REAR_BAY - DRAWER_WALL - 1;   // a sled's rear edge (drawer coords)
SLED_FLANGE_Y = [SPLIT - 24, SPLIT - 4];
BLOCK_LOCK_Y = (FLANGE_Y[0] + FLANGE_Y[1]) / 2;
SLED_LOCK_Y = (SLED_FLANGE_Y[0] + SLED_FLANGE_Y[1]) / 2;
STOP_Y = FLANGE_Y[0] - DRAWER_TRAVEL - 4.5;        // stop pin position (carrier coords)

// port wall: the DATA port and a slot for the optional AUX pigtail.  The DATA port is our own small
// board (electronics/data-port, config/rack.yaml › pcb.data_port): a USB-C source on its front edge,
// a side-entry JST PH 5 on its rear edge for the lead from the node's J7 through the drag chain.
// Components up on two bosses of the rear-bay floor, 2 × PT 2.6 × 8 from above, its front edge against
// the port wall's back face: the receptacle sits 1.7 mm behind the wall's front face, in the USB-C plug
// cut carried up through the wall's top (a U): a straight plug's overmold or a right-angle plug's body
// (19 mm tall, the wall's top only 5 mm over the axis) goes in until the plug seats.
PORT_X = concat(DATA_PORT_X, [AUX_PORT_X]);        // from config/rack.yaml (drawer.data_ports, aux_port)
PORT_Z = DRAWER_BOTTOM + 8.5;                      // the USB-C mouth's centre (tools/webscene.py mirrors it)
DATA_PCB_Z = PORT_Z - 1.63 - DATA_PCB_T;           // the board's underside (the USB4105's mouth 1.63 over its top): the bosses' top
DATA_PCB_X0 = DATA_PORT_X[0] - DATA_PCB_USB;       // drawer x of the board's left edge (KiCad x = 0)
DATA_PCB_Y0 = DRAWER_PORT_WALL_Y;                  // drawer y of its front edge: the port wall's back face

// board plate (drops into the drawer between front panel and port wall)
PLATE_W = DRAWER_INNER_W - 0.6;
PLATE_D = DRAWER_PORT_WALL_Y - DRAWER_WALL - DRAWER_FRONT_T - 0.6;   // up to the port wall's front face
PLATE_X0 = DRAWER_WALL + 0.3;                      // drawer coords
PLATE_Y0 = DRAWER_FRONT_T + 0.3;
function plate_pins() = [[10, 10], [PLATE_W - 10, PLATE_D - 10]];   // 180°-symmetric locating pins

// ---------------------------------------------------------------- drag chain
CHAIN_W = CHAIN_OUTER[0];                          // vertical extent when lying flat
CHAIN_H = CHAIN_OUTER[1];                          // horizontal extent (X) of one run
CHAIN_Z = CARRIER_BOTTOM + CHAIN_W / 2 + 0.6;      // centre line height in the plenum
CHAIN_FIXED_RUN_X = CHAIN_FIXED[0];
// End pieces: a tab flush with the outer face of the U, two holes along the chain
// (CHAIN_END_HOLES = [pitch, first hole from the mouth]).  The fixed end screws to the anchor,
// a block outside the fixed run that sits on two M3 insert bosses; the moving end to the foot.
ANCHOR = [8, 30];                                  // block X × Y
ANCHOR_X1 = CHAIN_FIXED_RUN_X - CHAIN_H / 2;       // its inner face = the fixed run's outer face
ANCHOR_Y0 = CHAIN_FIXED[1] - 6;
ANCHOR_Z0 = CARRIER_BOTTOM + 3;                    // top of the insert bosses
ANCHOR_BOSSES = [for (y = [ANCHOR_Y0 + 4, ANCHOR_Y0 + ANCHOR[1] - 4]) [ANCHOR_X1 - ANCHOR[0] / 2, y]];
// the rigid end pieces stay in straight runs over the whole stroke, and the U clears the rear wall
assert(CHAIN_BEND_Y - CHAIN_MOVING_Y >= CHAIN_END_LENGTH, "chain: the moving end piece reaches the bend (drawer closed)");
assert(CHAIN_BEND_Y - DRAWER_TRAVEL / 2 - CHAIN_FIXED[1] >= CHAIN_END_LENGTH, "chain: the fixed end piece reaches the bend (drawer open)");
assert(CHAIN_BEND_Y + CHAIN_R + CHAIN_H / 2 <= CARRIER_D - CARRIER_WALL - 1, "chain: the U bend reaches the tray's rear wall");
function chain_end_holes(mouth_y) = [for (k = [0, 1]) mouth_y + CHAIN_END_HOLES[1] + k * CHAIN_END_HOLES[0]];
DECK_SLOT = [CHAIN_MOVING_X, CHAIN_FOOT_Y - DRAWER_TRAVEL - 7, CHAIN_FOOT_Y + 7];  // x, y0, y1
FOOT_HOLE = [CHAIN_MOVING_X - DRAWER_X0, CHAIN_FOOT_Y];                           // drawer coords

// ---------------------------------------------------------------- camera pod
CAM_CENTER = [CAM_MOUNT[0], CAM_MOUNT[1]];
function cam_inserts() = [for (x = [-1, 1], y = [-1, 1]) CAM_CENTER + [x, y] * CAM_MOUNT[2] / 2];
