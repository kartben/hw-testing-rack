// Camera pod — hangs from a bay's ceiling (the bottom of the tray above, or the cap plate) and looks
// straight down at the board: an Arducam Mega 3MP SPI camera in its case (B0434, a ~120° M12 lens) and
// the pod board right behind it (electronics/camera-pod: the PH-8 lead from the bay's own node J6, the
// Mega's 3.3 V and header, four white LEDs along the edge beside the camera), so nothing is soldered.
//
//   -D 'PART="pod"'       the printed pod (dark PETG, opaque): a plate screwed to the ceiling's four
//                         camera inserts on a diagonal (2 × M3×8 from below), a sleeve the Mega's case snaps into, lens
//                         down at the lens spot, its rear wall carried down as the baffle between the
//                         LEDs and the lens, and the pod board's two standoffs behind it
//   -D 'PART="diffuser"'  white PETG: a 1 mm floor DIFF_GAP under the LEDs on two posts, which clamp the
//                         board to its standoffs (2 × PT 2.6×14 through both), open round J2's housing
//   -D 'PART="mega"', "podpcb", "podpcb_parts"   the camera and the board, for the viewer and the renders
//
// Pod frame: origin at the insert square's centre (config/rack.yaml › bay.camera_mount) on the
// ceiling's underside, x and y as the carrier's, the pod below z = 0.  The lens axis is at
// bay.camera_lens; the inserts sit right of the node above and clear of its drag chain, on the cap
// plate's 30 mm grid, so one pod fits every row.  The board: config/rack.yaml › pcb.camera_pod,
// components (LEDs) down, its LED edge (KiCad y = 0) against the baffle, KiCad x = carrier x.
// PLACEHOLDERS: the Mega's case (MEGA_*): Arducam gives 33 × 33 mm and 35 mm overall with the stock
// M12, no drawing; measure the first one (the case, the XH's side and height) before printing.
// Print: the pod upside down (the ceiling face on the bed), the diffuser floor down; no supports.
include <../lib/carrier.scad>

PART = "pod";
LENS = CAM_LENS - CAM_CENTER;           // the lens axis in the pod frame
PLATE_T = 3;
P = CAM_MOUNT[2] / 2;
PAD = P + 6;                            // the plate's half-width around the insert square

MEGA_CASE = [34, 34, 12];               // the case: x × y × height, its back against the plate (PLACEHOLDER)
MEGA_HOLDER = [14, 6];                  // the M12 holder under the case: square, height (PLACEHOLDER)
MEGA_OPTIC = [14, 9.5];                 // the ~120° lens: Ø, length out of the holder
MEGA_XH = [15, 6, 7];                   // its white XH 6-pin on the case's right side: along y, out, height (PLACEHOLDER)
// the sleeve's window on the XH's side, open from the case's face: the XH and its plug slide up through it as the
// case goes in; 3 mm wider than the XH each side and 1 mm over its top (width along y, height over the case's face)
XH_WIN = [MEGA_XH[0] + 6, (MEGA_CASE[2] + MEGA_XH[2]) / 2 + 1];
FIT = 0.3;                              // the sleeve's clearance round the case, per side
SW = 1.6;                               // the sleeve's walls
LIP = 0.8;                              // its snap lips under the case, front and rear

POD_GAP = 2;                            // the plate → the pod board's bare back
LED_H = 0.8;                            // 2835 LEDs
DIFF_GAP = 7;                           // the LEDs' face → the diffuser (5–10 mm)
DIFF_T = 1;

CASE_Z = -PLATE_T - MEGA_CASE[2];       // the case's lens face
LENS_Z = CASE_Z - MEGA_HOLDER[1] - MEGA_OPTIC[1];   // the lens tip
SLEEVE = [MEGA_CASE[0] + 2 * FIT + 2 * SW, MEGA_CASE[1] + 2 * FIT + 2 * SW];
BOARD0 = [LENS[0] - (POD_LEDS[0] + POD_LEDS[len(POD_LEDS) - 1]) / 2,   // KiCad (0, 0): the LEDs centred on
          LENS[1] + SLEEVE[1] / 2 + 0.5];                               // the lens, the LED edge at the baffle
PCB_Z = -PLATE_T - POD_GAP;             // the board's back
FACE_Z = PCB_Z - POD_PCB_T;             // its component face (down)
DIFF_Z = FACE_Z - LED_H - DIFF_GAP;     // the diffuser floor's top face
BAFFLE_Z = DIFF_Z - DIFF_T - 2;         // the baffle's bottom, below the diffuser
DIFF = [29, POD_PCB_SIZE[1] - 2];       // the diffuser floor from the board's left edge and LED edge (stops short of J1)
J2_CUT = [POD_HEADER[0] - 9.5, POD_HEADER[1] - 5, 19, 12];   // J2's Dupont housing passes: x, y, w, d (KiCad)

function board(k) = BOARD0 + k;         // KiCad → pod frame (components down, x and y as the carrier's)

module plate_2d() hull() {
    square(2 * PAD, center = true);
    translate(LENS) square(SLEEVE, center = true);
    translate(BOARD0) square(POD_PCB_SIZE);
}

