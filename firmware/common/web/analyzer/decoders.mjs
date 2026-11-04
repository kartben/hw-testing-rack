/*
 * Protocol decoders on a capture (capture.mjs), in the browser: UART, I²C,
 * SPI, WS2812B.  Each takes the capture and the lanes it reads (k: the
 * index in cap.channels) and returns rows of boxes for the viewer:
 * {label, items: [{t0, t1, text, kind}]}, times in seconds from the
 * trigger, kind data, addr, ctl or err.  A row may also say how its boxes make
 * up messages, one row each in the decoded table: frames: [{t0, t1, text, kind,
 * hex, items, fields}], fields what a script reads of it.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

const hex = (v, digits = 2) => v.toString(16).toUpperCase().padStart(digits, "0");

/* A byte as text: the character if it prints, \r \n \t, else its hex */
function shown(v) {
  return v === 0x0d ? "\\r" : v === 0x0a ? "\\n" : v === 0x09 ? "\\t"
       : v >= 0x20 && v < 0x7f ? String.fromCharCode(v) : `0x${hex(v)}`;
}

/* The sample indexes where any of these lanes changes, in order */
function changes(cap, ks) {
  const all = new Set();
  for (const k of ks) {
    for (const i of cap.edges(k).subarray(1)) {
      all.add(i);
    }
  }
  return Int32Array.from(all).sort();
}

/* What ends a UART's message: a newline, or a pause of this many bytes' time */
const PAUSE_BYTES = 10;

/* A UART's bytes as messages: a line of text, or what came in one go */
function uartMessages(items) {
  const frames = [];
  let group = [];
  const flush = () => {
    if (group.length) {
      frames.push({
        t0: group[0].t0, t1: group.at(-1).t1, text: group.map((x) => x.text).join(""),
        kind: group.some((x) => x.kind === "err") ? "err" : "data",
        hex: group.map((x) => hex(x.value)).join(" "), items: group, fields: { bytes: group.map((x) => x.value) },
      });
      group = [];
    }
  };
  for (const it of items) {
    if (group.length && it.t0 - group.at(-1).t1 > PAUSE_BYTES * (it.t1 - it.t0)) {
      flush();
    }
    group.push(it);
    if (it.value === 0x0a) {
      flush();
    }
  }
  flush();
  return frames;
}

/*
 * UART, 8N1 by default: idle high (invert: idle low), a start bit, LSB
 * first.  An odd parity or a stop bit not high marks the byte.
 */
export function uart(cap, { k, baud, bits = 8, parity = "none", stop = 1, invert = false, label }) {
  const P = cap.rate / baud;
  if (P < 4) {
    throw new Error(`${baud} Bd needs ${(4 * baud / 1e6).toFixed(1)} MS/s at least`);
  }
  const at = (i) => cap.level(k, Math.min(cap.count - 1, Math.round(i))) ^ (invert ? 1 : 0);
  const e = cap.edges(k), items = [];
  let after = 0;
  for (let m = 1; m < e.length; m++) {
    const s = e[m];
    if (s < after || at(s) !== 0 || at(s + P / 2) !== 0) {
      continue;
    }
    const frame = 1 + bits + (parity === "none" ? 0 : 1);
    if (s + P * (frame + stop) > cap.count) {
      break;
    }
    let v = 0, ones = 0;
    for (let b = 0; b < bits; b++) {
      const lv = at(s + P * (1.5 + b));
      v |= lv << b;
      ones += lv;
    }
    let err = null;
    if (parity !== "none" && ((ones + at(s + P * (bits + 1.5))) % 2 === 0) !== (parity === "even")) {
      err = "parity";
    }
    if (at(s + P * (frame + 0.5)) !== 1) {
      err ??= "framing";
    }
    items.push({ t0: cap.time(s), t1: cap.time(s + P * (frame + stop)), value: v,
                 text: err ? `${shown(v)} ${err}` : shown(v), kind: err ? "err" : "data" });
    after = s + P * (frame + 0.5);
  }
  return [{ label: label ?? `UART ${baud >= 1e6 ? `${baud / 1e6} M` : `${baud} `}Bd`, items, frames: uartMessages(items) }];
}

/* I²C: START, the address with R/W, data bytes, ACK or NACK after each, STOP */
export function i2c(cap, { sda, scl, label = "I²C" }) {
  const items = [];
  let pSda = cap.firstLevel(sda), pScl = cap.firstLevel(scl);
  let bits = [], first = 0, inFrame = false, isAddr = false, pending = null;
  for (const i of changes(cap, [sda, scl])) {
    const d = cap.level(sda, i), c = cap.level(scl, i);
    if (pScl && c && d !== pSda) {
      /* SDA while SCL is high: START (again, if it was running) or STOP */
      items.push({ t0: cap.time(i), t1: cap.time(i), text: d ? "P" : inFrame ? "Sr" : "S", kind: "ctl" });
      inFrame = !d;
      isAddr = !d;
      bits = [];
      pending = null;
    } else if (!pScl && c && inFrame) {
      if (!bits.length) {
        first = i;
      }
      bits.push(d);
      if (bits.length === 9) {
        const b = bits.slice(0, 8).reduce((v, x) => (v << 1) | x, 0), ack = bits[8] ? "NACK" : "ACK";
        pending = isAddr ? { text: `${b & 1 ? "R" : "W"} 0x${hex(b >> 1)} ${ack}`, kind: "addr", value: b >> 1 }
                         : { text: `0x${hex(b)} ${ack}`, kind: "data", value: b };
        pending.t0 = cap.time(first);
        isAddr = false;
        bits = [];
      }
    } else if (pScl && !c && pending) {
      /* The byte's box ends with its ACK clock */
      items.push({ ...pending, t1: cap.time(i) });
      pending = null;
    }
    pSda = d;
    pScl = c;
  }
  /* The STOP and START marks get some width: a bit's */
  const bytes = items.filter((x) => x.kind !== "ctl");
  const w = bytes.length ? Math.min(...bytes.map((x) => x.t1 - x.t0)) / 9 : 0;
  for (const it of items) {
    if (it.kind === "ctl") {
      it.t0 -= w / 2;
      it.t1 += w / 2;
    }
  }
  return [{ label, items }];
}

