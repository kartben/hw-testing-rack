#!/bin/sh
# Before/after pairs: every proto rendered twice (VIEW=today, VIEW=proposed) from one fixed camera, framed
# on the feature; compose.py then puts the two side by side with callouts.  From the repo root:
#   sh mechanical/review/proto/pairs.sh          -> mechanical/review/pairs/<name>_{today,proposed}.png
O="${OPENSCAD:-/c/Program Files/OpenSCAD/openscad.exe}"
cd "$(dirname "$0")/../.." || exit 1
mkdir -p review/pairs
# name  cx,cy,cz,rotx,roty,rotz,dist   (OpenSCAD gimbal camera, orthographic)
pair() { name=$1; cam=$2
  for v in today proposed; do
    "$O" --preview --imgsize=900,700 --projection=o --colorscheme=Tomorrow --camera="$cam" -D "VIEW=\"$v\"" \
      -o "review/pairs/${name}_$v.png" "review/proto/$name.scad" 2>&1 | grep -i "error"
  done; }
pair tray_guide      6,30,20,90,0,0,40
pair cradle_finger   5,3,66,62,0,320,40
pair ladder_nut_trap 16,12,5,50,0,215,38
pair cam_pin         0,0,11.5,65,0,20,18
pair drawer_front    78,0,12.6,78,0,350,70
pair ladder_hook     0.5,-3,3.7,25,0,15,42
pair latch_arm       -1,46,10.5,70,0,270,70
pair sleeve_tab      18,0,9,60,0,15,45
pair anchor_boss     0,-3,4,70,0,0,28
pair detent          10,20,11,55,0,30,45
pair peg_skin        0,0,-2.5,150,0,20,22
ls review/pairs | wc -l
