// Geometry shared by the carrier, deck, drawer, plates, chain parts and the assembly.
// All positions are in CARRIER coordinates (origin = front-left-bottom of one
// bay's carrier, X right, Y towards the back, Z up) unless stated otherwise.
include <common.scad>

WALL = CARRIER_WALL;
BOSS_D = 7.5;

// ---------------------------------------------------------------- bay node PCB
// KiCad coordinates on the node (y = 0 at the REAR edge) → carrier XY.
function node_xy(k) = [NODE_X0 + k[0], NODE_FRONT_Y + (NODE_SIZE[1] - k[1])];
NODE_REAR_Y = NODE_FRONT_Y + NODE_SIZE[1];
PWR_NOTCH_Y = node_xy([0, NODE_PWR_Y])[1];        // 24 V jumper (JST PH) between neighbouring nodes

// ---------------------------------------------------------------- deck fixings
// Side screws go guide → deck → base wall boss (one screw holds all three).
GUIDE_SCREW_X = 2.8;
function side_screws() = [for (y = [30, 105, 185]) for (x = [GUIDE_SCREW_X, CARRIER_W - GUIDE_SCREW_X]) [x, y]];
// Free-standing pillars under the deck middle (clear of the node and the chain).
function deck_pillars() = [[40, 165], [82, 165], [125, 75]];

// ---------------------------------------------------------------- drawer & guides
DRAWER_Y0 = 0;                                     // closed drawer front face
DRAWER_INNER_W = DRAWER_W - 2 * DRAWER_WALL;
DRAWER_PORT_WALL_Y = DRAWER_D - DRAWER_REAR_BAY;   // inner wall carrying the USB-C ports (drawer coords)
GUIDE_Y0 = DRAWER_FRONT_T + 1;
GUIDE_LIP_Z = DRAWER_FLANGE[1] + 0.4;              // lip underside above the deck
GUIDE_LIP_T = 2.0;
GUIDE_WALL_T = DRAWER_X0 - DRAWER_FLANGE[0] - 0.5;  // solid wall of the C-channel (inner face 0.5 from the flange)
STOP_PIN_X = DRAWER_X0 - DRAWER_FLANGE[0] / 2 - 0.2; // M2.5 stop screw, in the flange path
FLANGE_Y = [DRAWER_D - 26, DRAWER_D - 6];          // rear flange segment (drawer coords)
STOP_Y = FLANGE_Y[0] - DRAWER_TRAVEL - 4.5;        // stop pin position (carrier coords)
DETENT_DRAWER = [22, DRAWER_D - 14];               // magnet in drawer bottom (drawer coords)
DETENT_DECK = [DRAWER_X0 + DETENT_DRAWER[0], DETENT_DRAWER[1]];

// port wall: two positions for the panel-mount USB-C DATA socket (it goes in the one farther
// from the board's USB, so the two plugs never meet) and a slot for the optional AUX pigtail
PORT_X = concat(DATA_PORT_X, [AUX_PORT_X]);        // from config/rack.yaml (drawer.data_ports, aux_port)
PORT_Z = DRAWER_BOTTOM + 7;
PORT_EARS = 26;                                    // M3 ear pitch of common panel-mount USB-C extensions

// drawer width for a bay spanning `span` units (wide bays share the node of their left unit)
function drawer_w(span) = span * BAY_PITCH - BAY_GAP - 2 * DRAWER_GUIDE_W - 2 * DRAWER_CLEAR;

// board plate (drops into the drawer between front panel and port wall)
function plate_w(span) = drawer_w(span) - 2 * DRAWER_WALL - 0.6;
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
