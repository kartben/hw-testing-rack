// Review proto (not a part): the drawer's front panel, today (r 1.2 vertical edges, a label recess for a
// blank 100 × 12 strip or tape) and proposed (the same panel with a 0.6 mm × 45° chamfer on the bed edge
// against the elephant's foot, R 2 on the top edges, and the bay label as a two-colour inlay: the ID
// debossed 0.8 mm into the label strip, the second nozzle filling it).  docs/printed-parts-review.md ›
// Drawer, Label.
//
//   openscad -D 'VIEW="both"' -o drawer_front.png mechanical/review/proto/drawer_front.scad
VIEW = "both";
W = 156; H = 30; T = 4; ID = "B3";
$fn = 48;
module rbox(size, r) hull() for (x = [r, size[0] - r], y = [r, size[1] - r]) translate([x, y, 0]) cylinder(r = r, h = size[2]);
module scoop() translate([W / 2, -0.01, H]) rotate([-90, 0, 0]) scale([1, 0.32, 1]) cylinder(r = 28, h = T + 0.02, $fn = 96);
module recess() translate([W / 2, -0.01, H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(0.9) offset(r = 0.6) square([W - 40, 11.2], center = true);

module today() {
    color("#a9c4e4") difference() { rbox([W, T, H], 1.2); scoop(); recess(); }
    color("#f4f4f4") translate([W / 2, -0.9, H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(1.0) offset(r = 0.5) square([W - 40 - 0.4, 11.2 - 0.4], center = true);   // the blank label
}

// chamfered foot, rounded top: the panel as a hull of its bottom (inset 0.6) and its top (r 2 fillet approximated by a 45° step + offset)
module panel_proposed() hull() {
    translate([0.6, 0.6, 0]) rbox([W - 1.2, T - 1.2, 0.01], 0.6);                         // the bed edge, 0.6 in: a 45° chamfer up to z 0.6
    translate([0, 0, 0.6]) rbox([W, T, H - 2.6], 1.2);
    translate([0.8, 0.8, H - 2]) rbox([W - 1.6, T - 1.6, 1.4], 0.6);                      // the top edge eased
    translate([2, 2, H - 0.01]) rbox([W - 4, T - 4, 0.01], 0.4);
}
module proposed() {
    color("#a9c4e4") difference() { panel_proposed(); scoop(); recess(); }
    // the label strip with its ID debossed, filled by the second nozzle (two colours, one object)
    translate([W / 2, -0.9, H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1]) {
        color("#f4f4f4") difference() {
            linear_extrude(1.0) offset(r = 0.5) square([W - 40 - 0.4, 11.2 - 0.4], center = true);
            translate([0, 0, -1]) linear_extrude(1.8) text(ID, size = 7, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
        }
        color("#1d2b22") linear_extrude(0.8) text(ID, size = 7, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");
    }
}

if (VIEW == "today" || VIEW == "both") today();
if (VIEW == "proposed" || VIEW == "both") translate([0, 0, VIEW == "both" ? -40 : 0]) proposed();
