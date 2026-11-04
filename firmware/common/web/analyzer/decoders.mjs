/*
 * Protocol decoders on a capture (capture.mjs), in the browser: UART, I²C,
 * SPI, WS2812B, PWM, 1-Wire, CAN, SWD.  Each takes the capture and the lanes it reads (k: the
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

const hz = (f) => (f >= 1e6 ? `${(f / 1e6).toFixed(3)} MHz` : f >= 1e3 ? `${(f / 1e3).toFixed(3)} kHz` : `${f.toFixed(2)} Hz`);

/*
 * PWM or a clock: from each rising edge to the next, the frequency and the
 * share of the period spent high.  Periods alike to a sample make one box, so
 * a steady signal is one box and a change shows.  stats: over the whole lane,
 * what a test asserts.
 */
export function pwm(cap, { k, label = "PWM" }) {
  const e = cap.edges(k), first = cap.firstLevel(k), items = [];
  const periods = [];
  for (let m = 1; m + 2 < e.length; m++) {
    /* e[m] is a change: the level after it is the first one's, flipped m times */
    if ((first ^ (m & 1)) === 1) {
      periods.push({ at: e[m], high: e[m + 1] - e[m], period: e[m + 2] - e[m] });
    }
  }
  let run = null;
  const flush = () => {
    if (run) {
      const period = run.periods / run.count, high = run.highs / run.count, f = cap.rate / period, duty = 100 * high / period;
      items.push({ t0: cap.time(run.from), t1: cap.time(run.to), kind: "data", text: `${hz(f)} · ${duty.toFixed(1)} %`,
                   freq: f, duty, count: run.count,
                   detail: `${run.count} period${run.count === 1 ? "" : "s"}, ${(1e6 * period / cap.rate).toPrecision(5)} µs each` });
    }
    run = null;
  };
  for (const p of periods) {
    if (run && (Math.abs(p.period - run.period) > 1 || Math.abs(p.high - run.high) > 1)) {
      flush();
    }
    run ??= { from: p.at, to: p.at, period: p.period, high: p.high, count: 0, periods: 0, highs: 0 };
    run.to = p.at + p.period;
    run.count++;
    run.periods += p.period;
    run.highs += p.high;
  }
  flush();
  const stats = periods.length ? (() => {
    const freqs = periods.map((p) => cap.rate / p.period), duties = periods.map((p) => 100 * p.high / p.period);
    const sum = (a) => a.reduce((x, y) => x + y, 0), span = (a) => ({ min: Math.min(...a), max: Math.max(...a) });
    return { periods: periods.length, freq: { ...span(freqs), mean: cap.rate * periods.length / sum(periods.map((p) => p.period)) },
             duty: { ...span(duties), mean: 100 * sum(periods.map((p) => p.high)) / sum(periods.map((p) => p.period)) } };
  })() : { periods: 0 };
  return [{ label, items, stats }];
}

const W1_ROM_COMMANDS = { 0x33: "READ ROM", 0x55: "MATCH ROM", 0xcc: "SKIP ROM", 0xf0: "SEARCH ROM", 0xec: "ALARM SEARCH",
                          0x3c: "OVERDRIVE SKIP", 0x69: "OVERDRIVE MATCH" };

/* 1-Wire's CRC-8 (x^8 + x^5 + x^4 + 1, LSB first): a ROM code with its CRC comes to 0 */
function w1Crc(bytes) {
  let crc = 0;
  for (const b of bytes) {
    crc ^= b;
    for (let i = 0; i < 8; i++) {
      crc = crc & 1 ? (crc >> 1) ^ 0x8c : crc >> 1;
    }
  }
  return crc;
}

/*
 * 1-Wire at standard speed, on the one line; overdrive is not read.  Low for
 * 480 µs or more (from 360 here) is a reset, then a device answers with a low
 * of 60 to 240 µs, 15 to 60 µs after the release.  Otherwise each fall starts a
 * bit slot, read 15 µs on, whoever drives it; bytes LSB first.  After a reset
 * the first byte is a ROM command: READ and MATCH are followed by the 8 bytes
 * of a ROM code, SEARCH by bits that make no bytes.  frames: from a reset to the next.
 */
