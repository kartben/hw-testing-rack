// Review proto (not a part): the cam base's split pivot, today (Ø3.4 pin, 0.8 slit 4.5 deep, Ø3.9 head:
// 0.25 mm of bend per half-pin across the layers, 2.4 % at the root) and proposed (the slit 6.5 deep
// through a Ø4.4 × 2 relief in the column's top, Ø3.7 head: 0.15 mm, 0.7 %).  Printed standing on its
// plug, as today.  docs/printed-parts-review.md › Pegs.
//
//   openscad -D 'VIEW="both"' -o cam_pin.png mechanical/review/proto/cam_pin.scad
VIEW = "both";
H = 10; CAM_FLANGE = 1.0; CAM_RISE = 3.6; PIVOT_D = 3.4;
$fn = 48;
module base(head = 3.9, split = 4.5, relief = 0) {
    difference() {
        cylinder(d1 = 8.5, d2 = 7.0, h = H - CAM_FLANGE);
        if (relief) translate([0, 0, H - CAM_FLANGE - relief]) cylinder(d = 4.4, h = relief + 1);
    }
    difference() {
        union() {
            cylinder(d = PIVOT_D, h = H - CAM_FLANGE + CAM_RISE);
            translate([0, 0, H - CAM_FLANGE + CAM_RISE]) cylinder(d1 = head, d2 = PIVOT_D - 0.6, h = 0.8);
        }
        translate([-0.4, -5, H - CAM_FLANGE + CAM_RISE - split]) cube([0.8, 10, 10]);
    }
}
module cam_ghost() color("#f0a060", 0.35) translate([0, 0, H - CAM_FLANGE]) difference() { cylinder(d = 7, h = CAM_FLANGE); translate([0, 0, -1]) cylinder(d = PIVOT_D + 0.2, h = 5); }

if (VIEW == "today" || VIEW == "both") { color("#a9c4e4") base(); cam_ghost(); }
if (VIEW == "proposed" || VIEW == "both") translate([VIEW == "both" ? 14 : 0, 0, 0]) { color("#a9c4e4") base(3.7, 6.5, 2); cam_ghost(); }
