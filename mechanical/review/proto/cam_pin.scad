// Review proto (not a part): the cam base's split pivot with the cam's flange on it (grey, translucent).
// Today: a Ø3.4 pin, 0.8 slit 4.5 deep, Ø3.9 head: each half-pin bends 0.25 mm across its layers to pass
// the cam's Ø3.6 bore, 2.4 % at the root (FEM 64 MPa), allowed 1 %.  Proposed (accent): a Ø4.4 × 2 relief in
// the column's top, the slit 6.5 deep, head Ø3.7: 0.15 mm, 0.7 % (FEM 20 MPa).
// docs/printed-parts-review.md › Pegs.
//
//   openscad -D 'VIEW="today"' -o cam_pin_today.png mechanical/review/proto/cam_pin.scad
include <_review.scad>
VIEW = "today";
H = 10; CAM_FLANGE = 1.0; CAM_RISE = 3.6; PIVOT_D = 3.4;
$fn = 48;
module column(relief) difference() {
    cylinder(d1 = 8.5, d2 = 7.0, h = H - CAM_FLANGE);
    if (relief) translate([0, 0, H - CAM_FLANGE - relief]) cylinder(d = 4.4, h = relief + 1);
}
module pin(head, split) difference() {
    union() {
        cylinder(d = PIVOT_D, h = H - CAM_FLANGE + CAM_RISE);
        translate([0, 0, H - CAM_FLANGE + CAM_RISE]) cylinder(d1 = head, d2 = PIVOT_D - 0.6, h = 0.8);
    }
    translate([-0.4, -5, H - CAM_FLANGE + CAM_RISE - split]) cube([0.8, 10, 10]);
}
module cam() mate(0.4) translate([0, 0, H - CAM_FLANGE]) difference() { cylinder(d = 9, h = CAM_FLANGE + 2.2); translate([0, 0, -1]) cylinder(d = PIVOT_D + 0.2, h = 6); }

if (VIEW == "today") { part() { column(0); pin(3.9, 4.5); } cam(); }
else { part() column(2); changed() pin(3.7, 6.5); cam(); }
