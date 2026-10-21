// Ladder — the printed side wall between two bays of the panel frame (no aluminium).
//
//   openscad -D 'PART="row"' -D ROW=0 -o ladder_a.stl  parts/ladder.scad   (holds row A's trays)
//   openscad -D 'PART="base"'          -o ladder_base.stl parts/ladder.scad (floor -> row A)
//   openscad -D 'PART="cap"' -D ROW=2  -o ladder_cap.stl  parts/ladder.scad (on top of the last row)
//
// One ladder per column boundary and per row; trays on both sides share it.  A row ladder
// runs from the bottom plane of its row's trays to the bottom plane of the next row's: front
// post, rear post, a bottom band along the slope (grooves on both faces for the tray runners,
// latch windows, the row cable hole), a top band (slots for the next ladder's hooks) and a
// brace.  Stacking: the lower ladder's top edge carries a ridge, the upper one's bottom edge
// the matching notch and two snap hooks in its own plane; the hooks face opposite ways, which
// also locates the ladders along the slope.  Release a hook by pushing its barb through the
// window.  Print: flat as modelled (the profile is in XY), PETG, 3 walls, 15 % infill.
include <../lib/panels.scad>

PART = "row";       // row | base | cap
ROW = 0;            // row whose trays the ladder holds (A = 0); for "cap": the row above the last

FLOOR_BAND = 22;                         // base ladder bottom band (frame Z)
FLOOR_Y0 = PF + 1;                       // floor plate front edge (frame Y)
FLOOR_D = PR - 2 - FLOOR_Y0;             // floor plate depth (its rear end = the groove end)
HOOK_DIR = [1, -1];                      // barb towards +y / -y (locates the ladders along y)

// ------------------------------------------------------------------ snap hooks (2D, local: x = row y - hy)
module hook_local() {
    translate([-HOOK_W / 2, -HOOK_DROP]) square([HOOK_W, HOOK_DROP + 0.01]);
    polygon([[HOOK_W / 2 - 0.01, -(HOOK_NECK + 0.3)], [HOOK_W / 2 + HOOK_BARB, -(HOOK_NECK + 0.3)],
             [HOOK_W / 2 + HOOK_BARB, -(HOOK_DROP - 2.5)], [HOOK_W / 2 - 0.01, -HOOK_DROP]]);
}
module hook_relief_local()           // frees the beam root inside the ladder's own band, its ends round
    for (s = [-1, 1]) translate([s > 0 ? HOOK_W / 2 : -HOOK_W / 2 - 1, -0.5]) {
        square([1, HOOK_ROOT]);
        translate([0.5, HOOK_ROOT]) circle(r = HOOK_RELIEF_R, $fn = 24);
    }
module hook_slot_local() {           // receiving slot in the lower ladder's top band
    translate([-HOOK_W / 2 - 1.2, -HOOK_NECK - 0.01]) square([HOOK_W + 1.4, HOOK_NECK + 1]);
    translate([-HOOK_W / 2 - 1.2, -(HOOK_DROP + 1)]) square([HOOK_W + 1.2 + HOOK_BARB + 1.0, HOOK_DROP + 1 - HOOK_NECK]);
}
module each_hook(k) for (i = [0 : len(HOOK_Y) - 1])
    in_row(k) translate([HOOK_Y[i], 0]) mirror([HOOK_DIR[i] < 0 ? 1 : 0, 0]) children();

// ------------------------------------------------------------------ 2D features
module windows_2d(k0, d0, k1, d1, z0 = undef) {
    y0 = PF + POST_W;
    y1 = PR - POST_W;
    a = is_undef(z0) ? [y0, line_z(k0, d0, y0)] : [y0, z0];
    b = is_undef(z0) ? [y1, line_z(k0, d0, y1)] : [y1, z0];
    offset(r = WIN_R) offset(delta = -WIN_R) difference() {
        polygon([a, b, [y1, line_z(k1, d1, y1)], [y0, line_z(k1, d1, y0)]]);
        hull() {
            translate(a) circle(d = BRACE_W);
            translate([y1, line_z(k1, d1, y1)]) circle(d = BRACE_W);
        }
    }
}
module latch_windows_2d(k) for (ly = LATCH_Y)
    in_row(k) translate([ly - 0.2, GROOVE_Z[0]]) square([LATCH_WIN, GROOVE_Z[1] - GROOVE_Z[0]]);
module jumper_2d(k)
    in_row(k) translate([JUMPER_Y[0], JUMPER_Z0 - 0.5]) square([JUMPER_Y[1] - JUMPER_Y[0], BAND_B + 2]);

