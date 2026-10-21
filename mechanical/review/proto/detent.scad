// Review proto (not a part): the drawer's closed-position detent, on a slice of the tray's left ledge, today
// (a 6 × 3 magnet glued in a pocket of the ledge's pad, its twin under the drawer) and proposed (a spring
// tab cut in the ledge, 20 × 2.5 with a 0.6 mm bump, 0.56 % in the print plane, ≈ 3 N; a notch under the
// drawer).  docs/printed-parts-review.md › Drawer.
//
//   openscad -D 'VIEW="today"' -o detent_today.png mechanical/review/proto/detent.scad
VIEW = "today";
LEDGE_X = 12; LEDGE_T = 2.5; L = 40; WALL = 2;
$fn = 48;
module ledge() { cube([WALL, L, 12]); translate([0, 0, 9.5]) cube([LEDGE_X, L, LEDGE_T]); }
module today() {
    difference() {
        union() { ledge(); translate([0, L / 2 - 5, 9.5]) cube([LEDGE_X + 4, 10, LEDGE_T]); }   // the widened pad
        translate([LEDGE_X + 1, L / 2, 9.5 + LEDGE_T - 3.2]) cylinder(d = 6.25, h = 4);          // the magnet pocket
    }
    color("#777") translate([LEDGE_X + 1, L / 2, 9.5 + LEDGE_T - 3.1]) cylinder(d = 6, h = 3);   // the magnet
}
module proposed() {
    difference() {
        ledge();
        // the tab: freed by two 0.8 mm slits along y, 20 mm long, hinged at its rear end
        for (x = [LEDGE_X - 5.5, LEDGE_X - 2.2]) translate([x, L / 2 - 10, 9]) cube([0.8, 20, 4]);
        translate([LEDGE_X - 5.5, L / 2 - 10, 9]) cube([4.1, 0.8, 4]);
    }
    // the bump on the tab's free end, 45° both ways: it drops into a notch under the drawer when closed
    translate([LEDGE_X - 4.7, L / 2 - 8, 9.5 + LEDGE_T - 0.01]) rotate([90, 0, 90]) linear_extrude(2.5) polygon([[0, 0], [0.6, 0.6], [2.4, 0.6], [3, 0]]);
}
color("#a9c4e4") if (VIEW == "today") today(); else proposed();
