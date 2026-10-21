// Review proto (not a part): the power box (parts/power_box.scad as it is) seen from the front with its lid
// on, its markings three ways.  Today: 5.25 mm bold capitals engraved 0.8 mm and inlaid in white on the front
// (A B C D under the LED pairs, PD, CTL), the rear (PD IN), the left wall (A–D at the row windows) and the lid
// (the rack's name, RESET, BOOT).  "plain": the walls bare but the two marks a hand needs, the row letters at
// the left-wall windows and PD IN at the rear USB-C (the other USB-C is the console).  "small": the same, plus
// 3 mm letters debossed 0.4 mm (no inlay) under the LED pairs (A B C D), PD, CTL and RESET / BOOT on the lid;
// the rack's name dropped in both.  The preview (OpenCSG) does not render letters cut out of a wall reliably,
// so the proposed marks are drawn as paint on the wall, 0.05 mm proud: white for an inlay, dark for a deboss.
// docs/printed-parts-review.md › Power box.
//
//   openscad -D 'VIEW="today"' -o power_box_labels_today.png mechanical/review/proto/power_box_labels.scad
//   VIEW = today | plain | small
include <_review.scad>
include <../../parts/power_box.scad>
PART = "none";                               // after the include (the last assignment wins): the box's modules and sizes, none of its own geometry
VIEW = "today";
// the box's own engravings, switched off unless today's view (the main file's definition wins)
module base_labels(inlay = false) if (VIEW == "today") base_labels_today(inlay);
module lid_label(inlay = false) if (VIEW == "today") lid_label_today(inlay);

// as power_box.scad draws them
module base_labels_today(inlay) {
    for (i = [0 : len(HUB_ROWS) - 1]) engrave(ROW_NAMES[i], [0, hub_xy([0, HUB_ROWS[i]])[1], (HUB_TOP - 0.6 + ROW_CUT[1] + HB) / 2], -90, inlay);
    for (i = [0 : 3]) engrave(ROW_NAMES[i], [HUB_X0 + HUB_LEDS[i], 0, USB_BOTTOM - 4], 0, inlay);
    engrave("PD", [HUB_X0 + HUB_LEDS[4], 0, HB - 3.4], 0, inlay);
    engrave("CTL", [HUB_X0 + (HUB_LEDS[5] + HUB_USB) / 2, 0, USB_BOTTOM - 4], 0, inlay);
    engrave("PD IN", [HUB_X0 + HUB_PD, D, USB_BOTTOM - 4], 180, inlay);
}
module lid_label_today(inlay) translate([0, 0, HB + LID_T - TEXT[1]]) linear_extrude(TEXT[1] + (inlay ? 0 : EPS)) {
    translate([W / 2, D / 2 - 8]) rotate(90) label("hw-testing-rack · power", 7);
    for (i = [0 : 1]) translate(hub_xy(HUB_BUTTONS[i]) + [BUTTON_PIN[1] / 2 + 1.5, 0]) label(BUTTON_NAMES[i], halign = "left");
}
// a mark painted on a wall's outer face: p its centre on that face, rz 0 front / -90 left / 180 rear (as
// engrave()), local +z is the outward normal
PROUD = 0.05;
module mark(t, p, rz, size, halign = "center") translate(p) rotate([90, 0, rz]) translate([0, 0, -0.3]) linear_extrude(0.3 + PROUD, convexity = 10)
    text(t, size = size, font = "Liberation Sans:style=Bold", halign = halign, valign = "center");
module lid_mark(t, p, size, halign = "center") translate([p[0], p[1], HB + LID_T - 0.3]) linear_extrude(0.3 + PROUD, convexity = 10)
    text(t, size = size, font = "Liberation Sans:style=Bold", halign = halign, valign = "center");
// what every proposed view keeps (inlaid, as today): the row letters at the windows, PD IN at the rear
module kept_marks() color("#f2f1ec") {
    for (i = [0 : len(HUB_ROWS) - 1]) mark(ROW_NAMES[i], [0, hub_xy([0, HUB_ROWS[i]])[1], (HUB_TOP - 0.6 + ROW_CUT[1] + HB) / 2], -90, TEXT[0]);
    mark("PD IN", [HUB_X0 + HUB_PD, D, USB_BOTTOM - 4], 180, TEXT[0]);
}
// the small option: 3 mm capitals debossed 0.4 mm, no inlay: drawn dark, as they read by their shadow
SMALL = 3.0;
module small_marks() color("#4d5663") {
    for (i = [0 : 3]) mark(ROW_NAMES[i], [HUB_X0 + HUB_LEDS[i], 0, USB_BOTTOM - 3.2], 0, SMALL);
    mark("PD", [HUB_X0 + HUB_LEDS[4], 0, HB - 3.0], 0, SMALL);
    mark("CTL", [HUB_X0 + (HUB_LEDS[5] + HUB_USB) / 2, 0, USB_BOTTOM - 3.2], 0, SMALL);
    for (i = [0 : 1]) lid_mark(BUTTON_NAMES[i], hub_xy(HUB_BUTTONS[i]) + [BUTTON_PIN[1] / 2 + 1.5, 0], SMALL, "left");
}

if (VIEW == "today") { part() { base(); lid(); } color("#f2f1ec") { base_labels_today(true); lid_label_today(true); } }
else if (VIEW == "plain") { part() { base(); lid(); } kept_marks(); }
else { part() { base(); lid(); } kept_marks(); small_marks(); }