// ------------------------------------------------------------------ 3D features
module ridge3(k)                     // along line z = 0 of row k (a top edge)
    intersection() {
        ladder_strip3();
        difference() {
            in_row3(k) hull() {
                translate([-60, -0.01, (PANEL_T - RIDGE_W) / 2]) cube([CARRIER_D + 120, 0.02, RIDGE_W]);
                translate([-60, RIDGE - 0.01, (PANEL_T - RIDGE_W) / 2 + RIDGE]) cube([CARRIER_D + 120, 0.01, RIDGE_W - 2 * RIDGE]);
            }
            for (hy = HOOK_Y) in_row3(k) translate([hy - RIDGE_GAP / 2, -1, -1]) cube([RIDGE_GAP, RIDGE + 2, PANEL_T + 2]);
        }
    }
module notch3(k)                     // along line z = 0 of row k (a bottom edge)
    difference() {
        in_row3(k) hull() {
            translate([-60, -0.5, (PANEL_T - RIDGE_W) / 2 - 0.2]) cube([CARRIER_D + 120, 0.5, RIDGE_W + 0.4]);
            translate([-60, RIDGE + 0.2 - 0.01, PANEL_T / 2 - 0.5]) cube([CARRIER_D + 120, 0.01, 1.0]);
        }
        for (hy = HOOK_Y) in_row3(k) translate([hy - RIDGE_GAP / 2, -1, -1]) cube([RIDGE_GAP, RIDGE + 4, PANEL_T + 2]);
    }
module grooves3(k)                   // tray runner grooves on both faces, open at the front
    in_row3(k) for (z = [-1, PANEL_T - GROOVE_D])
        translate([-40, GROOVE_Z[0], z]) cube([GROOVE_END + 40, GROOVE_Z[1] - GROOVE_Z[0], GROOVE_D + 1]);

module brace_holes3(zs)                // heat-set insert holes in the rear edge (in the ladder plane)
    for (z = zs) translate([PR + 1, z, PANEL_T / 2]) rotate([0, -90, 0]) {
        cylinder(d = BRACE_INSERT[0], h = BRACE_INSERT[1] + 1, $fn = 20);
        cylinder(d1 = BRACE_INSERT[0] + 0.8, d2 = BRACE_INSERT[0], h = 1.4, $fn = 20);     // lead-in
    }

// ------------------------------------------------------------------ parts
module ladder_row(k) {
    difference() {
        union() {
            linear_extrude(PANEL_T) difference() {
                union() {
                    band_quad(k, 0, k + 1, 0);
                    each_hook(k) hook_local();
                }
                windows_2d(k, BAND_B, k + 1, -BAND_T);
                each_hook(k) hook_relief_local();
                each_hook(k + 1) hook_slot_local();
                latch_windows_2d(k);
                jumper_2d(k);
            }
            ridge3(k + 1);
        }
        grooves3(k);
        notch3(k);
        brace_holes3(brace_z(k));
    }
}

module ladder_base() {
    difference() {
        union() {
            linear_extrude(PANEL_T) difference() {
                polygon([[PF, 0], [PR, 0], [PR, line_z(0, 0, PR)], [PF, line_z(0, 0, PF)]]);
                windows_2d(0, 0, 0, -BAND_T, z0 = FLOOR_BAND);
                each_hook(0) hook_slot_local();
                for (ly = LATCH_Y) translate([FLOOR_Y0 + ly - 0.2, GROOVE_Z[0]]) square([LATCH_WIN, GROOVE_Z[1] - GROOVE_Z[0]]);
            }
            ridge3(0);
        }
        // floor plate grooves (horizontal), open at the front
        for (z = [-1, PANEL_T - GROOVE_D])
            translate([PF - 1, GROOVE_Z[0], z]) cube([FLOOR_Y0 + FLOOR_D - PF + 1, GROOVE_Z[1] - GROOVE_Z[0], GROOVE_D + 1]);
        brace_holes3(brace_z(-1));
    }
}

module ladder_cap(k) {
    difference() {
        linear_extrude(PANEL_T) difference() {
            union() {
                offset(r = 3) offset(delta = -3) band_quad(k, 0, k, BAND_B);
                band_quad(k, 0, k, BAND_B / 2);              // keep the bottom corners sharp
                each_hook(k) hook_local();
            }
            each_hook(k) hook_relief_local();
            latch_windows_2d(k);
        }
        grooves3(k);
        notch3(k);
    }
}

if (PART == "row") ladder_row(ROW);
else if (PART == "base") ladder_base();
else if (PART == "cap") ladder_cap(ROW);
