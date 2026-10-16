#!/usr/bin/env bash
# Photoreal renders (Blender Cycles, headless, in Docker).
#
#   tools/render.sh                 # hero, side, drawer, exploded → docs/img/
#   SAMPLES=256 tools/render.sh hero
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python}"
[ -x "$REPO/.venv/Scripts/python.exe" ] && PY="$REPO/.venv/Scripts/python.exe"
[ -x "$REPO/.venv/bin/python" ] && PY="$REPO/.venv/bin/python"
IMAGE=hw-testing-rack/blender
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" "$REPO/render"
if command -v cygpath >/dev/null 2>&1; then MOUNT="$(cygpath -m "$REPO")"; export MSYS_NO_PATHCONV=1; else MOUNT="$REPO"; fi
SHOTS="${*:-hero side drawer exploded}"
SAMPLES="${SAMPLES:-128}"

"$PY" "$REPO/tools/assembly_glb.py"
case " $SHOTS " in *" exploded "*) "$PY" "$REPO/tools/assembly_glb.py" --explode-bay C3 --out "$REPO/render/bay-exploded.glb" ;; esac

for shot in $SHOTS; do
  glb=render/assembly.glb
  [ "$shot" = exploded ] && glb=render/bay-exploded.glb
  docker run --rm -v "$MOUNT:/work" -w /work "$IMAGE" -b --factory-startup -P render/render.py -- \
    --glb "$glb" --shot "$shot" --samples "$SAMPLES" --out "docs/img/$shot.jpg" 2>&1 | grep -E "rendered|Error" || true
done
