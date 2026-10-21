// Review proto (not a part): the power box (parts/power_box.scad as it is) seen from the front with its lid on.
// Today: 5.25 mm bold capitals engraved 0.8 mm and inlaid in white on the front (A B C D under the LED pairs,
// PD, CTL), the rear (PD IN), the left wall (A–D at the row windows) and the lid (the rack's name, RESET,
// BOOT).  Proposed: the engravings filled (the walls plain), one small mark where a hand needs it: the row
// letters at the left-wall windows (plugging the rows), `PD IN` at the rear USB-C (the other USB-C is the
// console), the two pin holes on the lid left bare.  docs/printed-parts-review.md › Power box.
//
//   openscad -D 'VIEW="today"' -o power_box_labels_today.png mechanical/review/proto/power_box_labels.scad
include <_review.scad>
use <../../parts/power_box.scad>
VIEW = "today";
// the lid, modelled in place by power_box.scad; the box is 84 × 108 × 35
module box_today() { part() { base(); lid(); } color("#f2f1ec") { base_labels(inlay = true); lid_label(inlay = true); } }
module box_plain() part() { base(); lid(); base_labels(inlay = true); lid_label(inlay = true); }   // every engraving filled

if (VIEW == "today") box_today();
else box_plain();
