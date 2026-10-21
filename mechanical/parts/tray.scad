// Tray — one per bay in the panel frame: carrier base + deck + both drawer guides in one part.
//
//   openscad -D 'PART="tray"'        -o tray.stl        parts/tray.scad
//   openscad -D 'PART="cap_plate"'   -o cap_plate.stl   parts/tray.scad   (top row's ceiling)
//   openscad -D 'PART="floor_plate"' -o floor_plate.stl parts/tray.scad   (ties the base ladders)
//
// Same plenum as the carrier base (bay node standoffs, drag chain anchor and rails, fascia
// with the PC port / LED / SERVICE switch, camera inserts underneath), without the deck: the
// drawer now rides on two ledges along the side walls, under the same C-channel lips as the
// old guides.  The plenum is open under the drawer, so the node is in reach once the drawer
// is pulled out.  Each side wall carries a runner that slides into the ladder groove from
// the front; near the middle, a flex arm in the wall clicks a barb into the groove's window.
// To remove a tray: pull the drawer out, press both arms inwards, slide the tray forwards.
// Print: bottom down, PETG, 3 walls, 15 % infill, no supports (each ledge sits on its side wall,
// its inner edge on 45° gussets with short bridges between them; over the row cable's window it bridges
// from the fascia to the wall behind; the lips' undersides rise at 45° from the guide walls).
include <../lib/panels.scad>
// fascia_cutouts(): lib/carrier.scad

PART = "tray";

LEDGE_X = DRAWER_X0 + 4;                 // ledge reaches 4 mm under the drawer's bottom edge
LEDGE_T = 2.5;
LEDGE_Z = CARRIER_PLENUM;                // ledge top = the old deck surface (drawer bottom)
LIP_X = DRAWER_X0 - 1;                   // the lip's tip
// the lip's underside rises at 45° from the guide wall's face and passes 0.4 over the flange's outer edge
// (GUIDE_LIP_Z, as the old flat lip: the anti-tip contact), so it prints without support; 2 mm at the tip
LIP_UNDER = LEDGE_Z + GUIDE_LIP_Z - 0.5;       // at the wall's face
GUIDE_TOP = LIP_UNDER + (LIP_X - GUIDE_WALL_T) + GUIDE_LIP_T;
DETENT_LEDGE = [DRAWER_X0 + DRAWER_MAGNET[0] / 2 + 1, DRAWER_Y0 + DRAWER_D - 14];   // magnet in the left ledge, under the drawer's
DETENT_PAD = [DETENT_LEDGE[0] + DRAWER_MAGNET[0] / 2 + 1, DRAWER_MAGNET[0] + 2];   // the ledge widened around it: x end, length (y)
FLOOR_D = PR - 2 - (PF + 1);             // as in ladder.scad
HOLE_R = 7;                              // bottom relief: hexagons on a 16 mm grid
HOLE_PITCH = 16;
GUSSET_T = 2;                            // ribs under the ledges
GUSSET_STEP = 24;
CHAIN_X = [CHAIN_FIXED_RUN_X - CHAIN_H / 2 - 3, CHAIN_MOVING_X + CHAIN_H / 2 + 3];   // chain sweep (x)
// the row cable's tie anchors (x, y of their centre): it runs at y ≤ 9 from x 112 to the right wall, the
// chain foot reaching y 12 at x 133-145 with the drawer out; a cable tie round it through each one's tunnel,
// its strap passing between the anchor's front face and the fascia (TIE_STRAP)
TIE = [4.6, 5.5, 5];                      // an anchor: x, y, height above the floor; its tunnel along y, 3 × 2.2 (a 2.5 mm tie)
TIE_STRAP = 2;
JUMPER_TIES = [for (x = [118, CARRIER_W - 8]) [x, CARRIER_FASCIA + TIE_STRAP + TIE[1] / 2]];   // y 7.25

module tie_anchor() translate([-TIE[0] / 2, -TIE[1] / 2, CARRIER_BOTTOM - EPS]) difference() {
    cube([TIE[0], TIE[1], TIE[2] + EPS]);
    translate([0.8, -1, 1.2]) cube([TIE[0] - 1.6, TIE[1] + 2, 2.2]);
}
// the node's left M3 screws sit under the left ledge and lip: a hole through both over each passes the
// screw (pan head Ø5.6) and a Ø5 screwdriver shaft, tray at the bench and drawer out.  Countersunk under the
// lip and on the ledge, so the drawer's rear flange can't catch an edge; at the ledge's front end it opens
// forwards and inwards (no thin finger left)
NODE_ACCESS_D = 6.4;
NODE_ACCESS = [for (h = NODE_HOLES) if (node_xy(h)[0] < LEDGE_X + NODE_ACCESS_D / 2) node_xy(h)];
// low rails keeping the two runs straight, [x, y0, y1]: the fixed one starts behind the anchor
CHAIN_RAILS = [[CHAIN_FIXED_RUN_X - CHAIN_H / 2 - 1.6, ANCHOR_Y0 + ANCHOR[1] + 1, CARRIER_D - 30],
               [CHAIN_MOVING_X + CHAIN_H / 2 + 0.4, CHAIN_FIXED[1], CARRIER_D - 30]];

