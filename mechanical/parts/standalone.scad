// Standalone bays (docs/standalone.md): one bay out of the rack, on a desk.  The boards are the rack's own, as they
// are: the bay node, the single DATA port board or the DATA ×4 v2.  A bought USB-C PD trigger module fixed at 20 V
// (config/rack.yaml › standalone.pd_module) feeds the node's J1 in place of the power hub.
//
//   -D 'PART="solo_base"' / "solo_lid"     Solo: the node on four insert bosses, the single DATA port board hung
//                                          under the lid over the node's front right (USB-C is reversible)
//   -D 'PART="quad_base"' / "quad_shelf" / "quad_lid"   Quad: the DATA ×4 v2 standing behind the front face in two
//                                          side slots, the node on a shelf over it
//   -D 'PART="desk_frame"'                 the honeycomb plate's desk frame: the rack's plate drops in (on its two
//                                          pins), and the box's two front feet drop into the dock behind it
//   "<part>_in_place": where it sits (the checks, the renders); the lids print top face down.
//
// Box frame: x right, y towards the back (0 = the front face), z up (0 = the underside; the rubber feet below it).
// Front: the node's PC port, SERVICE switch and status window, as on the tray's fascia, and the DUT port(s).
// Rear: the PD module's USB-C; the wall thinned to 1.2 over the node's antenna.  Lid: RESET / BOOT pin holes over
// guide tubes, a window over J6 (the camera lead plugs in from above), vents over the node's buck.
// Print: bases upright, lids top face down, the shelf and the frame flat; PETG, no supports (docs/mechanical.md ›
// Printing).  4 × M3 × 8 into heat-set inserts hold each lid, as many the node.
include <../lib/carrier.scad>

PART = "solo_base";

T = 2;                                     // walls
FL = 2;                                    // floors
LID_T = 2;
R = VL_R[0];
CH = VL_CHAMFER;
STAND = 6;                                 // the node's bosses over the floor (an M3 insert, 5.7 deep)
LID_SCREW = [9, 2.5];                      // the lid's screw bosses under it: Ø, depth (the pan head's counterbore)

// ---------------------------------------------------------------- shared
module rr(s, r = R) offset(r = r) offset(delta = -r) square(s);
// a block with R3 vertical edges, `cb` × 45° round its bed edge, `ct` round its top edge
module vl_block(s, cb = CH, ct = 0, r = R) hull() {
    translate([cb, cb, 0]) linear_extrude(EPS) rr([s[0] - 2 * cb, s[1] - 2 * cb], r - cb);
    translate([0, 0, cb]) linear_extrude(s[2] - cb - ct) rr([s[0], s[1]], r);
    if (ct > 0) translate([ct, ct, s[2] - EPS]) linear_extrude(EPS) rr([s[0] - 2 * ct, s[1] - 2 * ct], r - ct);
}
// the open box: walls and floor, its top at h
module shell(w, d, h) difference() {
    vl_block([w, d, h]);
    translate([T, T, FL]) cube([w - 2 * T, d - 2 * T, h]);
}
function nk(k, x0, y0) = [x0 + k[0], y0 + NODE_SIZE[1] - k[1]];   // the node's KiCad xy → box xy
module node_bosses(x0, y0) for (h = NODE_HOLES) translate(concat(nk(h, x0, y0), FL - EPS)) difference() {
    cylinder(d = BOSS_D, h = STAND + EPS);                                  // as the tray's standoffs
    translate([0, 0, STAND + EPS]) insert_hole(INSERT_M3);
}
// the node's front edge, as the tray's fascia (lib/carrier.scad › fascia_cutouts): its PC port (the USB-C stadium,
// so an overmold passes), the status LED's window, the SERVICE switch's slot; `top`: the node's PCB top
module node_front(x0, top) {
    translate([x0 + NODE_FRONT[0], -EPS, top + 1.6]) rotate([-90, 0, 0]) usbc_plug_cut(T + 2);
    translate([x0 + NODE_FRONT[1], -EPS, top + 0.7]) rotate([-90, 0, 0]) cylinder(d = 3.2, h = T + 2);
    translate([x0 + NODE_FRONT[2] - 3.7, -EPS, top + 1.4 - 1.5]) cube([7.4, T + 2, 3]);
}
module usbc_front(x, z) translate([x, -EPS, z]) rotate([-90, 0, 0]) usbc_plug_cut(T + 2);
module feet_pockets(w, d) for (x = [12, w - 12], y = [12, d - 12])       // 0.5 deep: they only locate the bumpers
    translate([x, y, -EPS]) cylinder(d = SA_FEET[0] + 0.6, h = FEET_SET + EPS);
