// Review proto (not a part): one of the tray's two chain-anchor bosses cut in half, the insert (copper), the
// anchor block and its M3 × 8 above (grey, translucent).  Today: a 5.5 mm boss with a 5.7 mm insert pocket:
// it goes 0.2 mm through the tray's 2.5 mm floor, a Ø4 hole in the first layer.  Proposed (accent): a 7.5 mm
// boss, 1.8 mm of floor under the insert.  docs/printed-parts-review.md › Chain anchor.
//
//   openscad -D 'VIEW="today"' -o anchor_boss_today.png mechanical/review/proto/anchor_boss.scad
include <_review.scad>
VIEW = "today";
$fn = 48;
module half() difference() { union() children(); translate([-20, 0, -5]) cube([40, 20, 40]); }   // the far half removed: a section
module floor_slab() translate([-10, -10, 0]) cube([20, 20, 2.5]);
module boss(h) difference() {
    cylinder(d = 7.5, h = h);
    translate([0, 0, h - 5.7]) cylinder(d = 4.0, h = 5.7 + 0.01);
    translate([0, 0, h - 0.6]) cylinder(d1 = 4.0, d2 = 4.8, h = 0.61);
}
module floor_cut(h) difference() { floor_slab(); translate([0, 0, h - 5.7]) cylinder(d = 4.0, h = 6); }
module insert(h) color("#b87333") translate([0, 0, h - 5.7]) difference() { cylinder(d = 4.0, h = 5.7); translate([0, 0, -1]) cylinder(d = 3, h = 8); }
module anchor(h) { mate(0.4) translate([-4, -8, h]) cube([8, 16, 9]); color("#8d8d8d", 0.7) translate([0, 0, h - 5.5]) { cylinder(d = 2.9, h = 8 + 5.5); translate([0, 0, h + 3 - h + 5.5]) cylinder(d = 5.6, h = 2); } }

if (VIEW == "today") half() { part() { floor_cut(5.5); boss(5.5); } insert(5.5); anchor(5.5); }
else half() { part() floor_cut(7.5); changed() boss(7.5); insert(7.5); anchor(7.5); }