// ------------------------------------------------------------------ shell (shared with the plates)
// Left side wall with its runner, latch arm and barb (x <= WALL); `ly` = barb catch face.
// a slot through the wall (along x, from x0, `len` long) between (y, z) centres a and b, its ends round
module wall_slot(x0, len, a, b) hull() for (c = [a, b])
    translate([x0, c[0], c[1]]) rotate([0, 90, 0]) cylinder(d = LATCH_SLOT, h = len, $fn = 24);

module side_wall(d, h, ly, runner_end) {
    rh = RUNNER_Z[1] - RUNNER_Z[0];
    sz = [RUNNER_Z[0] - LATCH_SLOT / 2, RUNNER_Z[1] + LATCH_SLOT / 2];   // the two long slots' centre lines
    sy = ly - LATCH_SLOT / 2;
    difference() {
        union() {
            cube([WALL, d, h]);
            translate([-RUNNER_OUT, RUNNER_Y0, RUNNER_Z[0]]) cube([RUNNER_OUT + EPS, runner_end - RUNNER_Y0, rh]);
            translate([-RUNNER_OUT, ly, RUNNER_Z[0]]) hull() {      // barb: square catch face, ramp behind
                translate([-EPS, 0, 0]) cube([EPS, 4, rh]);
                translate([-BARB, 0, 0]) cube([BARB, 1.5, rh]);
            }
        }
        // flex arm: wall + runner between two slots, free at the front end (the barb); the slots' ends round
        // (the root's two are the arm's stress raisers)
        wall_slot(-RUNNER_OUT - BARB - 1, WALL + RUNNER_OUT + BARB + 2, [sy, sz[0]], [sy, sz[1]]);
        for (z = sz) wall_slot(-RUNNER_OUT - 1, WALL + RUNNER_OUT + 2, [sy, z], [ly + LATCH_ARM - LATCH_SLOT / 2, z]);
    }
}

module both_sides(d, h, runner_end) {
    side_wall(d, h, LATCH_Y[0], runner_end);
    translate([CARRIER_W, 0, 0]) mirror([1, 0, 0]) side_wall(d, h, LATCH_Y[1], runner_end);
}

// hexagon relief, kept clear of `keep` (list of [x, y, r]) and of a margin along the edges
module relief_2d(d, keep, margin = 9, r = HOLE_R, pitch = HOLE_PITCH, skip_x = [0, 0]) {
    for (j = [0 : floor(d / (pitch * 0.866))], i = [0 : floor(CARRIER_W / pitch)]) {
        c = [margin + r * 0.866 + i * pitch + (j % 2) * pitch / 2, margin + r + j * pitch * 0.866];
        if (c[0] + r <= CARRIER_W - margin && c[1] + r <= d - margin
            && (c[0] + r < skip_x[0] || c[0] - r > skip_x[1])
            && min([for (k = concat(keep, [[-1e3, -1e3, 0]])) norm([c[0], c[1]] - [k[0], k[1]]) - k[2]]) > r + 2)
            translate(c) rotate(30) circle(r = r, $fn = 6);
    }
}

// nx × ny rounded windows between ribs, with solid rings around `keep` ([x, y, r])
module window_grid_2d(d, nx, ny, margin, rib, keep) {
    cw = (CARRIER_W - 2 * margin - (nx - 1) * rib) / nx;
    ch = (d - 2 * margin - (ny - 1) * rib) / ny;
    offset(r = 4) offset(delta = -4) difference() {
        for (i = [0 : nx - 1], j = [0 : ny - 1]) translate([margin + i * (cw + rib), margin + j * (ch + rib)]) square([cw, ch]);
        for (k = keep) translate([k[0], k[1]]) circle(r = k[2] + 4);
    }
}

