// One frame of the viewer's LVGL screen (site/assets/lvgl/lvgl-demo.wasm, built by tools/lvgl_wasm/build.sh)
// as a PNG, for the offline renders (tools/assembly_glb.py puts it on the board's display).  The same wasm
// the viewer runs: LVGL's own demo, its software renderer, an XRGB8888 frame buffer.
//
//   node tools/lvgl_frame.mjs [music|widgets] [w] [h] [ms] [out.png]
//   node tools/lvgl_frame.mjs music 480 800 6000 render/assets/lvgl/music-480x800.png
//
// ms: how long LVGL runs before the frame is taken, in 33 ms ticks (the music demo's intro takes ~3 s).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crc32, deflateSync } from 'node:zlib';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const [demo = 'music', w = '480', h = '800', ms = '6000', out = `render/assets/lvgl/${demo}-${w}x${h}.png`] =
  process.argv.slice(2);
const W = +w, H = +h;

const wasm = readFileSync(join(REPO, 'site', 'assets', 'lvgl', 'lvgl-demo.wasm'));
const { instance } = await WebAssembly.instantiate(wasm, {});
const ex = instance.exports;
const ptr = ex.screen_init(W, H, demo === 'music' ? 0 : 1);
if (!ptr) throw new Error(`LVGL screen ${W}x${H} too large`);
for (let t = 0; t < +ms; t += 33) ex.screen_tick(33);

// XRGB8888 → RGB rows, each behind PNG's filter byte 0
const src = new Uint32Array(ex.memory.buffer, ptr, W * H);
const raw = Buffer.alloc((W * 3 + 1) * H);
for (let y = 0; y < H; y++) {
  const row = y * (W * 3 + 1);
  for (let x = 0; x < W; x++) {
    const v = src[y * W + x], o = row + 1 + x * 3;
    raw[o] = (v >>> 16) & 0xff; raw[o + 1] = (v >>> 8) & 0xff; raw[o + 2] = v & 0xff;
  }
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
  return Buffer.concat([len, td, crc]);
}
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 8; ihdr[9] = 2;   // 8-bit RGB
const png = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
const dst = join(REPO, out);
mkdirSync(dirname(dst), { recursive: true });
writeFileSync(dst, png);
console.log(`wrote ${out} (${demo}, ${W}x${H}, after ${ms} ms)`);
