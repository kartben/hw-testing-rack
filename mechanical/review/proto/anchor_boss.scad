// Review proto (not a part): one of the tray's two chain-anchor bosses, cut in half, today (a 5.5 mm boss
// with a 5.7 mm insert pocket: it goes 0.2 mm through the tray's floor, a hole in the first layer) and
// proposed (7.5 mm: 1.8 mm of floor under the insert).  docs/printed-parts-review.md › Chain anchor.
//
//   openscad -D 'VIEW="today"' -o anchor_boss_today.png mechanical/review/proto/anchor_boss.scad
VIEW = "today";
$fn = 48;
module boss(h) difference() {
    union() { translate([-10, -10, 0]) cube([20, 20, 2.5]); cylinder(d = 7.5, h = h); }
    translate([0, 0, h - 5.7]) cylinder(d = 4.0, h = 5.7 + 0.01);
    translate([0, 0, h - 0.6]) cylinder(d1 = 4.0, d2 = 4.8, h = 0.61);
    translate([-11, 0, -1]) cube([22, 12, 12]);          // half, to see the section
}
color("#a9c4e4") boss(VIEW == "today" ? 5.5 : 7.5);
color("#b87333") translate([0, 0, (VIEW == "today" ? 5.5 : 7.5) - 5.7]) difference() { cylinder(d = 4.0, h = 5.7); translate([0, 0, -1]) cylinder(d = 3, h = 8); translate([-5, 0, -1]) cube([10, 10, 10]); }