// ------------------------------------------------------------------ tray
// Under the drag chain (it slides along y over the bottom), slots along y instead of hexagons
module chain_slots_2d(keep) {
    difference() {
        for (x = [CHAIN_X[0] + 3 : 9 : CHAIN_X[1] - 5], y0 = [22 : 46 : CARRIER_D - 50])
            translate([x, y0]) square([5, 40]);
        for (k = keep) translate([k[0], k[1]]) circle(r = k[2] + 2.5);
        for (r = CHAIN_RAILS) translate([r[0] - 2, r[1] - 2]) square([5.2, r[2] - r[1] + 4]);   // under the rails
    }
}

module tray_bottom_2d() {
    keep = concat(
        [for (h = NODE_HOLES) concat(node_xy(h), [5])],
        [for (c = cam_inserts()) concat(c, [5])],
        [for (b = ANCHOR_BOSSES) concat(b, [5])],
        [for (t = JUMPER_TIES) concat(t, [6])]);
    difference() {
        square([CARRIER_W, CARRIER_D]);
        relief_2d(CARRIER_D, keep, skip_x = CHAIN_X);
        chain_slots_2d(keep);
    }
}

// ledge (drawer runner surface) + guide wall + lip, left side; 45° gussets below, every GUSSET_STEP and
// either side of what they must clear (the row cable's window, this side's latch arm, the node's screws),
// the ledge bridging between them.  The ledge runs from the fascia (raised to it, tray()): over the window
// it is a bridge from the fascia to the wall behind.  `latch_y`: this side's latch arm
module guide_left(latch_y) {
    y0 = GUIDE_Y0;
    y1 = CARRIER_D - 2;
    free = concat([[JUMPER_Y[0] - 1, JUMPER_Y[1] + 1], [latch_y - 2, latch_y + LATCH_ARM + 1]],
                  [for (p = NODE_ACCESS) [p[1] - NODE_ACCESS_D / 2 - 1, p[1] + NODE_ACCESS_D / 2 + 1]]);
    gussets = concat([for (g = [y0 : GUSSET_STEP : y1 - GUSSET_T]) g], [y1 - GUSSET_T],
                     [for (f = free) each [f[0] - GUSSET_T - 0.5, f[1] + 0.5]]);
    difference() {
        union() {
            translate([0, 0, LEDGE_Z - LEDGE_T]) cube([LEDGE_X, y1, LEDGE_T]);
            // the side wall stops at CARRIER_WALL_H (the old deck's underside): raise it to the
            // ledge, which then sits on the wall all along instead of on the gussets alone
            translate([0, 0, CARRIER_WALL_H - EPS]) cube([WALL, y1, LEDGE_Z - LEDGE_T - CARRIER_WALL_H + 2 * EPS]);
            for (y = gussets)
                if (y >= y0 && y <= y1 - GUSSET_T && len([for (f = free) if (y + GUSSET_T > f[0] && y < f[1]) 1]) == 0)
                    translate([0, y, LEDGE_Z - LEDGE_T]) rotate([90, 0, 0]) mirror([0, 0, 1])
                        linear_extrude(GUSSET_T) polygon([[WALL - EPS, 0], [LEDGE_X, 0], [WALL - EPS, -(LEDGE_X - WALL)]]);
            translate([0, y0, LEDGE_Z]) cube([GUIDE_WALL_T, y1 - y0, GUIDE_TOP - LEDGE_Z]);
            translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(y1 - y0)
                polygon([[GUIDE_WALL_T - EPS, LIP_UNDER - EPS], [LIP_X, LIP_UNDER + LIP_X - GUIDE_WALL_T], [LIP_X, GUIDE_TOP],
                         [GUIDE_WALL_T - EPS, GUIDE_TOP]]);
        }
        // lead-in under the lip at the front
        translate([GUIDE_WALL_T, y0 - EPS, LEDGE_Z + GUIDE_LIP_Z - EPS]) hull() {
            cube([DRAWER_X0, EPS, 1.4]);
            translate([0, 6, 0]) cube([DRAWER_X0, EPS, EPS]);
        }
        // drawer end stop: a PT 2.3 × 8 screw (LIP_SCREW) through the lip, biting into the ledge; and a
        // sled bay's lock screws, the same way: its port block's flanges, and a fixed bay's sled (in a drawer
        // bay the first pair locks the drawer shut, for carrying the rack).  Round each shank, between the
        // ledge and the lip, the guide wall is relieved (its face is 0.15 mm inside the shank's reach).  The head sits
        // in a counterbore at the old flat lip's top, so the screw reaches as deep into the ledge as it did
        for (y = [STOP_Y, BLOCK_LOCK_Y, SLED_LOCK_Y]) {
            translate([STOP_PIN_X, y, LEDGE_Z - LEDGE_T - 1]) cylinder(d = LIP_SCREW[2], h = 10);
            translate([STOP_PIN_X, y, LEDGE_Z + GUIDE_LIP_Z - 1]) cylinder(d = LIP_SCREW[3], h = GUIDE_TOP - LEDGE_Z - GUIDE_LIP_Z + 2);
            translate([STOP_PIN_X, y, LEDGE_Z + GUIDE_LIP_Z + GUIDE_LIP_T]) cylinder(d = LIP_SCREW[1] + 0.5, h = GUIDE_TOP);
            translate([STOP_PIN_X, y, LEDGE_Z - EPS]) cylinder(d = LIP_SCREW[0] + 0.8, h = GUIDE_LIP_Z + 2 * EPS);
        }
    }
}

