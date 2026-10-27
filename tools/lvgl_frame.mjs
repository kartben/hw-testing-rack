// One frame of the viewer's LVGL screen (site/assets/lvgl/lvgl-demo.wasm, built by tools/lvgl_wasm/build.sh)
// as a PNG, for the offline renders (tools/assembly_glb.py puts it on the board's display).  The same wasm
// the viewer runs: LVGL's own demo, its software renderer, an XRGB8888 frame buffer.
//
//   node tools/lvgl_frame.mjs [music|widgets] [w] [h] [ms] [out.png]
//   node tools/lvgl_frame.mjs music 480 800 6000 render/assets/lvgl/music-480x800.png
//   node tools/lvgl_frame.mjs widgets 320 240 40000      # A4's Wio Terminal: the slideshow's Shop tab, its bar chart
//   node tools/lvgl_frame.mjs status                     # every bay's front display (rack.json › screens):
//                                                        # render/assets/lvgl/status-<bay>.png
//
// ms: how long LVGL runs before the frame is taken, in 33 ms ticks (the music demo's intro takes ~3 s).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crc32, deflateSync } from 'node:zlib';
import { statusLines, statusScreen } from '../site/bay_screen.js';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const [demo = 'music', w = '480', h = '800', ms = '6000', out = `render/assets/lvgl/${demo}-${w}x${h}.png`] =
  process.argv.slice(2);

const wasm = readFileSync(join(REPO, 'site', 'assets', 'lvgl', 'lvgl-demo.wasm'));
const { instance } = await WebAssembly.instantiate(wasm, {});
const ex = instance.exports;

// XRGB8888 → RGB rows, each behind PNG's filter byte 0
function pngOf(src, W, H) {
  const raw = Buffer.alloc((W * 3 + 1) * H);
  for (let y = 0; y < H; y++) {
    const row = y * (W * 3 + 1);
    for (let x = 0; x < W; x++) {
      const v = src[y * W + x], o = row + 1 + x * 3;
      raw[o] = (v >>> 16) & 0xff; raw[o + 1] = (v >>> 8) & 0xff; raw[o + 2] = v & 0xff;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 8; ihdr[9] = 2;   // 8-bit RGB
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
  return Buffer.concat([len, td, crc]);
}
function save(rel, png) {
  const dst = join(REPO, rel);
  mkdirSync(dirname(dst), { recursive: true });
  writeFileSync(dst, png);
}

if (demo === 'status') {
  const screens = JSON.parse(readFileSync(join(REPO, 'site', 'assets', 'rack.json'), 'utf-8')).screens ?? [];
  if (screens.length) {
    const [W, H] = screens[0].px;
    const draw = statusScreen(ex, W, H);
    for (const s of screens) save(`render/assets/lvgl/status-${s.status.id}.png`, pngOf(draw(statusLines(s.status)), W, H));
  }
  console.log(`wrote ${screens.length} front displays' frames, render/assets/lvgl/status-<bay>.png`);
} else {
  const W = +w, H = +h;
  const ptr = ex.screen_init(W, H, demo === 'music' ? 0 : 1);
  if (!ptr) throw new Error(`LVGL screen ${W}x${H} too large`);
  for (let t = 0; t < +ms; t += 33) ex.screen_tick(33);
  save(out, pngOf(new Uint32Array(ex.memory.buffer, ptr, W * H), W, H));
  console.log(`wrote ${out} (${demo}, ${W}x${H}, after ${ms} ms)`);
}
