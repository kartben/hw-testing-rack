#!/bin/sh
# Renders the review protos to mechanical/review/*.png (OpenSCAD 2021 preview: colours kept; orthographic,
# the whole proto fitted).  From the repo root:   sh mechanical/review/proto/render.sh
O="${OPENSCAD:-/c/Program Files/OpenSCAD/openscad.exe}"
cd "$(dirname "$0")/../.." || exit 1
R=review
shot() { name=$1; rot=$2; shift 2; "$O" --preview --imgsize=1400,900 --projection=o --viewall --autocenter --colorscheme=Tomorrow --camera="0,0,0,$rot,0" "$@" -o "$R/$name.png" "$R/proto/$name.scad" 2>&1 | grep -i "error" ; }
shot ladder_nut_trap 50,0,215
shot tray_guide 118,0,30
shot cradle_finger 62,0,320
shot cam_pin 65,0,20
shot drawer_front 75,0,350
ls -la $R/*.png
