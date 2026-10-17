// Panel frame (no aluminium): geometry shared by the ladders, trays and plates.
//
// The rack becomes a grid of printed parts:
//   * LADDERS: the side walls between bays, one per column boundary and per row, printed
//     flat.  A ladder is a frame (front post, rear post, a bottom band along the shelf slope
//     with the tray groove, a top band taking the next ladder's hooks, one brace).  Ladders
//     stack with a ridge/notch joint and in-plane snap hooks: no screws.
//   * TRAYS: the old carrier base + deck + drawer guides in one part.  Its two side walls
//     carry RUNNERS that slide into the ladders' grooves from the front; a flex arm in each
//     wall clicks a barb into a window of the groove (press it to pull the tray out).
//   * a BASE ladder (from the floor up to row A) with a floor plate, and a CAP strip on top
//     holding a cap plate (the top row's ceiling).
//
// Coordinates.  Frame: X right, Y back, Z up (as in config/rack.yaml).  Row k: origin at the
// front-bottom edge of its trays, y along the slope (back and up), z perpendicular to it.
// Ladder 2D profiles are drawn in the frame side plane: 2D x = frame Y, 2D y = frame Z; the
// part is that profile extruded PANEL_T along +z, which is also its print orientation.
include <carrier.scad>

TILT = FRAME_TILT;

PANEL_T = FRAME_PANEL_T;                 // ladder thickness (frame X), config/rack.yaml
PANEL_CLEAR = FRAME_PANEL_CLEAR;         // tray wall <-> ladder face, per side
PANEL_PITCH = BAY_PITCH;                 // 165.8: tray + ladder + 2 clearances (tools/rackcfg.py)

POST_W = 8;                             // front and rear posts (frame Y)
BAND_B = 18;                             // bottom band height (row z): the tray groove
BAND_T = 14;                             // top band height (row z): the next ladder's hooks
BRACE_W = 6;
WIN_R = 4;                               // window corner radius

PF = FRAME_ROW_Y0 - 6;                   // ladder front edge (frame Y), vertical
PR = FRAME_ROW_Y0 + CARRIER_D * cos(TILT);   // ladder rear edge

// tray runner <-> ladder groove (row z), grooves on both faces of the bottom band
RUNNER_Z = [8, 13];
GROOVE_Z = [RUNNER_Z[0] - 0.15, RUNNER_Z[1] + 0.15];
GROOVE_D = 2.4;                          // per face: leaves a 2.6 mm core
RUNNER_OUT = PANEL_CLEAR + GROOVE_D - 0.3;
RUNNER_Y0 = 4;
GROOVE_END = CARRIER_D - 2;              // closed rear end = the tray's insertion stop

// tray latch: flex arm in the side wall; barb into a window through the groove core
LATCH_Y = [110, 70];                     // barb catch face (row y): left wall, right wall
LATCH_ARM = 26;
LATCH_SLOT = 1.0;
BARB = 1.2;
LATCH_WIN = 6;

// ladder-to-ladder snap hooks, in the ladder plane, hanging from a ladder's bottom edge
HOOK_Y = [45, 165];                      // row y
HOOK_W = 2.6;                            // beam width (flex direction)
HOOK_DROP = 9;                           // below the joint
HOOK_ROOT = 7;                           // free length inside the ladder's own band
HOOK_BARB = 1.0;
HOOK_NECK = 4;                           // neck of the receiving slot
RIDGE = 2;                               // joint ridge height
RIDGE_W = PANEL_T - 2.4;                 // ridge base width (45° sides)
RIDGE_GAP = HOOK_W + 6;                  // no ridge / notch around a hook

// rear diagonal braces: an X per bay and per row, screwed behind the rear posts of its two
// ladders (M3 × 8 into heat-set inserts).  Four inserts per rear post; a brace uses the 1st and 3rd on its left ladder and
// the 2nd and 4th on its right one, so the two bays sharing a ladder never meet.
BRACE_T = 3;
XBRACE_W = 8;
BRACE_PRELOAD = 0.25;                    // each diagonal is this much shorter than its holes' spacing: taut X
BRACE_SCREW_HOLE = 3.1;                  // in the brace: an M3 screw threads in snugly, no slack
BRACE_INSERT = [INSERT_M3[0], 6.2];      // heat-set M3 insert in the ladder's rear edge: Ø × depth
function brace_z(k) = k < 0
    ? let (top = line_z(0, 0, PR)) [30, 48, top - 44, top - 26]
    : let (b = line_z(k, 0, PR), h = ROW_HEIGHTS[min(k, len(ROW_HEIGHTS) - 1)]) [b + 28, b + 46, b + h - 47, b + h - 29];

// 24 V jumper between neighbouring nodes: passes through the tray walls and the ladder
JUMPER_Y = [PWR_NOTCH_Y - 5.5, PWR_NOTCH_Y + 5.5];
JUMPER_Z0 = CARRIER_BOTTOM + CARRIER_STANDOFF;

ROW_Z0 = FRAME_BASE_H;                   // frame Z of row A's front-bottom edge
function row_z(k) = k <= 0 ? ROW_Z0 : row_z(k - 1) + ROW_HEIGHTS[min(k - 1, len(ROW_HEIGHTS) - 1)];

// frame side-plane point of row k's (y, z)
function side_pt(k, y, z) = [FRAME_ROW_Y0 + y * cos(TILT) - z * sin(TILT), row_z(k) + y * sin(TILT) + z * cos(TILT)];
// frame Z, at frame Y = Y, of the line z = d of row k
function line_z(k, d, Y) = row_z(k) + d / cos(TILT) + (Y - FRAME_ROW_Y0) * tan(TILT);
// row y of the point of the line z = d of row k at frame Y = Y
function line_y(k, d, Y) = (Y - FRAME_ROW_Y0 + d * sin(TILT)) / cos(TILT);

// quadrilateral between line (k0, d0) and line (k1, d1), from frame Y = y0 to y1
module band_quad(k0, d0, k1, d1, y0 = PF, y1 = PR)
    polygon([[y0, line_z(k0, d0, y0)], [y1, line_z(k0, d0, y1)], [y1, line_z(k1, d1, y1)], [y0, line_z(k1, d1, y0)]]);

// 2D children drawn in row-k coordinates (x = row y, y = row z) -> frame side plane
module in_row(k) translate([FRAME_ROW_Y0, row_z(k)]) rotate(TILT) children();

// 3D children in row-k coordinates (x = row y, y = row z, z = across the ladder)
module in_row3(k) translate([FRAME_ROW_Y0, row_z(k), 0]) rotate([0, 0, TILT]) children();

// vertical strip of the ladder (frame Y between PF and PR), 2D and 3D
module ladder_strip() translate([PF, -1000]) square([PR - PF, 3000]);
module ladder_strip3() translate([PF, -1000, -1]) cube([PR - PF, 3000, PANEL_T + 2]);
