// Bay label for the drawer front's label recess (116 × 12.4 × 0.9): 100 × 12 × 1.0, the bay's ID in 7 mm
// capitals debossed 0.8 mm into the face that shows and filled by the H2D's second nozzle, flush: one object,
// two colours (docs/printed-parts-review.md, finding 12).  That face prints on the bed, the crispest there is,
// so the text is mirrored here and reads right on the drawer.  The two parts register:
//
//   openscad -D 'ID="B3"' -D 'PART="body"'  -o bay_label_b3.stl       parts/label.scad
//   openscad -D 'ID="B3"' -D 'PART="inlay"' -o bay_label_b3_inlay.stl parts/label.scad
//
// In Bambu Studio, load both files at once and answer "yes" to loading them as one object with multiple
// parts; give the inlay the light filament (docs/mechanical.md).  No ID: a blank, for 12 mm tape instead.
include <../lib/carrier.scad>

ID = "";
PART = "body";                          // body | inlay
SIZE = [100, 12, 1.0];
TEXT = [7.3, 0.8];                      // text size (7 mm capitals, Liberation Sans Bold), depth

module id_2d() translate([SIZE[0] / 2, SIZE[1] / 2]) mirror([1, 0])
    text(ID, size = TEXT[0], font = "Liberation Sans:style=Bold", halign = "center", valign = "center");

if (PART == "inlay") linear_extrude(TEXT[1]) id_2d();
else difference() {
    rbox(SIZE, r = 1);
    if (ID != "") translate([0, 0, -EPS]) linear_extrude(TEXT[1] + EPS) id_2d();
}
