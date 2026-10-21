// Review proto (not a part): one wall of the camera pod's sleeve with the Mega's case in it (grey,
// translucent), printed as the pod is (upside down: the wall stands on the plate, the lip at its far end).
// Today: a rigid 1.6 mm wall with a 0.8 mm lip, bent across its layers each time the case goes in or out:
// 1.3 % (FEM 42 MPa), allowed 0.5 % for repeated use.  Proposed (accent): a tab 16 × 10 cut on three sides
// (0.6 slits), hinged on a vertical edge, a 0.5 mm lip on its free end: it bends in the print plane, 0.75 %.
// docs/printed-parts-review.md › Camera pod.
//
//   openscad -D 'VIEW="today"' -o sleeve_tab_today.png mechanical/review/proto/sleeve_tab.scad
include <_review.scad>
VIEW = "today";
SW = 1.6; W = 36; H = 12; PLATE = 3; LIP = 0.8; FIT = 0.3;
module plate() translate([-2, -10, 0]) cube([W + 4, 12, PLATE]);
module wall() translate([0, 0, PLATE - 0.01]) cube([W, SW, H]);
module lip_today() translate([W / 2 - 8, -LIP, PLATE + H - 1.2]) cube([16, LIP + 0.01, 1.2]);
module tab_cuts() {
    translate([W / 2 - 8 + 16, -1, PLATE + 1]) cube([0.6, SW + 2, 10]);
    translate([W / 2 - 8, -1, PLATE + 1]) cube([16.6, SW + 2, 0.6]);
    translate([W / 2 - 8, -1, PLATE + 1 + 10 - 0.6]) cube([16.6, SW + 2, 0.6]);
}
module tab_region() translate([W / 2 - 8 - 0.3, -1.5, PLATE + 1 - 0.3]) cube([16.9, SW + 3, 10.6]);
module lip_tab() translate([W / 2 - 8 + 10, -0.5, PLATE + 1 + 2]) cube([5.5, 0.51, 6]);
// the camera's case against the wall, its lens face at the top (printed upside down: the case goes in from above)
module case() mate(0.4) translate([1, -FIT - 34, PLATE]) cube([W - 2, 34, H - 1.2]);

if (VIEW == "today") { part() { plate(); wall(); lip_today(); } case(); }
else {
    part() { plate(); difference() { wall(); tab_cuts(); tab_region(); } }
    changed() { difference() { intersection() { wall(); tab_region(); } tab_cuts(); } lip_tab(); }
    case();
}
