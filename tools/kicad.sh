#!/usr/bin/env bash
# Run the electronics generator inside the official KiCad Docker image.
#
#   tools/kicad.sh bay-node                 # schematic + placed PCB + ERC/DRC
#   tools/kicad.sh bay-node --route         # + Freerouting (Java, in eclipse-temurin:25-jre)
#   tools/kicad.sh bay-node --route --fab   # + gerbers, CPL, BOM, PDF, renders, STEP/GLB
#   tools/kicad.sh bay-node --ses [--fab]   # re-import the last Freerouting session (no re-route)
#   tools/kicad.sh bay-node --check [--fab] # ERC + read-only DRC of the PCB as it is (CI), + fab outputs
#   tools/kicad.sh bay-node --fab           # same as --check --fab
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${KICAD_IMAGE:-kicad/kicad:10.0-full}"
JRE="${JRE_IMAGE:-eclipse-temurin:25-jre}"
FR_VER=2.5.0
FR_JAR="$REPO/.cache/freerouting/freerouting-$FR_VER.jar"
BOARD="$1"; shift
ROUTE=0; SES=0; CHECK=0; FAB=""
for a in "$@"; do case "$a" in
  --route) ROUTE=1 ;; --ses) SES=1 ;; --check) CHECK=1 ;; --fab) FAB="--fab" ;;
  *) echo "unknown option: $a" >&2; exit 2 ;;
esac; done
if command -v cygpath >/dev/null 2>&1; then MOUNT="$(cygpath -m "$REPO")"; export MSYS_NO_PATHCONV=1; else MOUNT="$REPO"; fi

kicad() {
  docker run --rm -v "$MOUNT:/work" -w /work -e HOME=/tmp "$IMAGE" sh -c     "mkdir -p /tmp/.config/kicad/10.0 && cp /usr/share/kicad/template/sym-lib-table /usr/share/kicad/template/fp-lib-table /tmp/.config/kicad/10.0/ && python3 electronics/tools/build_board.py $*"
}

if [ "$ROUTE" = 1 ]; then
  if [ ! -f "$FR_JAR" ]; then
    mkdir -p "$(dirname "$FR_JAR")"
    curl -sSL -o "$FR_JAR" "https://github.com/freerouting/freerouting/releases/download/v$FR_VER/freerouting-$FR_VER.jar"
  fi
  kicad "$BOARD" --dsn
  PASSES="${PASSES:-60}"
  docker run --rm -v "$MOUNT:/work" -w "/work/electronics/$BOARD/build" "$JRE" sh -c     "java -jar /work/.cache/freerouting/freerouting-$FR_VER.jar --gui.enabled=false -de $BOARD.dsn -do $BOARD.ses --router.autorouter.max_passes=$PASSES > freerouting.log 2>&1; grep -E 'Auto-routing stage completed|unrouted connections' freerouting.log | tail -8"
  kicad "$BOARD" --ses $FAB
elif [ "$SES" = 1 ]; then
  kicad "$BOARD" --ses $FAB
elif [ "$CHECK" = 1 ] || [ -n "$FAB" ]; then
  kicad "$BOARD" --check $FAB
else
  kicad "$BOARD"
fi
