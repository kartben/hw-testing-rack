// The bay node's front display (firmware/bay-node/src/display.c) from a bay's status (rack.json › screens ›
// status, tools/webscene.py › front_status): the lines tools/lvgl_wasm/status.c draws, each its colour's letter
// (w white, o orange, g green, G grey, r red) and its text, written as display.c's refresh() writes them.  The
// viewer (site/screen.js) and the renders' frames (tools/lvgl_frame.mjs) both draw them.

// jitter: how much the values wander, as on a live node (0 for a still frame)
export function statusLines(s, jitter = 0) {
  const wander = (v, f) => Math.round(v * (1 + jitter * f * (Math.random() * 2 - 1)));
  const out = ['w' + s.id, s.addr ? 'w' + s.addr : 'ono Wi-Fi'];
  if (s.dut) {
    const mv = wander(s.dut.mv, 0.06);
    out.push(`g${Math.floor(mv / 1000)}.${String(Math.floor((mv % 1000) / 10)).padStart(2, '0')} V  ${wander(s.dut.ma, 1)} mA`);
  } else {
    out.push('GDUT off');
  }
  out.push(s.fault ? 'rFAULT' : 'r');
  for (let i = 0; i < 4; i++) {
    const p = s.ports?.[i];
    if (!s.ports) out.push(`G${i + 1}  -`);
    else if (p.latched) out.push(`r${i + 1}  fault`);
    else if (p.on) out.push(`g${i + 1}  ${wander(p.ma, 1)} mA`);
    else out.push(`G${i + 1}  off`);
  }
  out.push(`wUSB/IP ${s.usbip}   ${s.path}`);
  return out.join('\n');
}

// One LVGL (the wasm's exports) drawing every bay's screen in turn: draw(lines) puts them on the labels,
// redraws the w × h frame buffer and returns it (XRGB8888)
export function statusScreen(ex, w, h) {
  const fb = ex.screen_init(w, h, 2);
  if (!fb) throw new Error(`LVGL screen ${w}×${h} too large`);
  const buf = ex.status_buf();
  const enc = new TextEncoder();
  return (lines) => {
    const bytes = enc.encode(lines).subarray(0, 1023);
    const mem = new Uint8Array(ex.memory.buffer, buf, 1024);
    mem.set(bytes);
    mem[bytes.length] = 0;
    ex.status_apply();
    return new Uint32Array(ex.memory.buffer, fb, w * h);
  };
}