FEET_SET = 0.5;                            // so the box's underside stands SA_FEET[1] - FEET_SET over the desk
// the lid's four M3 × 8: the base's corner bosses take the inserts (Ø7.5, 0.25 into the walls)
module lid_bosses(ps, zl) for (p = ps) translate([p[0], p[1], FL - EPS]) difference() {
    cylinder(d = 7.5, h = zl - LID_SCREW[1] - FL + EPS);
    translate([0, 0, zl - LID_SCREW[1] - FL + EPS]) insert_hole(INSERT_M3, runout = 1);
}
// the lid: a plate on the walls, a locating rim inside them, screw bosses, RESET / BOOT guide tubes down to 1 mm over
// the node's buttons (`btn`: their xy, `top`: the node's PCB top), vents and the window over J6
module lid(w, d, zl, ps, btn, top, vents, cam) difference() {
    union() {
        translate([0, 0, zl]) vl_block([w, d, LID_T], cb = 0, ct = CH);
        translate([0, 0, zl - 2]) difference() {
            translate([T + 0.2, T + 0.2, 0]) cube([w - 2 * T - 0.4, d - 2 * T - 0.4, 2 + EPS]);
            translate([T + 1.4, T + 1.4, -EPS]) cube([w - 2 * T - 2.8, d - 2 * T - 2.8, 3]);
        }
        for (p = ps) translate([p[0], p[1], zl - LID_SCREW[1]]) cylinder(d = LID_SCREW[0], h = LID_SCREW[1] + EPS);
        for (b = btn) translate([b[0], b[1], top + 2.5]) cylinder(d = 4.4, h = zl - top - 2.5 + EPS);
        children();
    }
    for (p = ps) translate([p[0], p[1], zl - LID_SCREW[1] - 1]) {
        cylinder(d = M3_CLEAR, h = 10);
        translate([0, 0, 1 + LID_SCREW[1] + LID_T - 2.4]) cylinder(d = 6.2, h = 5);
    }
    for (b = btn) translate([b[0], b[1], top]) cylinder(d = 1.8, h = 50);
    for (v = vents) translate([v[0], v[1], zl - 1]) cube([2, v[2], LID_T + 2]);
    translate([cam[0] - 4.5, cam[1] - 12, zl - 3]) cube([9, 24, LID_T + 4]);
}
// the PD module (config/rack.yaml › standalone.pd_module): its PCB's edge against the rear wall's inner face, its
// seat on the floor, a fence round its sides and far end (the plug's push), a 1 mm double-sided foam pad under it.
// In the rear wall: a collar round its USB-C's shell (the inner 0.6, it centres the receptacle whatever the board),
// the overmold's cut through the outer 1.4 (a receptacle 0.6–2 mm proud of its PCB's edge).
// `xc`: its axis; `d`: the box's depth; `zb`: the board's underside
PD_FOAM = 1.0;
PD_COLLAR = 0.6;
function pd_far(d) = d - T - SA_PD[0];     // the board's far end
module pd_seat(xc, d, zb) {
    y0 = pd_far(d) - 1.5;
    w = SA_PD[1] + 0.6;
    difference() {
        translate([xc - w / 2 - 1.2, y0, FL - EPS]) cube([w + 2.4, d - T - y0 + EPS, zb + SA_PD[2] + 0.6 - FL + EPS]);
        translate([xc - w / 2, y0 + 1.2, zb - PD_FOAM]) cube([w, d, 20]);
        // under the board's middle: room for a mid-mount receptacle's shell and the parts underneath
        translate([xc - w / 2 + 2, y0 + 3, FL]) cube([w - 4, d, 20]);
    }
}
module pd_cut(xc, d, zb) translate([xc, d - T - EPS, zb + SA_PD[3]]) {
    translate([-4.65, 0, -1.8]) cube([9.3, T + 2 * EPS, 3.6]);                               // the collar (the shell)
    translate([0, PD_COLLAR, 0]) rotate([-90, 0, 0]) usbc_plug_cut(T);                     // the overmold
}
// a recess for the unit's name (9 mm tape, or a printed inlay as the drawer's bay label), its ceiling at 45°
module name_recess(x, z, w = 24, h = 9.4) translate([x, -EPS, z]) hull() {
    cube([w, EPS, h + 0.6]);
    cube([w, 0.6 + EPS, h]);
}

