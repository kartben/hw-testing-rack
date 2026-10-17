// Label blank (12 × 100 mm) for the drawer front's label recess.
//
//   openscad -o bay_label.stl parts/label.scad
include <../lib/carrier.scad>

rbox([100, 12, 1.0], r = 1);