export function onewire(cap, { k, label = "1-Wire" }) {
  const e = cap.edges(k), first = cap.firstLevel(k), us = (n) => n * cap.rate / 1e6, items = [], frames = [];
  if (us(15) < 2) {
    throw new Error(`1-Wire needs ${(2 / 15).toFixed(2)} MS/s at least`);
  }
  let frame = null, bits = [], from = 0, end = 0, phase = "data", rom = [], romFrom = 0, searchFrom = 0, searchBits = 0;
  const push = (it) => {
    items.push(it);
    frame?.items.push(it);
  };
  const box = (a, b, text, kind, more = {}) => push({ t0: cap.time(a), t1: cap.time(b), text, kind, ...more });
  const flushBits = () => {
    if (bits.length) {
      box(from, end, `${bits.length} bit${bits.length === 1 ? "" : "s"}`, "err");
    }
    bits = [];
    if (phase === "search" && searchBits) {
      box(searchFrom, end, `${searchBits} search bits`, "ctl");
    }
    searchBits = 0;
    if (phase === "rom" && rom.length) {
      box(romFrom, end, `ROM cut after ${rom.length} bytes`, "err");
    }
    rom = [];
  };
  const close = () => {
    flushBits();
    if (frame) {
      const f = frame, shown = f.items.filter((x) => x.text !== "reset" && x.text !== "presence");
      const values = f.items.filter((x) => x.value !== undefined);
      frames.push({ t0: f.items[0].t0, t1: f.items.at(-1).t1, text: shown.map((x) => x.text).join(" ") || "reset",
                    kind: f.items.some((x) => x.kind === "err") ? "err" : "data",
                    hex: values.map((x) => hex(x.value, 2)).join(" "), items: f.items,
                    fields: { presence: f.presence, command: f.command, rom: f.rom, bytes: f.bytes } });
    }
    frame = null;
  };
  const byte = (v) => {
    if (phase === "command") {
      const name = W1_ROM_COMMANDS[v];
      box(from, end, name ? `0x${hex(v)} ${name}` : `0x${hex(v)}`, "addr", { value: v });
      if (frame) {
        frame.command = name ?? null;
      }
      phase = v === 0x33 || v === 0x55 ? "rom" : v === 0xf0 || v === 0xec ? "search" : "data";
      rom = [];
      romFrom = end;
      searchFrom = end;
    } else if (phase === "rom") {
      if (!rom.length) {
        romFrom = from;
      }
      rom.push(v);
      if (rom.length === 8) {
        const good = w1Crc(rom) === 0;
        const code = [...rom].reverse().map((x) => hex(x)).join("");
        box(romFrom, end, `ROM ${code}${good ? "" : " CRC bad"}`, good ? "addr" : "err");
        if (frame) {
          frame.rom = code;
          frame.bytes.push(...rom);
        }
        rom = [];
        phase = "data";
      }
    } else {
      box(from, end, `0x${hex(v)}`, "data", { value: v });
      frame?.bytes.push(v);
    }
  };
  for (let m = 1; m < e.length; m++) {
    /* The level after e[m] is the first one's, flipped m times: a fall starts everything */
    if ((first ^ (m & 1)) !== 0) {
      continue;
    }
    const i = e[m], release = m + 1 < e.length ? e[m + 1] : cap.count, low = release - i;
    if (low >= us(360)) {
      close();
      frame = { items: [], presence: false, command: null, rom: null, bytes: [] };
      box(i, release, "reset", "ctl");
      const next = m + 2 < e.length ? e[m + 2] : Infinity, back = m + 3 < e.length ? e[m + 3] : cap.count;
      const width = back - next;
      if (next - release <= us(120) && width >= us(30) && width <= us(480)) {
        box(next, back, "presence", "ctl");
        frame.presence = true;
        m += 2;
      } else {
        box(release, Math.min(cap.count - 1, release + us(240)), "no presence", "err");
      }
      phase = "command";
      continue;
    }
    if (low > us(120)) {
      box(i, release, `low ${(low * 1e6 / cap.rate).toFixed(0)} µs`, "err");
      continue;
    }
    const bit = cap.level(k, Math.min(cap.count - 1, Math.round(i + us(15))));
    end = Math.min(cap.count - 1, Math.round(i + us(60)));
    if (phase === "search") {
      searchBits++;
      continue;
    }
    if (!bits.length) {
      from = i;
    }
    bits.push(bit);
    if (bits.length === 8) {
      const v = bits.reduceRight((a, b) => (a << 1) | b, 0);
      bits = [];
      byte(v);
    }
  }
  close();
  return [{ label, items, frames }];
}