module pod() {
    s = SLEEVE;
    difference() {
        union() {
            translate([0, 0, -PLATE_T]) linear_extrude(PLATE_T) offset(r = 3) offset(delta = -3) plate_2d();
            // the sleeve, its rear wall down past the diffuser: the baffle
            translate([LENS[0], LENS[1], 0]) difference() {
                union() {
                    translate([-s[0] / 2, -s[1] / 2, CASE_Z]) cube([s[0], s[1], MEGA_CASE[2] + EPS]);
                    translate([-s[0] / 2, s[1] / 2 - SW, BAFFLE_Z]) cube([s[0], SW, CASE_Z - BAFFLE_Z + EPS]);
                    // the lips under the case: the rear one on the baffle's inner face, the front one carried
                    // under its wall (it touched the wall only along an edge: a loose sliver in the print)
                    translate([-8, s[1] / 2 - SW - LIP, CASE_Z - 1.2]) cube([16, LIP, 1.2]);
                    translate([-8, -s[1] / 2, CASE_Z - 1.2]) cube([16, SW + LIP, 1.2]);
                }
                translate([-s[0] / 2 + SW, -s[1] / 2 + SW, CASE_Z - EPS]) cube([s[0] - 2 * SW, s[1] - 2 * SW, MEGA_CASE[2] + EPS]);
                // the XH's side (XH_WIN)
                translate([s[0] / 2 - SW - EPS, -XH_WIN[0] / 2, CASE_Z - EPS]) cube([SW + 2 * EPS, XH_WIN[0], XH_WIN[1] + EPS]);
            }
            for (h = POD_PCB_HOLES) translate([board(h)[0], board(h)[1], PCB_Z]) cylinder(d = 6, h = POD_GAP + EPS);
        }
        // 2 × M3×8 on a diagonal up into the ceiling's inserts (run on past them: tray.scad), heads in
        // counterbores: two screws fix a 12 g pod.  No locating rib: the pod prints ceiling face down, so
        // nothing can stand proud of that face, and the two screws already set where it sits and its turn
        for (s = [-1, 1]) translate([s * P, s * P, -PLATE_T - EPS]) {
            cylinder(d = M3_CLEAR, h = PLATE_T + 2 * EPS);
            cylinder(d = 6.2, h = 1.6);
        }
        for (h = POD_PCB_HOLES) translate([board(h)[0], board(h)[1], PCB_Z - EPS]) cylinder(d = 2.1, h = POD_GAP + PLATE_T - 0.8);
    }
}

// the diffuser: a 1 mm floor under the LED edge and the board's middle, on two posts at the board's holes
module diffuser() {
    post = FACE_Z - DIFF_Z;
    difference() {
        union() {
            translate([BOARD0[0], BOARD0[1] - 0.5, DIFF_Z - DIFF_T]) cube([DIFF[0], DIFF[1] + 0.5, DIFF_T]);
            for (h = POD_PCB_HOLES) translate([board(h)[0], board(h)[1], DIFF_Z - EPS]) cylinder(d = 5.5, h = post + EPS);
        }
        translate([board([J2_CUT[0], J2_CUT[1]])[0], board([J2_CUT[0], J2_CUT[1]])[1], DIFF_Z - DIFF_T - EPS])
            cube([J2_CUT[2], J2_CUT[3], DIFF_T + 2 * EPS]);
        for (h = POD_PCB_HOLES) translate([board(h)[0], board(h)[1], DIFF_Z - DIFF_T - EPS]) {
            cylinder(d = 2.9, h = post + DIFF_T + 2 * EPS);
            cylinder(d = 5.2, h = 1.0);
        }
    }
}

// the Mega stand-in: its case, the white XH on its right side, the M12 holder and the lens
module mega() translate([LENS[0], LENS[1], 0]) {
    translate([-MEGA_CASE[0] / 2, -MEGA_CASE[1] / 2, CASE_Z]) cube(MEGA_CASE);
    translate([MEGA_CASE[0] / 2, -MEGA_XH[0] / 2, CASE_Z + (MEGA_CASE[2] - MEGA_XH[2]) / 2]) cube([MEGA_XH[1], MEGA_XH[0], MEGA_XH[2]]);
    translate([-MEGA_HOLDER[0] / 2, -MEGA_HOLDER[0] / 2, CASE_Z - MEGA_HOLDER[1]]) cube([MEGA_HOLDER[0], MEGA_HOLDER[0], MEGA_HOLDER[1] + EPS]);
    translate([0, 0, LENS_Z]) cylinder(d = MEGA_OPTIC[0], h = MEGA_OPTIC[1] + EPS, $fn = 48);
}

// the pod board stand-in (config/rack.yaml › pcb.camera_pod): the board, then J1 and J2's housing (the viewer's
// site/camera.js draws the LEDs and their light)
module podpcb() translate([BOARD0[0], BOARD0[1], FACE_Z]) difference() {
    linear_extrude(POD_PCB_T) offset(r = 1.5) offset(delta = -1.5) square(POD_PCB_SIZE);
    for (h = POD_PCB_HOLES) translate([h[0], h[1], -1]) cylinder(d = 2.7, h = POD_PCB_T + 2);
}
module podpcb_parts() translate([BOARD0[0], BOARD0[1], FACE_Z]) {
    translate([31, POD_LEAD_Y - 10, -5.6]) cube([8.65, 20, 5.6]);                           // J1, S8B-PH-SM4-TB
    translate([POD_HEADER[0] - 7.62, POD_HEADER[1] - 2.5, -2.5]) cube([15.24, 5, 2.5]);     // J2's plastic
    translate([POD_HEADER[0] - 7.62, POD_HEADER[1] - 1.27, -2.5 - 14]) cube([15.24, 2.54, 14]);   // its Dupont housing
}

if (PART == "pod") rotate([180, 0, 0]) pod();
else if (PART == "diffuser") diffuser();
else if (PART == "podpcb") podpcb();
else if (PART == "podpcb_parts") podpcb_parts();
else mega();
