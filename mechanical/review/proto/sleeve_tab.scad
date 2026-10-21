// Review proto (not a part): one wall of the camera pod's sleeve, printed as the pod is (upside down: the
// wall stands on the plate, the lip at its far end), today (a rigid 1.6 mm wall with a 0.8 mm lip: the
// whole wall bends across its layers, 1.3 %, the FEM's 42 MPa at the root) and proposed (a tab 16 × 10 cut
// on three sides, hinged on a vertical edge, a 0.5 mm lip on its free end: it bends in the print plane,
// 0.75 %).  docs/printed-parts-review.md › Camera pod.
//
//   openscad -D 'VIEW="today"' -o sleeve_tab_today.png mechanical/review/proto/sleeve_tab.scad
VIEW = "today";
SW = 1.6; W = 36; H = 12; PLATE = 3; LIP = 0.8;
module plate() translate([-2, -6, 0]) cube([W + 4, 8, PLATE]);
module wall_today() {
    translate([0, 0, PLATE - 0.01]) cube([W, SW, H]);
    translate([W / 2 - 8, -LIP, PLATE + H - 1.2]) cube([16, LIP + 0.01, 1.2]);     // the lip, inwards (-y)
}
module wall_proposed() {
    difference() {
        translate([0, 0, PLATE - 0.01]) cube([W, SW, H]);
        // three slits (0.6) round a 16 × 10 tab, its hinge on the left vertical edge
        translate([W / 2 - 8 + 16, -1, PLATE + 1]) cube([0.6, SW + 2, 10]);
        translate([W / 2 - 8, -1, PLATE + 1]) cube([16.6, SW + 2, 0.6]);
        translate([W / 2 - 8, -1, PLATE + 1 + 10 - 0.6]) cube([16.6, SW + 2, 0.6]);
    }
    translate([W / 2 - 8 + 10, -0.5, PLATE + 1 + 2]) cube([5.5, 0.51, 6]);          // the lip on the tab's free end
}
color("#a9c4e4") { plate(); if (VIEW == "today") wall_today(); else wall_proposed(); }
