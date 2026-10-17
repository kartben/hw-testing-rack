"""One assembled bay as a STEP, for an interference check: printed parts only (no screws, inserts or node).

    freecadcmd tools/notice/fit_check.py      -> <build>/out/sc_bay.step
    solidcraft-cli run check.json --in sc_bay.step --results
        with check.json = {"commands": [{"command": "inspect.interference", "params": {}},
                                        {"command": "inspect.clearance", "params": {"clearance": 0.3}}]}
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import FreeCAD as App
import Import
import notice as N

ids = ["lb0", "lb1", "la0", "la1", "lc0", "lc1", "fp0", "tr0", "dr0", "cp0", "bb0", "ba0"]
doc = App.newDocument("check")
objs = []
for iid in ids:
    o = doc.addObject("Part::Feature", iid)
    o.Label = iid
    o.Shape = N.shape_of(iid)
    objs.append(o)
doc.recompute()
Import.export(objs, os.path.join(N.OUT, "sc_bay.step"))
N.log("sc_export_check", len(objs), "bodies")
