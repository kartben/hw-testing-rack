# Assembly notice line art (FreeCAD)

The drawings of the IKEA-style assembly notice — the steps, their detail
circles, the part thumbnails and the hardware icons — are drawn by FreeCAD from
the same OpenSCAD sources as the prints:

```bash
python tools/notice/run.py                 # every drawing → mechanical/build/notice/out/*.svg
python tools/notice/run.py a3 pin          # some of them
```

How:

* **Exact solids, no meshes.**  OpenSCAD exports each part's evaluated tree
  (`openscad -o part.csg`); `csg2part.py` rebuilds it with OpenCASCADE: real
  circles and cylinders, exact hulls of circles, polygons only where the part
  has them (the hexagon reliefs).  Volumes match the STLs to 0.1 %.
* **Real fasteners.**  ISO 7045 pan-head Phillips screws and heat-set inserts
  from FreeCAD's Fasteners workbench, threads included.
* **The bay node from KiCad.**  `kicad-cli pcb export step`, with simple bodies
  for the parts the KiCad library has no 3D model for (`node.py`).
* **One hidden-line projection per drawing.**  `notice.py` places the parts as
  in the rack (the step's new parts at their approach position), projects the
  whole compound once with TechDraw (`projectEx`: visible sharp edges and
  outlines, no hidden or tangent lines), then gives each visible edge back to
  the part it lies on, so parts already in place are drawn light grey, new
  ones black, fasteners thinner.  Dashed screw axes go through the same
  projection.  Each drawing is fitted to its slot on the A4 page, clear of the
  page's detail circle and "click!" bubble.

`fit_check.py` writes one assembled bay as a STEP for an interference check
(`inspect.interference` in SolidCraft found the drawer magnet boss hitting the
tray's guide lip; fixed).

Needs FreeCAD 1.x with the Fasteners workbench (`FREECADCMD=` if `freecadcmd`
is not on the path), OpenSCAD, and kicad-cli or Docker for the bay node.
Projections are cached in `mechanical/build/notice/out/cache/`; `run.py`
always recomputes them.