module tray() {
    difference() {
        union() {
            linear_extrude(CARRIER_BOTTOM) tray_bottom_2d();
            cube([CARRIER_W, CARRIER_FASCIA, CARRIER_WALL_H]);                       // fascia
            // raised to the ledges at both ends: they start on it
            for (x = [0, CARRIER_W - LEDGE_X]) translate([x, 0, CARRIER_WALL_H - EPS])
                cube([LEDGE_X, CARRIER_FASCIA, LEDGE_Z - LEDGE_T - CARRIER_WALL_H + 2 * EPS]);
            translate([0, CARRIER_D - WALL, 0]) cube([CARRIER_W, WALL, CARRIER_WALL_H]);   // rear wall
            both_sides(CARRIER_D, CARRIER_WALL_H, GROOVE_END);
            guide_left(LATCH_Y[0]);
            translate([CARRIER_W, 0, 0]) mirror([1, 0, 0]) guide_left(LATCH_Y[1]);
            // node PCB standoffs
            for (h = NODE_HOLES) translate(concat(node_xy(h), [0]))
                cylinder(d = BOSS_D, h = CARRIER_BOTTOM + CARRIER_STANDOFF);
            // camera-pod insert bosses (inserts go in from below)
            for (c = cam_inserts()) translate([c[0], c[1], 0]) cylinder(d = 7.5, h = CARRIER_BOTTOM + 4);
            // the row cable's two tie anchors, in front of the chain foot's reach (panels.scad › JUMPER_Y)
            for (t = JUMPER_TIES) translate([t[0], t[1], 0]) tie_anchor();
            // drag-chain anchor bosses (2 × M3 inserts, outside the fixed run) and the low rails
            for (b = ANCHOR_BOSSES) translate(concat(b, [0])) cylinder(d = 7.5, h = ANCHOR_Z0);
            for (r = CHAIN_RAILS) translate([r[0], r[1], 0]) cube([1.2, r[2] - r[1], CARRIER_BOTTOM + 3]);
            // detent magnet pad: the left ledge widened under the drawer's magnet, on a 45° gusset
            translate([0, DETENT_LEDGE[1] - DETENT_PAD[1] / 2, LEDGE_Z - LEDGE_T]) {
                cube([DETENT_PAD[0], DETENT_PAD[1], LEDGE_T]);
                rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(DETENT_PAD[1])
                    polygon([[WALL - EPS, 0], [DETENT_PAD[0], 0], [WALL - EPS, -(DETENT_PAD[0] - WALL)]]);
            }
        }
        for (h = NODE_HOLES) translate(concat(node_xy(h), [CARRIER_BOTTOM + CARRIER_STANDOFF])) insert_hole(INSERT_M3);
        for (c = cam_inserts()) translate([c[0], c[1], 0]) mirror([0, 0, 1]) insert_hole(INSERT_M3);
        for (b = ANCHOR_BOSSES) translate(concat(b, [ANCHOR_Z0])) insert_hole(INSERT_M3);
        fascia_cutouts();
        // bay label recess on the fascia, right of the controls
        translate([CARRIER_W - 34, 0.6 - EPS, CARRIER_WALL_H / 2]) rotate([90, 0, 0])
            linear_extrude(0.7) square([52, 11], center = true);
        // row cable: through both side walls and their runners, under the ledge
        for (x = [-RUNNER_OUT - 1, CARRIER_W - WALL - EPS])
            translate([x, JUMPER_Y[0], JUMPER_Z0]) cube([WALL + RUNNER_OUT + 1 + 2 * EPS, JUMPER_Y[1] - JUMPER_Y[0], LEDGE_Z - LEDGE_T - JUMPER_Z0]);
        // rear service slot (row feed, the camera lead, airflow)
        translate([20, CARRIER_D - WALL - EPS, CARRIER_BOTTOM + 2]) cube([60, WALL + 2 * EPS, CARRIER_WALL_H - 5]);
        // the node's RESET button sits under the left ledge's inner edge: a notch over its plunger lets a
        // pin reach it from above, drawer pulled out; the drawer still rests on 1.5 mm of ledge there
        translate(concat(node_xy(NODE_RESET), [LEDGE_Z - LEDGE_T - 1])) cylinder(r = LEDGE_X - node_xy(NODE_RESET)[0] + 1.5, h = LEDGE_T + 2);
        // screwdriver access to the node's left screws (NODE_ACCESS)
        for (p = NODE_ACCESS) translate([p[0], p[1], 0]) {
            r = NODE_ACCESS_D / 2;
            translate([0, 0, LEDGE_Z - LEDGE_T - 1]) cylinder(d = NODE_ACCESS_D, h = GUIDE_TOP - LEDGE_Z + LEDGE_T + 2);
            translate([0, 0, LEDGE_Z - 0.6]) cylinder(d1 = NODE_ACCESS_D, d2 = NODE_ACCESS_D + 1.2 + 2 * EPS, h = 0.6 + EPS);
            translate([0, 0, LEDGE_Z + GUIDE_LIP_Z - EPS]) cylinder(d1 = NODE_ACCESS_D + 2, d2 = NODE_ACCESS_D, h = 1);
            if (p[1] - r < GUIDE_Y0 + 2)
                translate([-r, CARRIER_FASCIA - p[1], LEDGE_Z - LEDGE_T - 1]) cube([LEDGE_X + 1 - p[0] + r, p[1] - CARRIER_FASCIA, GUIDE_TOP - LEDGE_Z + LEDGE_T + 2]);
        }
        // closed-position detent magnet, flush with the left ledge (the pad below gives it its depth)
        translate([DETENT_LEDGE[0], DETENT_LEDGE[1], LEDGE_Z]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1]);
    }
}

