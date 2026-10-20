#!/usr/bin/env bash
# The order panel of a board assembled two ways (electronics/tools/panelize.py), in the KiCad Docker image plus
# KiKit (built here once: the image tools/kicad.sh uses, with `pip install kikit`).
#
#   tools/panel.sh data-port-x4-v2            # after tools/kicad.sh data-port-x4-v2 --fab (it reads the variants' files)
#   tools/panel.sh data-port-x4-v2 --check    # only the panel's BOM/CPL halves against the variants'
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${KICAD_IMAGE:-kicad/kicad:10.0-full}"
KIKIT=1.8.1
IMAGE="${KIKIT_IMAGE:-hw-testing-rack/kicad-kikit:10.0-$KIKIT}"
BOARD="$1"; shift
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -q -t "$IMAGE" - <<EOF
FROM $BASE
USER root
RUN apt-get update -qq && apt-get install -y -qq python3-pip && python3 -m pip install --quiet --break-system-packages kikit==$KIKIT && rm -rf /var/lib/apt/lists/*
USER kicad
EOF
fi
if command -v cygpath >/dev/null 2>&1; then MOUNT="$(cygpath -m "$REPO")"; export MSYS_NO_PATHCONV=1; else MOUNT="$REPO"; fi
docker run --rm -v "$MOUNT:/work" -w /work -e HOME=/tmp "$IMAGE" sh -c \
  "mkdir -p /tmp/.config/kicad/10.0 && cp /usr/share/kicad/template/sym-lib-table /usr/share/kicad/template/fp-lib-table /tmp/.config/kicad/10.0/ && python3 electronics/tools/panelize.py $BOARD $*"