const CAN_SAMPLE_POINT = 0.7;   /* of a bit, from its start */
const CAN_IDLE_BITS = 7;        /* recessive this long: the bus is free again, whatever came before */

class CanStop extends Error {}

/*
 * Classic CAN on a controller's TX or RX line, dominant low: base and extended
 * frames, data and remote, bit stuffing, the CRC, the ACK slot.  A frame's
 * start synchronizes hard, each recessive to dominant edge again.  An FD frame
 * is named and skipped.  After an error it waits for the bus to go idle.
 * A sender's own TX pin shows no ACK: nobody else drives that wire.
 */
export function can(cap, { k, baud = 500000, label }) {
  const P = cap.rate / baud;
  if (P < 4) {
    throw new Error(`CAN at ${baud / 1e3} kbit/s needs ${(4 * baud / 1e6).toFixed(1)} MS/s at least`);
  }
  const e = cap.edges(k), first = cap.firstLevel(k), items = [], frames = [];
  /* The level after e[m] is the first one's, flipped m times */
  const falling = (m) => (first ^ (m & 1)) === 0;
  let m = 1, after = 0;

  const skipToIdle = (from) => {
    for (let n = 1; n < e.length; n++) {
      const start = e[n], end = n + 1 < e.length ? e[n + 1] : cap.count;
      if (!falling(n) && end > from && end - Math.max(start, from) >= CAN_IDLE_BITS * P) {
        return Math.max(start, from) + CAN_IDLE_BITS * P;
      }
    }
    return cap.count;
  };

  while (m < e.length) {
    if (e[m] < after || !falling(m)) {
      m++;
      continue;
    }
    /* A frame from this start of frame */
    const sof = e[m], boxes = [];
    let pos = sof, scan = m, run = 0, last = -1, crcBits = [], fields = null, bad = null, end = sof;
    const raw = () => {
      /* An edge to dominant near where this bit starts is where it starts */
      while (scan < e.length && e[scan] < pos - P / 2) {
        scan++;
      }
      for (let n = scan; n < e.length && e[n] <= pos + P / 2; n++) {
        if (falling(n)) {
          pos = e[n];
          break;
        }
      }
      const at = pos + CAN_SAMPLE_POINT * P;
      if (at >= cap.count) {
        throw new CanStop("cut off");
      }
      const v = cap.level(k, Math.round(at));
      pos += P;
      return v;
    };
    /* A bit of the stuffed part: after five alike, a sixth of the opposite level that is not data */
    const bit = () => {
      if (run === 5) {
        const stuff = raw();
        if (stuff === last) {
          throw new CanStop("stuff error");
        }
        last = stuff;
        run = 1;
      }
      const v = raw();
      run = v === last ? run + 1 : 1;
      last = v;
      crcBits.push(v);
      return v;
    };
    const read = (n) => {
      let v = 0;
      for (let i = 0; i < n; i++) {
        v = v * 2 + bit();
      }
      return v;
    };
    const box = (a, b, text, kind, more = {}) => boxes.push({ t0: cap.time(a), t1: cap.time(b), text, kind, ...more });
    try {
      bit();                      /* start of frame */
      let id = read(11);
      const b12 = bit(), ide = bit();
      let rtr = b12, fd = false;
      if (ide) {
        id = id * 2 ** 18 + read(18);
        rtr = bit();
        fd = bit() === 1;
        bit();
      } else {
        fd = bit() === 1;
      }
      if (fd) {
        throw new CanStop("CAN FD frame: not read");
      }
      const dlc = read(4), n = rtr ? 0 : Math.min(dlc, 8);
      const idText = `0x${hex(id, ide ? 8 : 3)}${rtr ? " RTR" : ""} [${dlc}]`;
      box(sof, pos, idText, "addr", { value: id });
      const data = [];
      for (let i = 0; i < n; i++) {
        const from = pos, v = read(8);
        data.push(v);
        box(from, pos, `0x${hex(v)}`, "data", { value: v });
      }
      let crc = 0;
      for (const b of crcBits) {
        const top = b ^ ((crc >> 14) & 1);
        crc = (crc << 1) & 0x7fff;
        if (top) {
          crc ^= 0x4599;
        }
      }
      const from = pos, got = read(15);
      /* The stuffing stops with the CRC; a stuff bit after its last five alike still comes */
      if (run === 5) {
        raw();
      }
      const crcOk = got === crc;
      box(from, pos, crcOk ? "CRC" : `CRC 0x${hex(got, 4)}, 0x${hex(crc, 4)} expected`, crcOk ? "ctl" : "err");
      const delimiter = raw(), ackStart = pos, ack = raw() === 0;
      const ackEnd = pos;
      raw();
      box(ackStart, ackEnd, ack ? "ACK" : "no ACK", "ctl");
      if (!delimiter) {
        box(ackStart - P, ackStart, "CRC delimiter low", "err");
      }
      fields = { id, extended: !!ide, rtr: !!rtr, dlc, data, crcOk, ack };
      end = pos + 7 * P;
    } catch (err) {
      if (!(err instanceof CanStop)) {
        throw err;
      }
      bad = err.message;
    }
    if (bad) {
      /* From where the last box ended: what was read stays readable */
      box(boxes.length ? cap.index(boxes.at(-1).t1) : sof, Math.min(pos, cap.count - 1), bad, "err");
      end = bad === "cut off" ? cap.count : skipToIdle(pos);
    }
    items.push(...boxes);
    frames.push({
      t0: boxes[0].t0, t1: boxes.at(-1).t1,
      text: boxes.filter((x) => x.text !== "CRC" && x.kind !== "ctl").map((x) => x.text).join(" ") +
            (fields && !fields.ack ? " (no ACK)" : ""),
      kind: boxes.some((x) => x.kind === "err") ? "err" : "data",
      hex: fields ? fields.data.map((v) => hex(v)).join(" ") : "", items: boxes, fields: fields ?? { error: bad },
    });
    after = end;
    m++;
  }
  return [{ label: label ?? `CAN ${baud / 1e3} kbit/s`, items, frames }];
}