// ---------------------------------------------------------------- Solo
S_W = 106;  S_D = 95.5;  S_H = 31.1;
S_ZL = S_H - LID_T;                        // the lid's underside
S_NX = 17.5;  S_NY = 2.5;  S_NZ = FL + STAND;      // the node: left edge, front edge, underside
S_NTOP = S_NZ + NODE_T;
S_DX = 55.5;  S_DC = 21.5;                 // the DATA board, hung: left edge (turned over), its component face (down)
S_DUSB = [S_DX + DATA_PCB_SIZE[0] - DATA_PCB_USB, S_DC - 1.63];   // its USB-C's axis
S_LIDS = [[5.5, 5.5], [S_W - 5.5, 5.5], [5.5, 45], [S_W - 5.5, S_D - 5.5]];
S_PDX = 9.8;  S_PDZ = FL + 4;              // the PD module: axis (its seat 0.2 off the node's rear-left boss), underside
S_BTN = [nk(NODE_RESET, S_NX, S_NY), nk(NODE_BOOT, S_NX, S_NY)];
S_ANT = [S_NX + 21, S_NX + 43];            // the node's antenna (its WROOM-1's rear end), x

module solo_base() difference() {
    union() {
        shell(S_W, S_D, S_ZL);
        node_bosses(S_NX, S_NY);
        lid_bosses(S_LIDS, S_ZL);
        pd_seat(S_PDX, S_D, S_PDZ);
    }
    node_front(S_NX, S_NTOP);
    usbc_front(S_DUSB[0], S_DUSB[1]);
    name_recess(78, 6);
    pd_cut(S_PDX, S_D, S_PDZ);
    translate([S_ANT[0], S_D - T - EPS, FL + 4]) cube([S_ANT[1] - S_ANT[0], 0.8 + EPS, S_ZL]);   // 1.2 over the antenna
    // AUX (J5): a lead's slot at the right wall's top edge
    translate([S_W - T - 1, nk(NODE_AUX, S_NX, S_NY)[1] - 4, S_ZL - 3.5]) cube([T + 2, 8, 3.5 + EPS]);
    // floor vents under the node's middle; the feet
    for (y = [24 : 6 : 60]) translate([S_NX + 26, y, -EPS]) cube([24, 2.5, FL + 2 * EPS]);
    feet_pockets(S_W, S_D);
}
module solo_lid() lid(S_W, S_D, S_ZL, S_LIDS, S_BTN, S_NTOP,
        [for (x = [S_NX + 2 : 4 : S_NX + 22]) [x, 22, 34]], nk(NODE_CAM, S_NX, S_NY))
    // the DATA board's two bosses: PT 2.3 × 8 up through the board (turned over, its holes mirrored in x)
    for (h = DATA_PCB_HOLES) translate([S_DX + DATA_PCB_SIZE[0] - h[0], S_NY + DATA_PCB_SIZE[1] - h[1], S_DC + DATA_PCB_T])
        difference() {
            cylinder(d = 6, h = S_ZL - S_DC - DATA_PCB_T + EPS);
            translate([0, 0, -EPS]) cylinder(d = PT_PILOT, h = 6.5);
        }

