// Camera pod — hangs from a bay's ceiling (the bottom plate of the carrier
// above, or the roof deck for the top row) and looks down at the board.
//
//   -D 'PART="mount"'   ceiling plate with two hinge lugs (4 × M3 into the ceiling inserts)
//   -D 'PART="cradle"'  tilting cradle for a Seeed XIAO ESP32S3 Sense, lens down
//
// The cradle pivots on an M3×30 screw (±35°) so the lens can be aimed at the
// board: the insert pattern is offset from the bay centre (it has to dodge
// the node and the chain in the plenum above), and in a double-width bay the
// pod hangs from the left half.
// Power: 5 V from the bay node's CAM connector (JST-PH 2-pin) of the carrier
// it hangs from.  Use a ≥120° lens: at ~90 mm a 66° lens only sees ~94×70 mm.
// Print: mount flat; cradle lens-window down. PETG, no supports.
include <../lib/carrier.scad>

PART = "mount";
XIAO = [21.0, 17.8, 15.0];        // board + Sense expansion stack
LUG_GAP = XIAO[0] + 2 * 2.0 + 1.0; // cradle outer width + clearance
PIVOT_Z = -14;                     // pivot axis below the ceiling
LENS_OFFSET_X = 0;                 // lens under the mount; tilt the cradle to aim at the board

module mount() {
    p = CAM_MOUNT[2];
    difference() {
        union() {
            translate([-p / 2 - 6, -p / 2 - 6, -3]) rbox([p + 12, p + 12, 3], r = 4);
            // two lugs carrying the pivot, offset so the lens sits at the bay centre
            for (sx = [-1, 1]) translate([LENS_OFFSET_X + sx * (LUG_GAP / 2 + 1.5) - 1.5, -6, PIVOT_Z - 5])
                cube([3, 12, -PIVOT_Z + 5 - 3 + EPS]);
            translate([LENS_OFFSET_X - LUG_GAP / 2 - 3, -6, -3]) cube([LUG_GAP + 6, 12, 3]);
        }
        for (x = [-p / 2, p / 2], y = [-p / 2, p / 2]) translate([x, y, -4]) {
            cylinder(d = M3_CLEAR, h = 5);
            cylinder(d = 6.2, h = 1.6);   // head recess (screws go up into the ceiling)
        }
        translate([LENS_OFFSET_X - LUG_GAP, 0, PIVOT_Z]) rotate([0, 90, 0]) cylinder(d = M3_CLEAR, h = 2 * LUG_GAP);
        // cable notch
        translate([-p / 2 - 7, -3, -4]) cube([6, 6, 5]);
    }
}

module cradle() {
    w = XIAO[0] + 4; d = XIAO[1] + 4; h = XIAO[2] + 3;
    difference() {
        union() {
            translate([-w / 2, -d / 2, -h]) rbox([w, d, h], r = 2);
            // pivot ears
            for (s = [-1, 1]) translate([s * (w / 2 - 1.5) - 1.5, -5, -6]) cube([3, 10, 12]);
        }
        translate([-XIAO[0] / 2 - 0.2, -XIAO[1] / 2 - 0.2, -h + 2]) cube([XIAO[0] + 0.4, XIAO[1] + 0.4, h]);
        translate([0, 0, -h - EPS]) cylinder(d = 11, h = 3);                 // lens window
        translate([-XIAO[0] / 2 - 3, -4.5, -h + 4]) cube([4, 9, 6]);       // USB-C / wire exit
        translate([-w, 0, 3]) rotate([0, 90, 0]) cylinder(d = 3.0, h = 2 * w); // pivot (self-tapping M3)
    }
}

if (PART == "mount") rotate([180, 0, 0]) mount(); else rotate([180, 0, 0]) cradle();