const SWD_READ = { 0: "IDCODE", 4: "CTRL/STAT", 8: "RESEND", 12: "RDBUFF" };
const SWD_WRITE = { 0: "ABORT", 4: "CTRL/STAT", 8: "SELECT", 12: "TARGETSEL" };
const SWD_ACK = { 1: "OK", 2: "WAIT", 4: "FAULT" };
const SWD_RESET_BITS = 50;      /* SWDIO high this many clocks at least: a line reset */
const JTAG_TO_SWD = 0xe79e;

/*
 * SWD: a bit per rising edge of SWCLK, SWDIO read just before it, since the
 * host changes it while the clock is low and the target after the edge.  A
 * request is start, APnDP, RnW, A[2:3], parity, stop, park, found by its stop,
 * park and parity; then a turnaround and a 3-bit ACK; on OK 32 bits of data
 * and their parity, with a turnaround before a write's or after a read's.
 * A write to DP 0xC, TARGETSEL, gets no ACK from anyone and goes straight on.
 * Bits are LSB first.
 */
export function swd(cap, { swclk, swdio, label = "SWD" }) {
  const e = cap.edges(swclk), first = cap.firstLevel(swclk), at = [], bits = [], items = [], frames = [];
  for (let m = 1; m < e.length; m++) {
    /* The level after e[m] is the first one's, flipped m times */
    if ((first ^ (m & 1)) === 1) {
      at.push(e[m]);
      bits.push(cap.level(swdio, Math.max(0, e[m] - 1)));
    }
  }
  const box = (a, b, text, kind, more = {}) => {
    const it = { t0: cap.time(at[a]), t1: cap.time(at[Math.min(b, at.length - 1)]), text, kind, ...more };
    items.push(it);
    return it;
  };
  const word = (from, n) => {
    let v = 0;
    for (let i = n - 1; i >= 0; i--) {
      v = v * 2 + bits[from + i];
    }
    return v;
  };
  const n = bits.length;
  let i = 0;
  while (i < n) {
    if (!bits[i]) {
      i++;
      continue;
    }
    let run = 1;
    while (i + run < n && bits[i + run]) {
      run++;
    }
    if (run >= SWD_RESET_BITS) {
      const it = box(i, i + run, "line reset", "ctl");
      frames.push({ ...it, items: [it], hex: "", fields: { event: "line reset" } });
      i += run;
      if (i + 16 <= n && word(i, 16) === JTAG_TO_SWD) {
        const sel = box(i, i + 16, "JTAG to SWD", "ctl");
        frames.push({ ...sel, items: [sel], hex: "", fields: { event: "JTAG to SWD" } });
        i += 16;
      }
      continue;
    }
    if (i + 13 > n) {
      break;
    }
    const [, apndp, rnw, a2, a3, parity, stop, park] = bits.slice(i, i + 8);
    if (stop !== 0 || park !== 1 || ((apndp ^ rnw ^ a2 ^ a3) !== parity)) {
      i++;
      continue;
    }
    const addr = (a3 << 3) | (a2 << 2), blind = !apndp && !rnw && addr === 12;
    const name = apndp ? `AP 0x${hex(addr, 1)}` : `DP ${(rnw ? SWD_READ : SWD_WRITE)[addr]}`;
    const parts = [box(i, i + 8, `${rnw ? "R" : "W"} ${name}`, "addr", { value: addr })];
    const code = word(i + 9, 3), ack = blind ? "none" : SWD_ACK[code] ?? "no ACK";
    if (!blind) {
      parts.push(box(i + 9, i + 12, ack, ack === "OK" || ack === "WAIT" ? "ctl" : "err"));
    }
    let next = i + 13, data = null, parityOk = null;
    if (ack === "OK" || blind) {
      const from = rnw ? i + 12 : i + 13;
      if (from + 33 > n) {
        parts.push(box(from, n - 1, "cut off", "err"));
        next = n;
      } else {
        data = word(from, 32);
        parityOk = bits.slice(from, from + 32).reduce((a, b) => a ^ b, 0) === bits[from + 32];
        parts.push(box(from, from + 33, `0x${hex(data, 8)}${parityOk ? "" : " parity"}`, parityOk ? "data" : "err", { value: data }));
        next = from + 33 + (rnw ? 1 : 0);
      }
    }
    frames.push({
      t0: parts[0].t0, t1: parts.at(-1).t1, text: parts.map((x) => x.text).join(" "),
      kind: parts.some((x) => x.kind === "err") ? "err" : "data", hex: data === null ? "" : hex(data, 8), items: parts,
      fields: { ap: !!apndp, read: !!rnw, addr, ack, data, parityOk },
    });
    i = next;
  }
  return [{ label, items, frames }];
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
  pwm: { name: "PWM / clock", lines: ["in"], run: (cap, d, k) => pwm(cap, { k: k.in }) },
  onewire: { name: "1-Wire", lines: ["dq"], run: (cap, d, k) => onewire(cap, { k: k.dq }) },
  can: { name: "CAN", lines: ["rx"], run: (cap, d, k) => can(cap, { k: k.rx, baud: d.baud ?? 500000 }) },
  swd: { name: "SWD", lines: ["swclk", "swdio"], run: (cap, d, k) => swd(cap, k) },
};

export const BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1e6, 2e6, 3e6];
export const CAN_RATES = [125000, 250000, 500000, 1000000];
