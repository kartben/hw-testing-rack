"""Print pin numbers/names/types of library symbols:  python pins.py Lib:Sym ..."""
import sys
from eda import LIB
for lid in sys.argv[1:]:
    sd = LIB.get(lid)
    print(f"== {lid}  bbox={tuple(round(v,2) for v in sd.bbox)}")
    print("   " + ", ".join(f"{p.number}:{p.name}({p.etype[:3]}{',H' if p.hidden else ''})" for p in sd.pins))
