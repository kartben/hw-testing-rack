// Bay drawer (one per bay) — drawer coordinates: origin at the front-left
// corner of the drawer body, z = 0 on the tray's ledges.
//
//   -D 'PART="drawer"'  the drawer (default), without its front
//   -D 'PART="front"'   its front, face down as printed (PART="front_in_place": in drawer coordinates)
//   -D 'PART="sled"'    a sled bay's plate: the drawer cut 1 mm in front of its port wall, no chain foot,
//                       no magnet; two flange segments at its rear (lock screws in a fixed bay)
//   -D 'PART="block"'   a sled bay's port block: the drawer's rear bay on its own, locked into the tray by
//                       two PT 2.3 × 8 through the guide lips
//
// - Front panel with a finger pull, a recess for 12 mm label tape and the display's window, its frame behind:
//   its own part, printed face down (the window's a plain hole, the frame stands straight up), pulled onto the
//   side walls, a PT 2.3 × 8 either side from inside the drawer into its back.
// - Board-plate pocket: plates drop in (two 180°-symmetric locating pins).
// - Rear bay behind the port wall, one for both DATA boards (a bay converts by changing the board, not the
//   drawer): four U's in the wall, the DATA ×4's ports.  A DATA ×4 v1 on three floor bosses; a DATA ×4 v2,
//   standing, in its cradle (parts/x4_cradle.scad) on the same three; or the single DATA port board on two
//   more, its USB-C behind the fourth U, the optional AUX pigtail through a free one.  Every board's PH 8 lead
//   comes up through the cable window at the rear right, from the drag chain's moving end: a rear strip (the
//   single board's lead, then along the rear wall to its PH; a v2's, over its cradle) and a side strip beside
//   a v1's right edge, under its J1.  The chain foot slides
//   into the rear-open groove under the bottom and is locked by one PT 2.3 × 8 screw from inside the rear bay.
// - Rear flange segments run under the guide lips (anti-tip); a notch under the left wall takes the bump of
//   the tray's printed detent tab (or, drawer.detent: magnet, a magnet under the rear bay over the left ledge).
// - It rides on the tray's two side ledges (parts/tray.scad), so its floor only carries the
//   board plate: nine windows.
// - Pin holes over the node's RESET and BOOT (through every plate too): press them with the drawer in.
// Print: bottom down, PETG, 3 walls, no supports.
include <../lib/carrier.scad>

PART = "drawer";

// drawer.detent: magnet: the magnet sits right inside the left wall, its boss within the drawer's footprint (a boss
// sticking out of the wall would hit the tray's guide lip on the last 10 mm before closing)
DETENT = [DRAWER_MAGNET[0] / 2 + 1, DRAWER_D - 14];
DETENT_BOSS = DRAWER_MAGNET[0] + 2;
RIB = 6;                                       // floor ribs

FRONT_OVERHANG = DRAWER_X0 - 1;            // front panel overhangs the guides
FOOT_GROOVE = [6.4, DRAWER_D - FOOT_HOLE[1] + 1, 2.3];
LABEL_Z = DRAWER_FRONT_H * 0.42;           // the label recess's centre height
// with a display, the pull and the label share the front's left part, the window and its frame the right one
FRONT_LEFT_X = HAS_DISPLAY ? (DISPLAY_WIN[0] - DISPLAY_FRAME[0] - FRONT_OVERHANG) / 2 : DRAWER_W / 2;
// the front's joint: a PT 2.3 × 8 either side, from inside the drawer along the drawer through a post hanging off
// the side wall (its underside at 45° from the plate's top) into a boss on the front's back, 0.3 short of the post:
// the screw pulls the front onto the walls' and the floor's front ends.  On the right the display frame's leg is
// the boss.  [screw x, boss x0, boss x1]
JOINT_Y = DRAWER_FRONT_T + 7.4;            // the posts' front faces
JOINT_T = 3;                               // the posts, thick
JOINT_Z = 13.5;                            // the screws' height
JOINT_W = 5.2;                             // a post, in from its wall's inner face
JOINTS = [[DRAWER_WALL + 2.75, DRAWER_WALL + 0.3, DRAWER_WALL + JOINT_W],
          [DRAWER_W - DRAWER_WALL - 2.9, DRAWER_W - DRAWER_WALL - JOINT_W, DRAWER_W - DRAWER_WALL - 0.3]];
