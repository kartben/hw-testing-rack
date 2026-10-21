// Shared by the review protos: the colours of a before/after pair.  The part in a neutral grey-blue, the
// geometry a proposal changes in the accent, the parts it mates with in a translucent grey.
NEUTRAL = "#b9c6d6";
ACCENT = "#ff7a1a";
MATE = "#6f7782";
MATE_A = 0.45;
PCB = "#2f6f4f";
module part() color(NEUTRAL) children();
module changed() color(ACCENT) children();
module mate(a = MATE_A) color(MATE, a) children();