// ---------------------------------------------------------------- Quad
// the DATA ×4 v2 (config/rack.yaml › pcb.data_port_x4_v2; x4_cradle.scad): 100 × 70 × 1.6, its four USB-C on its
// front face (mouths 6.4 off it), 2 × 6 headers at 26 over its bottom edge, VBUS LEDs at 33, D1, J1 on its rear face
V2 = [100, 70, 1.6];
V2_USB = [22, 40, 58, 76];  V2_USB_Z = 8.5;  V2_HDR_Z = 26;  V2_LED_Z = 33;  V2_D1 = [55.4, 67.6];
Q_W = 107;  Q_D = 95.5;
Q_VX = 3.5;  Q_VY = T + 1 + 6.4;  Q_VZ = FL;       // the v2: left end, front face (mouths 1 mm behind the wall), bottom
Q_SLOT = [V2[2] + 0.3, 4];                // its ends' slots: width, depth
Q_SHELF = [Q_VZ + V2[1] + 0.5, 2];        // the node's shelf: underside, thickness
Q_NX = 14;  Q_NY = 2.5;  Q_NZ = Q_SHELF[0] + Q_SHELF[1] + 4.5;   // the node on 4.5 mm bosses (6.5 for the insert)
Q_NTOP = Q_NZ + NODE_T;
Q_H = Q_NZ + 11.6 + 1 + LID_T;            // 1 mm over C1, the node's tallest part
Q_ZL = Q_H - LID_T;
Q_LIDS = [[5.5, 5.2], [Q_W - 5.5, 5.2], [5.5, Q_D - 5.5], [Q_W - 5.5, Q_D - 5.5]];   // the front pair 0.3 clear of the v2's slots
Q_PDX = 17.5;  Q_PDZ = FL + 4;
Q_BTN = [nk(NODE_RESET, Q_NX, Q_NY), nk(NODE_BOOT, Q_NX, Q_NY)];
Q_ANT = [Q_NX + 21, Q_NX + 43];
Q_RAIL = [Q_VX + Q_SLOT[1] - T, Q_VY - 2.5, 6.6];   // the slots' rails: width (from the wall), front, depth (y)