// the front panel: R3 on its two front vertical corners (its back joins the drawer), a 0.5 × 45° chamfer round its
// front and side bed edges, a 0.8 round on its top edges (lib/common.scad › the visual language)
module front_panel() {
    w = DRAWER_W + 2 * FRONT_OVERHANG;
    x0 = -FRONT_OVERHANG;
    r = VL_R[0];
    module outline(inset = 0) intersection() {
        hull() {
            for (x = [x0 + r, x0 + w - r]) translate([x, r]) circle(r = r - inset, $fn = 48);
            translate([x0 + inset, r]) square([w - 2 * inset, DRAWER_FRONT_T - r]);
        }
        translate([x0 - 1, -1]) square([w + 2, DRAWER_FRONT_T + 1]);
    }
    difference() {
        hull() {
            linear_extrude(EPS) outline(VL_CHAMFER);
            translate([0, 0, VL_CHAMFER]) linear_extrude(DRAWER_FRONT_H - VL_CHAMFER) outline();
        }
        translate([x0, 0, DRAWER_FRONT_H]) mirror([0, 0, 1]) edge_round(w);
        translate([x0, DRAWER_FRONT_T, DRAWER_FRONT_H]) mirror([0, 1, 0]) mirror([0, 0, 1]) edge_round(w);
        // finger pull: scoop at the top centre (of the left part, with a display)
        translate([FRONT_LEFT_X, -EPS, DRAWER_FRONT_H]) rotate([-90, 0, 0])
            scale([1, 0.32, 1]) cylinder(r = 28, h = DRAWER_FRONT_T + 2 * EPS, $fn = 96);
        // label recess (the bay label, or 12 mm tape): its ceiling at 45°, opening towards the face, so nothing
        // overhangs as printed (the label fits the 12.4 at its back; docs/printed-parts-fdm-review.md, item 7)
        translate([FRONT_LEFT_X, -EPS, LABEL_Z]) rotate([90, 0, 0]) mirror([0, 0, 1]) hull() {
            linear_extrude(EPS) translate([0, 0.45]) offset(r = 0.6) square([LABEL_RECESS_W, 12.4 - 1.2 + 0.9], center = true);
            translate([0, 0, 0.9 - EPS]) linear_extrude(EPS) offset(r = 0.6) square([LABEL_RECESS_W, 12.4 - 1.2], center = true);
        }
        if (HAS_DISPLAY) display_window();
    }
}

// the display goes in from the front through a plain window, DISPLAY_CLEAR round its glass
module display_window() let (w = DISPLAY_WIN)
    translate([w[0], -EPS, w[1]]) cube([w[2] - w[0], DRAWER_FRONT_T + 2 * EPS, w[3] - w[1]]);

