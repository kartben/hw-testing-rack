// Roof deck — closes the top of the rack above each top-row bay and gives
// the top-row camera pods the same insert pattern as a carrier's ceiling.
// The top surface has an M3 insert grid (25 mm) for accessories: a USB hub,
// a small switch, an Ethernet-to-Wi-Fi bridge, a status display...
// Print: top face down, PETG/ASA, no supports.
include <../lib/carrier.scad>

ROOF_T = 4;

module roof_deck() {
    difference() {
        union() {
            rbox([CARRIER_W, CARRIER_D, ROOF_T], r = 3);
            // perimeter lip hides the beam slots
            difference() {
                rbox([CARRIER_W, CARRIER_D, ROOF_T + 3], r = 3);
                translate([2, 2, -EPS]) rbox([CARRIER_W - 4, CARRIER_D - 4, ROOF_T + 4], r = 2);
            }
        }
        for (c = cam_inserts()) translate([c[0], c[1], 0]) mirror([0, 0, 1]) insert_hole(INSERT_M3);
        for (x = [20 : 25 : CARRIER_W - 20], y = [30 : 25 : CARRIER_D - 30])
            if (min([for (c = cam_inserts()) norm([x, y] - c)]) > 8)
                translate([x, y, ROOF_T]) insert_hole(INSERT_M3);
        for (y = [FRAME_PROFILE / 2, CARRIER_D - FRAME_PROFILE / 2], x = [26, CARRIER_W - 26])
            translate([x, y, -EPS]) {
                cylinder(d = M5_CLEAR, h = ROOF_T + 1);
                translate([0, 0, ROOF_T - 3]) cylinder(d = 9.5, h = 3 + EPS);
            }
        // camera cable pass-through at the rear
        translate([CAM_CABLE_HOLE[0], CARRIER_D - 14, -EPS]) rslot(12, 5, ROOF_T + 1);
    }
}

roof_deck();