/*
 * SPI while CS is active (low by default): bits on the clock's sampling
 * edge (mode 0 and 3: rising, 1 and 2: falling), MSB first, 8 a word.  A
 * row for MOSI and one for MISO when it is captured.
 */
export function spi(cap, { cs, sck, mosi, miso, mode = 0, bits = 8, lsbFirst = false, csHigh = false,
                           label = "SPI" }) {
  const rising = mode === 0 || mode === 3;
  const lines = [mosi, miso].filter((x) => x !== undefined && x !== null);
  const rows = lines.map((k) => ({ label: `${label} ${k === mosi ? "MOSI" : "MISO"}`, items: [], k }));
  let words = lines.map(() => 0), n = 0, first = 0, last = 0, pCs = cap.firstLevel(cs), pSck = cap.firstLevel(sck);
  for (const i of changes(cap, [cs, sck])) {
    const sel = cap.level(cs, i) === (csHigh ? 1 : 0), c = cap.level(sck, i);
    if (cap.level(cs, i) !== pCs) {
      n = 0;
      words = lines.map(() => 0);
    } else if (sel && c !== pSck && c === (rising ? 1 : 0)) {
      if (!n) {
        first = i;
      }
      lines.forEach((k, j) => {
        const b = cap.level(k, i);
        words[j] = lsbFirst ? words[j] | (b << n) : (words[j] << 1) | b;
      });
      last = i;
      if (++n === bits) {
        const half = (last - first) / (bits - 1) / 2;
        rows.forEach((r, j) => r.items.push({ t0: cap.time(first - half), t1: cap.time(last + half),
                                              text: `0x${hex(words[j], Math.ceil(bits / 4))}`, kind: "data",
                                              value: words[j] }));
        n = 0;
        words = lines.map(() => 0);
      }
    }
    pCs = cap.level(cs, i);
    pSck = c;
  }
  return rows.map(({ label: l, items }) => ({ label: l, items }));
}

/*
 * WS2812B: 1.25 µs a bit, high 0.4 µs for a 0 and 0.8 µs for a 1 (cut at
 * 0.6 µs); 24 bits a LED, green, red, blue, MSB first; low for more than
 * 50 µs latches them (reset).  A box per LED with its index and values, a
 * box per reset.
 */
export function ws2812(cap, { k, label = "WS2812B" }) {
  const e = cap.edges(k), items = [];
  const ts = (i) => i / cap.rate;
  let bits = [], first = 0, led = 0;
  const flush = (end, partial) => {
    if (bits.length === 24) {
      const v = bits.reduce((a, b) => (a << 1) | b, 0);
      led++;
      items.push({ t0: cap.time(first), t1: cap.time(end), kind: "data", value: v,
                   text: `LED ${led} · G ${hex(v >>> 16)} R ${hex((v >>> 8) & 255)} B ${hex(v & 255)}` });
    } else if (bits.length && partial) {
      items.push({ t0: cap.time(first), t1: cap.time(end), kind: "err", text: `${bits.length} bits` });
    }
    bits = [];
  };
  let lv = cap.firstLevel(k);
  for (let m = 1; m < e.length; m++) {
    lv ^= 1;
    const i = e[m], next = m + 1 < e.length ? e[m + 1] : cap.count;
    if (lv === 1) {
      /* A rising edge: a bit starts, its high time says which */
      if (!bits.length) {
        first = i;
      }
      bits.push(ts(next - i) > 0.6e-6 ? 1 : 0);
    } else if (ts(next - i) > 50e-6) {
      /* Low long enough: the LEDs latch */
      flush(i, true);
      led = 0;
      items.push({ t0: cap.time(i), t1: cap.time(next), text: "reset", kind: "ctl" });
    } else if (bits.length === 24) {
      flush(next, false);
    }
  }
  flush(cap.count - 1, true);
  return [{ label, items }];
}

/*
 * The decoders the page offers: their name, the lines they read (a "?" one
 * may be left out), what they need besides; run() gets the lines as lanes.
 */
export const DECODERS = {
  uart: { name: "UART", lines: ["rx"], run: (cap, d, k) => uart(cap, { k: k.rx, baud: d.baud ?? 115200 }) },
  i2c: { name: "I²C", lines: ["sda", "scl"], run: (cap, d, k) => i2c(cap, k) },
  spi: { name: "SPI", lines: ["cs", "sck", "mosi", "miso?"],
         run: (cap, d, k) => spi(cap, { ...k, mode: d.mode ?? 0 }) },
  ws2812: { name: "WS2812B", lines: ["din"], run: (cap, d, k) => ws2812(cap, { k: k.din }) },
};

export const BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1e6, 2e6, 3e6];