// its frame on the front's back: a leg either side of the window and two bars across behind it at its holes'
// heights.  Its stand-offs seat on the bars, an M2 from behind into each.  Printed face down, the legs stand
// straight up and the bars bridge between them; the bottom bar steps back over its SH header and plug
module display_frame() {
    w = DISPLAY_WIN;
    leg = DISPLAY_FRAME[0];
    bar = DISPLAY_FRAME[1];
    h = display_holes();
    z = [h[0][1] - 2.5, h[1][1] + 2.5];
    y1 = DISPLAY_SEAT_Y + bar;
    difference() {
        union() {
            // the right leg fills the room to the right wall: the front's right screw goes into it
            for (x = [[w[0] - leg, w[0]], [w[2], JOINTS[1][2]]]) translate([x[0], DRAWER_FRONT_T - EPS, z[0]])
                cube([x[1] - x[0], y1 - DRAWER_FRONT_T + EPS, z[1] - z[0]]);
            for (zc = [h[0][1], h[1][1]]) translate([w[0] - EPS, DISPLAY_SEAT_Y, zc - 2.5]) cube([w[2] - w[0] + 2 * EPS, bar, 5]);
        }
        // the screw holes from 0.2 behind the seat: the bars' first layer bridges whole, the screw pierces it
        for (p = h) translate([p[0], DISPLAY_SEAT_Y + 0.2, p[1]]) rotate([-90, 0, 0])
            cylinder(d = DISPLAY_FIT[3] + 0.4, h = bar, $fn = 24);
        sh = display_sh_x();
        translate([sh[0] - 2, DISPLAY_SEAT_Y - EPS, z[0] - EPS]) cube([sh[1] - sh[0] + 4, 1 + EPS, 5 + 2 * EPS]);
    }
}

// the front on its own (PART "front"): the panel, the display's frame and the joint's bosses, clear of the display's
// way in through the window
module front() difference() {
    union() {
        front_panel();
        if (HAS_DISPLAY) display_frame();
        for (j = JOINTS) translate([j[1], DRAWER_FRONT_T - EPS, JOINT_Z - 3.5]) cube([j[2] - j[1], JOINT_Y - 0.3 - DRAWER_FRONT_T + EPS, 7]);
    }
    for (j = JOINTS) translate([j[0], JOINT_Y - 0.3 + EPS, JOINT_Z]) rotate([90, 0, 0]) cylinder(d = PT_PILOT, h = 5.3, $fn = 16);
    // 0.3 clear of the posts (the display frame's right leg runs to them)
    for (x = [[-EPS, DRAWER_WALL + JOINT_W], [DRAWER_W - DRAWER_WALL - JOINT_W, DRAWER_W + EPS]])
        translate([x[0], JOINT_Y - 0.3, DRAWER_BOTTOM + PLATE_T]) cube([x[1] - x[0], 0.3 + EPS, DRAWER_WALL_H - DRAWER_BOTTOM - PLATE_T + EPS]);
    if (HAS_DISPLAY) let (w = DISPLAY_WIN) translate([w[0], -EPS, w[1]]) cube([w[2] - w[0], DISPLAY_SEAT_Y + EPS, w[3] - w[1]]);
}