// ------------------------------------------------------------------ plates: cap (ceiling) and floor
// A regular grid at the camera-pod pitch (CAM_MOUNT[2] = 30 mm), centred on the plate, with a
// boss and a through hole for an M3 heat-set insert at every rib crossing: the pod screws to
// any 30 mm square of crossings (centred on the bay by default), and the floor plate takes
// the PSU / hub brackets the same way.  No insert needed where nothing is mounted.
PLATE_WALL_H = RUNNER_Z[1] + 2;
GRID = CAM_MOUNT[2];
GRID_RIB = 6;
GRID_BORDER = 7;
function grid_lines(len) = [for (k = [-10 : 10]) let (v = len / 2 + GRID / 2 + k * GRID)
                            if (v > GRID_BORDER + GRID_RIB && v < len - GRID_BORDER - GRID_RIB) v];

module grid_windows_2d(d) {
    xs = concat([GRID_BORDER - GRID_RIB / 2], grid_lines(CARRIER_W), [CARRIER_W - GRID_BORDER + GRID_RIB / 2]);
    ys = concat([GRID_BORDER - GRID_RIB / 2], grid_lines(d), [d - GRID_BORDER + GRID_RIB / 2]);
    for (i = [0 : len(xs) - 2], j = [0 : len(ys) - 2])
        translate([xs[i] + GRID_RIB / 2, ys[j] + GRID_RIB / 2])
            offset(r = 3) offset(delta = -3) square([xs[i + 1] - xs[i] - GRID_RIB, ys[j + 1] - ys[j] - GRID_RIB]);
}

module tie_plate(d, runner_end) {
    pegs = [for (x = grid_lines(CARRIER_W), y = grid_lines(d)) [x, y]];
    difference() {
        union() {
            linear_extrude(CARRIER_BOTTOM) difference() {
                square([CARRIER_W, d]);
                grid_windows_2d(d);
            }
            both_sides(d, PLATE_WALL_H, runner_end);
            for (y = [0, d - WALL]) translate([0, y, 0]) cube([CARRIER_W, WALL, 8]);   // front / rear lips
            for (p = pegs) translate([p[0], p[1], 0]) cylinder(d = 7.5, h = CARRIER_BOTTOM + 4);
        }
        for (p = pegs) translate([p[0], p[1], -EPS]) cylinder(d = INSERT_M3[0], h = CARRIER_BOTTOM + 5);
    }
}

if (PART == "tray") tray();
else if (PART == "cap_plate") tie_plate(CARRIER_D, GROOVE_END);
else if (PART == "floor_plate") tie_plate(FLOOR_D, FLOOR_D);
