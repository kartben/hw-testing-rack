# Headless Blender (Cycles, CPU) for the photoreal renders.
#   docker build -t hw-testing-rack/blender render/
#   tools/render.sh
FROM ubuntu:24.04
ARG BLENDER=4.5.14
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
      libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxext6 libxkbcommon0 libsm6 libice6 \
      libgl1 libegl1 libglib2.0-0 libwayland-client0 libwayland-cursor0 libwayland-egl1 libdbus-1-3 \
 && curl -sSL "https://download.blender.org/release/Blender4.5/blender-${BLENDER}-linux-x64.tar.xz" | tar -xJ -C /opt \
 && ln -s "/opt/blender-${BLENDER}-linux-x64/blender" /usr/local/bin/blender \
 && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["blender"]
