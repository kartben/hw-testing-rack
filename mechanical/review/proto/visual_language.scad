// Review proto (not a part): the proposed visual language on a real part, the drawer (parts/drawer.scad as
// it is), its front-left corner.  Today: r 1.2 vertical edges straight onto the bed, a blank label.
// Proposed (accent): R3 on the panel's vertical edges, a 0.5 × 45° chamfer on the bed edge (the elephant's
// foot), the bay ID debossed 0.8 mm at the label's left end and filled by the second nozzle, `1 2 3 4` debossed
// 0.4 mm in the rear-bay floor in front of the ports.  The same rules go on every part (the ladders' outline and
// row letter, the fascia, the plates' FRONT arrow, the cradle's PT2.6 marks).
// docs/printed-parts-review.md › The visual language.
//
//   openscad -D 'VIEW="today"' -o visual_language_today.png mechanical/review/proto/visual_language.scad
include <_review.scad>
include <../../lib/carrier.scad>
use <../../parts/drawer.scad>
VIEW = "today";
FRONT_OVERHANG = DRAWER_X0 - 1;
X0 = -FRONT_OVERHANG; W = DRAWER_W + 2 * FRONT_OVERHANG; T = DRAWER_FRONT_T; H = DRAWER_FRONT_H;
R = 3; CH = 0.5; ID = "B3";
$fn = 48;
module corner_cutter(x, s) translate([x, 0, -1]) difference() { translate([s < 0 ? -1 : -R, -1, 0]) cube([R + 1, R + 1, H + 2]); translate([s < 0 ? R : 0, R, 0]) cylinder(r = R, h = H + 2); }
module corners() { corner_cutter(X0, -1); corner_cutter(X0 + W, 1); }   // the panel's two front vertical corners, cut square → R3
module corner_caps() for (x = [X0 + R, X0 + W - R]) translate([x, R, 0]) cylinder(r = R, h = H);
module chamfer_band() translate([X0, 0, 0]) rotate([90, 0, 90]) linear_extrude(W) polygon([[0, 0], [CH, 0], [0, CH]]);   // the bed edge, front face
module label_blank() color("#d8dde3") translate([DRAWER_W / 2, -0.95, H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(1.0) offset(r = 0.5) square([DRAWER_W - 26.4, 11.2 - 0.4], center = true);
module label_id() translate([DRAWER_W / 2, -0.95, H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1]) {
    color("#d8dde3") difference() { linear_extrude(1.0) offset(r = 0.5) square([DRAWER_W - 26.4, 11.2 - 0.4], center = true);
        translate([0, 0, -1]) linear_extrude(1.8) translate([-(DRAWER_W - 26.4) / 2 + 4, 0]) text(ID, size = 7, font = "Liberation Sans:style=Bold", halign = "left", valign = "center"); }
    changed() linear_extrude(0.8) translate([-(DRAWER_W - 26.4) / 2 + 4, 0]) text(ID, size = 7, font = "Liberation Sans:style=Bold", halign = "left", valign = "center");
}
module port_numbers() for (i = [0 : 3]) translate([DATA_X4_X0 + DATA_X4_USB[i], DRAWER_PORT_WALL_Y - DRAWER_WALL - 5, -0.01]) mirror([0, 0, 1])
    linear_extrude(0.4) mirror([1, 0, 0]) text(str(i + 1), size = 4.5, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");

if (VIEW == "today") { part() drawer(); label_blank(); }
else {
    part() difference() { drawer(); corners(); chamfer_band(); port_numbers(); }
    changed() { corner_caps(); }
    label_id();
}