module quad_base() difference() {
    union() {
        shell(Q_W, Q_D, Q_ZL);
        // the v2's two rails, floor to the shelf, each with a slot for the board's end
        for (x = [T - EPS, Q_W - T - Q_RAIL[0]]) translate([x, Q_RAIL[1], FL - EPS])
            cube([Q_RAIL[0] + EPS, Q_RAIL[2], Q_SHELF[0] - FL + EPS]);
        // the shelf's ledges along the side walls, 45° under them
        for (s = [0, 1]) translate([s == 0 ? T - EPS : Q_W - T + EPS, Q_VY + 6, Q_SHELF[0]]) mirror([s, 0, 0])
            rotate([-90, 0, 0]) linear_extrude(Q_D - T - 10 - Q_VY - 6) polygon([[0, 0], [4, 0], [0, 4]]);
        lid_bosses(Q_LIDS, Q_ZL);
        pd_seat(Q_PDX, Q_D, Q_PDZ);
    }
    for (x = [Q_VX - 0.15, Q_VX + V2[0] - Q_SLOT[1] - 0.5]) translate([x, Q_VY - 0.15, FL + EPS]) cube([Q_SLOT[1] + 0.65, Q_SLOT[0], Q_SHELF[0]]);
    // front: the four DUT ports, a window over each header (its Dupont housing plugs in through it), the LEDs'
    // windows, the port numbers; the node's row at the top, the name
    for (k = [0 : 3]) {
        x = Q_VX + V2_USB[k];
        usbc_front(x, Q_VZ + V2_USB_Z);
        translate([x - 7.62 - 0.6, -EPS, Q_VZ + V2_HDR_Z - 2.54 - 0.6]) cube([15.24 + 1.2, T + 2, 5.08 + 1.2]);
        translate([x - 5.2, -EPS, Q_VZ + V2_LED_Z]) rotate([-90, 0, 0]) cylinder(d = 3, h = T + 2);
        translate([x + 3, 0, Q_VZ + V2_LED_Z]) rotate([90, 0, 0]) deboss(str(k + 1), cap = 5.5);
    }
    translate([Q_VX + V2_D1[0], -EPS, Q_VZ + V2_D1[1]]) rotate([-90, 0, 0]) cylinder(d = 3, h = T + 2);
    node_front(Q_NX, Q_NTOP);
    name_recess(Q_W - 31, Q_NZ - 2);
    pd_cut(Q_PDX, Q_D, Q_PDZ);
    // rear: low vents, the wall thinned over the antenna; right: AUX's slot
    for (x = [32 : 6 : 92]) translate([x, Q_D - T - 1, 8]) cube([2.5, T + 2, 20]);
    translate([Q_ANT[0], Q_D - T - EPS, Q_NZ - 4]) cube([Q_ANT[1] - Q_ANT[0], 0.8 + EPS, Q_ZL]);
    translate([Q_W - T - 1, nk(NODE_AUX, Q_NX, Q_NY)[1] - 4, Q_ZL - 3.5]) cube([T + 2, 8, 3.5 + EPS]);
    feet_pockets(Q_W, Q_D);
}
// the shelf: on the ledges and the rails, 0.5 over the v2's top edge (the board can't lift out of its slots); open at
// its sides for the leads (PD into J1, left; J7 down to the v2's J1, right), slots for the air from below
module quad_shelf() difference() {
    union() {
        translate([T + 0.2, T + 0.2, Q_SHELF[0]]) cube([Q_W - 2 * T - 0.4, Q_D - 2 * T - 0.4, Q_SHELF[1]]);
        for (h = NODE_HOLES) translate(concat(nk(h, Q_NX, Q_NY), Q_SHELF[0] + Q_SHELF[1] - EPS)) difference() {
            cylinder(d = BOSS_D, h = Q_NZ - Q_SHELF[0] - Q_SHELF[1] + EPS);
            translate([0, 0, Q_NZ - Q_SHELF[0] - Q_SHELF[1] + EPS]) insert_hole(INSERT_M3);
        }
    }
    translate([T, 20, Q_SHELF[0] - 1]) cube([Q_NX - T - 1, 50, 5]);
    translate([Q_NX + NODE_SIZE[0] + 2, 20, Q_SHELF[0] - 1]) cube([Q_W - T - 10 - Q_NX - NODE_SIZE[0] - 2, 60, 5]);
    for (x = [Q_NX + 20 : 6 : Q_NX + 56]) translate([x, 25, Q_SHELF[0] - 1]) cube([2.5, 40, 5]);
    for (p = Q_LIDS) translate([p[0] < Q_W / 2 ? 0 : Q_W - 10, p[1] < Q_D / 2 ? 0 : Q_D - 10, Q_SHELF[0] - 1]) cube([10, 10, 5]);
}
module quad_lid() lid(Q_W, Q_D, Q_ZL, Q_LIDS, Q_BTN, Q_NTOP,
        [for (x = [Q_NX + 2 : 4 : Q_NX + 22]) [x, 22, 34]], nk(NODE_CAM, Q_NX, Q_NY));