// the joint's posts (drawer side) and their screws' clearance
module joint_posts() for (i = [0, 1]) let (o = i == 0 ? 0 : DRAWER_W, s = i == 0 ? 1 : -1, z0 = DRAWER_BOTTOM + PLATE_T,
                                          w = DRAWER_WALL + JOINT_W)
    translate([0, JOINT_Y, 0]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(JOINT_T)
        polygon([[o, z0], [o + s * DRAWER_WALL, z0], [o + s * w, z0 + JOINT_W], [o + s * w, DRAWER_WALL_H], [o, DRAWER_WALL_H]]);
module joint_holes() for (j = JOINTS)
    translate([j[0], JOINT_Y - EPS, JOINT_Z]) rotate([-90, 0, 0]) cylinder(d = PT_CLEAR, h = JOINT_T + 2 * EPS, $fn = 24);

// the DATA ports along the port wall: the DATA ×4's four (config/rack.yaml › pcb.data_port_x4)
PORT_XS = [for (u = DATA_X4_USB) DATA_X4_X0 + u];
assert(abs(DATA_PORT_X[0] - PORT_XS[3]) < 0.01, "the single DATA board's USB-C sits on the fourth port");
// the DATA ×4's bosses: v1's first three holes, which the v2's cradle shares (v1 is not ordered: its front-edge
// ledges are gone, docs/printed-parts-review.md); a fourth hole, if v1 has one, stays unused
X4_HOLES = [for (i = [0 : 2]) let (h = DATA_X4_HOLES[i]) [DATA_X4_X0 + h[0], DATA_PCB_Y0 + DATA_X4_SIZE[1] - h[1]]];
X4_BOSS_D = INSERT_M3[0] + 4;                     // the DATA ×4 bosses take M3 inserts (the cradle's M3 × 8): 2 mm of wall
// the single board's bosses and ledges: lib/carrier.scad › ONE_HOLES, ONE_LEDGES
// A DATA ×4 v2's plugs reach the ledges' front strip: the overmold (12.35 × 6.5 at most, on PORT_Z) passes the
// port wall's U and stops at the v2's mouths, 1 mm behind the wall, its underside (7.75) 0.02 into the ledges'
// top (SolidCraft, 2026-10-31).  That strip drops 0.3 for 1.2 mm; the single board keeps 0.8 mm of ledge.
LEDGE_STEP = [1.2, 0.3];                          // depth (y), drop
function pin_spots() = [for (k = [NODE_RESET, NODE_BOOT]) node_xy(k) - [DRAWER_X0, 0]];   // the node's buttons, drawer xy

module port_wall() {
    y = DRAWER_PORT_WALL_Y;
    t = DRAWER_WALL;
    w = USBC_PLUG_CUT[0];
    r = 1.5;                                        // the U's bottom corners: a right-angle body's fit there
    difference() {
        translate([0, y - t, 0]) cube([DRAWER_W, t, DRAWER_WALL_H]);
        // the DATA ports: the USB-C plug cut's width, from its bottom up through the wall's top
        for (x = PORT_XS) translate([x, y - t - EPS, PORT_Z - USBC_PLUG_CUT[1] / 2]) hull() {
            for (s = [-1, 1]) translate([s * (w / 2 - r), 0, r]) rotate([-90, 0, 0]) cylinder(r = r, h = t + 2 * EPS);
            translate([-w / 2, 0, r]) cube([w, t + 2 * EPS, DRAWER_WALL_H]);
        }
        // the display's lead into the rear bay: a notch at the wall's foot over the plate's right gap
        if (HAS_DISPLAY) translate([DRAWER_W - DRAWER_WALL - DRAWER_PLATE_GAP[1] - 0.5, y - t - EPS, DRAWER_BOTTOM - EPS])
            cube([DRAWER_PLATE_GAP[1] + 0.5 + EPS, t + 2 * EPS, 5.5 + EPS]);
        // the port numbers, 1–4 left to right, debossed in the wall's front face left of each U
        for (i = [0 : len(PORT_XS) - 1]) translate([PORT_XS[i] - w / 2 - 2.3, y - t, PORT_Z]) rotate([90, 0, 0])
            deboss(str(i + 1), cap = 5.5);
    }
}

// rear = the rear bay (port wall, DATA board, window); foot = the chain foot's groove and boss, the magnet
module drawer(rear = true, foot = true) {
    difference() {
        union() {
            translate([0, DRAWER_FRONT_T, 0]) rbox([DRAWER_W, DRAWER_D - DRAWER_FRONT_T, DRAWER_BOTTOM], r = 2);
            joint_posts();
            // side and rear walls
            for (x = [0, DRAWER_W - DRAWER_WALL]) translate([x, DRAWER_FRONT_T, 0]) cube([DRAWER_WALL, DRAWER_D - DRAWER_FRONT_T, DRAWER_WALL_H]);
            translate([0, DRAWER_D - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL, DRAWER_WALL_H]);
            if (rear) port_wall();
            // flange segments captured by the guides
            for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, FLANGE_Y[0], 0]) cube([DRAWER_FLANGE[0] + EPS, FLANGE_Y[1] - FLANGE_Y[0], DRAWER_FLANGE[1]]);
            // plate locating pins
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1], DRAWER_BOTTOM]) cylinder(d = 3.8, h = 2.2);
            // boss for the foot lock screw, and for the detent magnet (drawer.detent: magnet)
            if (foot) {
                translate([FOOT_HOLE[0], FOOT_HOLE[1], 0]) cylinder(d = 9, h = DRAWER_BOTTOM + 4);
                if (DRAWER_DETENT == "magnet") translate([DETENT[0], DETENT[1], 0]) cylinder(d = DETENT_BOSS, h = DRAWER_MAGNET[1] + 1.2);
            }
            if (rear) {
                // the boards' bosses, and two ledges under the single board's front edge (its underside is bare
                // but for its USB4105's pegs), their front strip lowered under a DATA ×4 v2 plug's overmold
                for (h = X4_HOLES) translate([h[0], h[1], 0]) cylinder(d = X4_BOSS_D, h = DATA_PCB_Z);
                for (h = ONE_HOLES) translate([h[0], h[1], 0]) cylinder(d = 5, h = DATA_PCB_Z);
                for (s = ONE_LEDGES) translate([s[0], DATA_PCB_Y0 - EPS, 0]) difference() {
                    cube([s[1] - s[0], 2, DATA_PCB_Z]);
                    translate([-EPS, -EPS, DATA_PCB_Z - LEDGE_STEP[1]]) cube([s[1] - s[0] + 2 * EPS, LEDGE_STEP[0] + EPS, 1]);
                }
            }
        }
        // rear-open groove for the chain foot, and its lock screw
        if (foot) {
            translate([FOOT_HOLE[0] - FOOT_GROOVE[0] / 2, FOOT_HOLE[1] - 5, -EPS]) cube([FOOT_GROOVE[0], FOOT_GROOVE[1] + 5, FOOT_GROOVE[2]]);
            translate([FOOT_HOLE[0], FOOT_HOLE[1], -EPS]) {
                cylinder(d = 2.8, h = DRAWER_BOTTOM + 5);
                translate([0, 0, DRAWER_BOTTOM + 4 - 2]) cylinder(d = 5.4, h = 2 + EPS);
            }
            // detent magnet from below
            if (DRAWER_DETENT == "magnet") translate([DETENT[0], DETENT[1], 0]) mirror([0, 0, 1]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1]);
        }
        detent_notch();
        joint_holes();
        // the optional covers' pockets (parts/covers.scad): in the rear wall's inner face, a tab's bump in each
        if (rear) for (x = COVER_TABS)
            translate([x + 3 - 0.5, DRAWER_D - DRAWER_WALL - EPS, 6 + 0.7]) cube([6, COVER_BUMP + 0.2 + EPS, 2 * COVER_BUMP + 1 + 0.6]);
        if (rear) {
            // pilots for the single DATA port board's PT 2.3 × 8, from above
            for (h = ONE_HOLES) translate([h[0], h[1], DATA_PCB_Z - 7]) cylinder(d = PT_PILOT, h = 7 + EPS);
            // the DATA ×4's (the cradle's): an M3 insert in each, its hole running on through the floor (an
            // M3 × 8 from the cradle goes 0.7 mm past the insert)
            for (h = X4_HOLES) translate([h[0], h[1], DATA_PCB_Z]) insert_hole(INSERT_M3, runout = DATA_PCB_Z - INSERT_M3[1] + 1);
            // cable window in the rear-bay floor, up to 1 mm off the rear wall and 1 mm short of the foot's boss:
            // a rear strip from 1.5 mm right of the third boss (the single board's lead comes up there and runs
            // left along the rear wall to its PH; a v2's drops behind its cradle), and a side strip 1 mm right of
            // a v1's right edge, from 4 mm behind the port wall (v1's J1 plug is right above)
            wy = DATA_PCB_Y0 + DATA_PCB_SIZE[1] + 1;
            wx = X4_HOLES[2][0] + X4_BOSS_D / 2 + 1.5;
            sx = DATA_X4_X0 + DATA_X4_SIZE[0] + 1;
            sy = DATA_PCB_Y0 + 4;
            we = FOOT_HOLE[0] - 5.5;
            wr = DRAWER_D - DRAWER_WALL - 1;
            assert(sx < we - 4, "the DATA ×4 is too long for a side strip beside it");
            translate([0, 0, -EPS]) linear_extrude(DRAWER_BOTTOM + 2 * EPS) offset(r = 2) offset(delta = -2) union() {
                translate([wx, wy]) square([we - wx, wr - wy]);
                translate([sx, sy]) square([we - sx, wr - sy]);
            }
        }
        // pin holes over the node's RESET and BOOT
        for (p = pin_spots()) translate([p[0], p[1], -EPS]) cylinder(d = 3.2, h = DRAWER_BOTTOM + 2 * EPS);
        // open floor: 3 × 3 windows between 6 mm ribs, solid side strips (they ride on the
        // tray ledges) and solid rings around the plate pins
        x0 = 8;
        y0 = DRAWER_FRONT_T + 6;
        cw = (DRAWER_W - 2 * x0 - 2 * RIB) / 3;
        ch = (DRAWER_PORT_WALL_Y - 6 - y0 - 2 * RIB) / 3;
        translate([0, 0, -EPS]) linear_extrude(DRAWER_BOTTOM + 2 * EPS) offset(r = 4) offset(delta = -4) difference() {
            for (i = [0 : 2], j = [0 : 2]) translate([x0 + i * (cw + RIB), y0 + j * (ch + RIB)]) square([cw, ch]);
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1]]) circle(r = 7);
        }
    }
}

