#!/bin/sh
# Before/after pairs: every proto rendered twice (VIEW=today, VIEW=proposed) from one fixed camera, framed
# on the feature; compose.py then puts the two side by side (AVANT | APRÈS) with callouts.  From the repo root:
#   sh mechanical/review/proto/pairs.sh          -> mechanical/review/pairs/<name>_{today,proposed}.png
O="${OPENSCAD:-/c/Program Files/OpenSCAD/openscad.exe}"
cd "$(dirname "$0")/../.." || exit 1
mkdir -p review/pairs
# name  cx,cy,cz,rotx,roty,rotz,dist   (OpenSCAD gimbal camera, orthographic)
pair() { name=$1; cam=$2
  for v in today proposed; do
    "$O" --preview --imgsize=1000,760 --projection=o --colorscheme=Tomorrow --camera="$cam" -D "VIEW=\"$v\"" \
      -o "review/pairs/${name}_$v.png" "review/proto/$name.scad" 2>&1 | grep -i "error"
  done; }
pair tray_guide      6,30,22,90,0,0,32
pair cradle_finger   5,4,60,55,0,150,58
pair ladder_nut_trap 16,12,3,48,0,215,30
pair cam_pin         0,0,11.5,65,0,20,16
pair ladder_hook     0.5,-2,3.7,25,0,15,34
pair latch_arm       -2,46,10.5,70,0,270,58
pair sleeve_tab      18,-6,9,60,0,15,40
pair anchor_boss     0,-3,5,70,0,0,24
pair detent          10,20,11,55,0,30,36
pair peg_skin        0,0,-2.5,150,0,20,20
pair visual_language 14,0,12,100,0,20,66
ls review/pairs | wc -l