// ---------------------------------------------------------------- the desk frame
// The rack's honeycomb plate (board_plate.scad: PLATE_W × PLATE_D × PLATE_T) in a pocket on two pins, as in the
// drawer; an open floor; behind it a dock at desk level: the box's two front feet drop through its slots and stand
// on the desk, the box's front face 0.5 off the frame's rear wall.  Both boxes: their front feet 12 from the
// corners, 106 and 107 wide.
F_IN = [PLATE_W + 0.6, PLATE_D + 0.6];
F_WALL = 2.4;
F_FLOOR = 2.5;
F_W = F_IN[0] + 2 * F_WALL;  F_D = F_IN[1] + 2 * F_WALL;
F_H = F_FLOOR + PLATE_T + 1;              // the rim 1 over the plate
F_DOCK = [26, SA_FEET[1] - FEET_SET - 0.5];   // behind the rear wall: depth, thickness (0.5 under the box)
F_FEET = [for (s = [-1, 1]) [F_W / 2 + s * (S_W / 2 - 12 + 0.25), F_D + 0.5 + 12]];   // between the two boxes' feet

module desk_frame() difference() {
    union() {
        vl_block([F_W, F_D, F_H]);
        translate([0, F_D - R - 1, 0]) vl_block([F_W, F_DOCK[0] + R + 1, F_DOCK[1]]);
        for (p = plate_pins()) translate([F_WALL + 0.3 + p[0], F_WALL + 0.3 + p[1], F_FLOOR - EPS]) cylinder(d = 3.8, h = 2.2 + EPS);
    }
    difference() {
        translate([F_WALL, F_WALL, F_FLOOR]) cube([F_IN[0], F_IN[1], F_H]);
        for (p = plate_pins()) translate([F_WALL + 0.3 + p[0], F_WALL + 0.3 + p[1], 0]) cylinder(d = 3.8, h = F_FLOOR + 2.2);
    }
    // the open floor: 3 × 3 windows between 8 mm ribs, solid rings round the pins
    cw = (F_IN[0] - 4 * 8) / 3;  chh = (F_IN[1] - 4 * 8) / 3;
    translate([0, 0, -EPS]) linear_extrude(F_FLOOR + 2 * EPS) offset(r = 4) offset(delta = -4) difference() {
        for (i = [0 : 2], j = [0 : 2]) translate([F_WALL + 8 + i * (cw + 8), F_WALL + 8 + j * (chh + 8)]) square([cw, chh]);
        for (p = plate_pins()) translate([F_WALL + 0.3 + p[0], F_WALL + 0.3 + p[1]]) circle(r = 7);
    }
    // the rim's top edge: 0.5 × 45° inside (the plate drops in), the dock's slots for the box's front feet
    hull() {
        translate([F_WALL, F_WALL, F_H - 0.6]) cube([F_IN[0], F_IN[1], EPS]);
        translate([F_WALL - 0.6, F_WALL - 0.6, F_H]) cube([F_IN[0] + 1.2, F_IN[1] + 1.2, EPS]);
    }
    for (f = F_FEET) translate([f[0], f[1], -EPS]) hull() for (dx = [-0.6, 0.6]) translate([dx, 0, 0]) cylinder(d = SA_FEET[0] + 1.2, h = F_FLOOR + 2 * EPS);
}

// ---------------------------------------------------------------- parts
module flip(h) translate([0, 0, h]) rotate([180, 0, 0]) children();   // a lid, top face down, its top on z 0
if (PART == "solo_base" || PART == "solo_base_in_place") solo_base();
else if (PART == "solo_lid") translate([0, S_D, 0]) flip(S_H) solo_lid();
else if (PART == "solo_lid_in_place") solo_lid();
else if (PART == "quad_base" || PART == "quad_base_in_place") quad_base();
else if (PART == "quad_shelf") translate([0, 0, -Q_SHELF[0]]) quad_shelf();
else if (PART == "quad_shelf_in_place") quad_shelf();
else if (PART == "quad_lid") translate([0, Q_D, 0]) flip(Q_H) quad_lid();
else if (PART == "quad_lid_in_place") quad_lid();
else if (PART == "desk_frame" || PART == "desk_frame_in_place") desk_frame();