// a sled: the drawer's front, flange segments under the guide lips at its rear.  Its floor ends open: the board
// plate runs to the port wall (y PLATE_D), over the sled's rear edge, so no rail can cross it there
// the printed detent's notch under the left wall (and a sled's flange): the tray's bump drops into it as the
// drawer closes; a sled gets the same detent
module detent_notch() if (DRAWER_DETENT == "printed")
    translate([DETENT_TAB_X - DRAWER_X0 - 0.2, DETENT_TAB_Y - DETENT_BUMP[1] / 2 - 0.2, -EPS])
        cube([DETENT_TAB[0] + 0.4, DETENT_BUMP[1] + 0.4, DETENT_BUMP[0] + 0.2]);

module sled() difference() {
    union() {
        intersection() {
            drawer(rear = false, foot = false);
            translate([-50, -50, -10]) cube([DRAWER_W + 100, SPLIT + 50, 100]);
        }
        for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, SLED_FLANGE_Y[0], 0])
            cube([DRAWER_FLANGE[0] + EPS, SLED_FLANGE_Y[1] - SLED_FLANGE_Y[0], DRAWER_FLANGE[1]]);
    }
    lock_holes(SLED_LOCK_Y);
    detent_notch();
}

// the port block: the drawer's rear bay on its own, its flanges drilled for the two lock screws
module block() difference() {
    intersection() {
        drawer(rear = true, foot = false);
        translate([-50, SPLIT, -10]) cube([DRAWER_W + 100, 100, 100]);
    }
    lock_holes(BLOCK_LOCK_Y);
}

// under the tray's lip screws (STOP_PIN_X, mirrored on the right): open at the flange's outer edge
module lock_holes(y) for (x = [STOP_PIN_X - DRAWER_X0, DRAWER_W - (STOP_PIN_X - DRAWER_X0)])
    translate([x, y, -EPS]) cylinder(d = LIP_SCREW[3], h = DRAWER_FLANGE[1] + 2 * EPS);

if (PART == "front") rotate([90, 0, 0]) front();
else if (PART == "front_in_place") front();
else if (PART == "sled") sled();
else if (PART == "block") block();
else drawer();
