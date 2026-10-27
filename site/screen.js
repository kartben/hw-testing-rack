// A live LVGL screen for a board's display: LVGL's own demos (music, widgets), built for wasm32 by
// tools/lvgl_wasm/build.sh and rendered by LVGL's software renderer into a frame buffer, which this copies
// into a texture.  LVGL runs at its own refresh rate (33 ms), whatever the page's frame rate.
import * as THREE from 'three';
import { statusLines, statusScreen } from './bay_screen.js';

export async function startLvgl(url, w, h, demo = 'music') {
  const res = await fetch(url);
  const { instance } = await WebAssembly.instantiate(await res.arrayBuffer(), {});
  const ex = instance.exports;
  const ptr = ex.screen_init(w, h, demo === 'music' ? 0 : 1);
  if (!ptr) throw new Error(`LVGL screen ${w}×${h} too large`);
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(w, h);
  const out = new Uint32Array(img.data.buffer);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  let last = performance.now();
  function step(now) {
    const ms = Math.min(100, Math.round(now - last));
    if (ms < 15) return;
    last = now;
    if (!ex.screen_tick(ms)) return;
    const src = new Uint32Array(ex.memory.buffer, ptr, w * h);    // XRGB8888 → RGBA
    for (let i = 0; i < src.length; i++) {
      const v = src[i];
      out[i] = 0xff000000 | ((v & 0xff) << 16) | (v & 0xff00) | ((v >>> 16) & 0xff);
    }
    ctx.putImageData(img, 0, 0);
    tex.needsUpdate = true;
  }
  return { tex, step, canvas };
}

// The bay nodes' front displays: one LVGL draws every bay's status screen in turn (site/bay_screen.js), each into
// its own texture, once a second as the node does (display.c's REFRESH_MS); the values wander a little, as live
// ones do.  screens: rack.json › screens.
export async function startStatus(url, screens) {
  const res = await fetch(url);
  const { instance } = await WebAssembly.instantiate(await res.arrayBuffer(), {});
  const [w, h] = screens[0].px;
  const draw = statusScreen(instance.exports, w, h);
  const outs = screens.map(() => {
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(w, h);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return { ctx, img, out: new Uint32Array(img.data.buffer), tex };
  });
  function paint() {
    screens.forEach((s, k) => {
      const src = draw(statusLines(s.status, 0.03)), o = outs[k];    // XRGB8888 → RGBA
      for (let i = 0; i < src.length; i++) {
        const v = src[i];
        o.out[i] = 0xff000000 | ((v & 0xff) << 16) | (v & 0xff00) | ((v >>> 16) & 0xff);
      }
      o.ctx.putImageData(o.img, 0, 0);
      o.tex.needsUpdate = true;
    });
  }
  paint();
  let last = performance.now();
  return {
    textures: outs.map((o) => o.tex),
    step(now) {
      if (now - last < 1000) return;
      last = now;
      paint();
    },
  };
}
