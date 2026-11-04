/*
 * A capture as the viewer and the decoders read it: each channel's level
 * changes, times from the trigger.  Built from what Analyzer.capture()
 * resolves to (protocol.mjs), or from a capture file.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { DECODERS } from "./decoders.mjs";
import { bytesPerSample } from "./protocol.mjs";

export const RATES = [1e6, 2e6, 5e6, 10e6, 20e6, 25e6, 50e6, 100e6];
/* The fewest samples a capture takes: a shorter one says nothing */
const MIN_SAMPLES = 1000;

export class Capture {
  /*
   * channels: the analyzer's channel numbers, 0-based; samples: words, bit i = channels[i];
   * names: what a file calls its channels, in that order
   */
  constructor({ channels, rate, pre, post, samples, stamps = new Uint32Array(0), names = null }) {
    Object.assign(this, { channels, rate, pre, post, samples, stamps, names });
    this.cache = new Map();
  }

  get count() {
    return this.samples.length;
  }

  /* Seconds from the trigger to sample i */
  time(i) {
    return (i - this.pre) / this.rate;
  }

  /* The sample at t seconds from the trigger */
  index(t) {
    return Math.round(t * this.rate) + this.pre;
  }

  level(k, i) {
    return (this.samples[i] >>> k) & 1;
  }

  /*
   * The k-th channel captured (channels[k]) as level changes: an Int32Array
   * of sample indexes, the first 0 (the start), each a change; the level at
   * the start is firstLevel(k).
   */
  edges(k) {
    if (!this.cache.has(k)) {
      const s = this.samples, out = [0];
      let lv = s.length ? (s[0] >>> k) & 1 : 0;
      for (let i = 1; i < s.length; i++) {
        const v = (s[i] >>> k) & 1;
        if (v !== lv) {
          out.push(i);
          lv = v;
        }
      }
      this.cache.set(k, Int32Array.from(out));
    }
    return this.cache.get(k);
  }

  firstLevel(k) {
    return this.samples.length ? this.level(k, 0) : 0;
  }
}

/*
 * A capture file: JSON, what a test or a script can read too.  samples is
 * base64 of the words, little-endian, bytesPerSample each, bit i = channels[i];
 * time 0 is sample pre, the trigger; names and decoders are as they were saved.
 */
const FILE_FORMAT = "hwtr-analyzer-capture";

function toBase64(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(s);
}

function fromBase64(text) {
  const s = atob(text), out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) {
    out[i] = s.charCodeAt(i);
  }
  return out;
}

/* names: one per captured channel; extra: source, saved... */
export function toFile(cap, names, decoders, extra = {}) {
  const s = cap.samples;
  return JSON.stringify({
    format: FILE_FORMAT, version: 1, ...extra,
    channels: cap.channels, names, rate: cap.rate, pre: cap.pre, post: cap.post, decoders,
    stamps: [...cap.stamps], bytesPerSample: s.BYTES_PER_ELEMENT,
    samples: toBase64(new Uint8Array(s.buffer, s.byteOffset, s.byteLength)),
  });
}

/* The decoders a file may bring: known types, numbers where numbers go, nothing else */
function fileDecoders(list) {
  const num = (v) => (Number.isFinite(v) ? v : undefined);
  return (Array.isArray(list) ? list : []).filter((d) => Object.hasOwn(DECODERS, d?.type)).map((d) => {
    const lines = {};
    for (const line of DECODERS[d.type].lines) {
      const role = line.replace("?", "");
      lines[role] = Number.isInteger(d.lines?.[role]) ? d.lines[role] : null;
    }
    const out = { type: d.type, lines };
    if (num(d.baud) > 0) {
      out.baud = d.baud;
    }
    if ([0, 1, 2, 3].includes(d.mode)) {
      out.mode = d.mode;
    }
    return out;
  });
}

/* {cap, decoders, ...the file's own fields}; throws what is wrong with it */
export function fromFile(text) {
  let f;
  try {
    f = JSON.parse(text);
  } catch {
    throw new Error("not a capture file: it is not JSON");
  }
  if (f?.format !== FILE_FORMAT) {
    throw new Error("not a capture file");
  }
  if (f.version !== 1) {
    throw new Error(`capture file version ${f.version}: this page reads version 1`);
  }
  const Word = { 1: Uint8Array, 2: Uint16Array, 4: Uint32Array }[f.bytesPerSample];
  const count = f.pre + f.post;
  if (!Word || !(f.rate > 0) || !Number.isInteger(count) || f.pre < 0 || f.post < 0 || typeof f.samples !== "string" ||
      !Array.isArray(f.channels) || !f.channels.every((c) => Number.isInteger(c) && c >= 0) ||
      f.channels.length > f.bytesPerSample * 8) {
    throw new Error("damaged capture file");
  }
  let bytes;
  try {
    bytes = fromBase64(f.samples);
  } catch {
    throw new Error("damaged capture file: its samples");
  }
  if (bytes.length !== count * f.bytesPerSample) {
    throw new Error(`damaged capture file: ${bytes.length} bytes of samples, ${count * f.bytesPerSample} expected`);
  }
  const names = f.channels.map((c, k) => String(f.names?.[k] ?? `CH${c + 1}`));
  return {
    ...f,
    decoders: fileDecoders(f.decoders),
    cap: new Capture({ channels: f.channels, rate: f.rate, pre: f.pre, post: f.post, names,
                       samples: new Word(bytes.buffer), stamps: Uint32Array.from(Array.isArray(f.stamps) ? f.stamps : []) }),
  };
}

/*
 * What a capture of this many seconds (0: as long as it can) takes with these
 * channels at this rate (info: Analyzer.identify()): the samples and the
 * seconds it gets, what the buffer holds, whether the seconds asked fit.
 */
export function timing(info, channels, rate, asked = 0) {
  const bps = bytesPerSample(channels.length ? channels : [0]);
  const most = Math.floor(info.buffer / bps);
  const samples = asked ? Math.min(most, Math.max(MIN_SAMPLES, Math.round(asked * rate))) : most;
  return { samples, seconds: samples / rate, held: most / rate, bits: bps * 8, fits: !asked || asked * rate <= most };
}

/* The fastest rate at which the buffer holds this many seconds, or null */
export function fastestFor(info, channels, seconds) {
  return RATES.filter((r) => r <= info.maxRate && timing(info, channels, r).held >= seconds).at(-1) ?? null;
}

/* The slowest rate of at least this many samples per second, or null */
export function slowestOver(info, need) {
  return RATES.find((r) => r <= info.maxRate && r >= need) ?? null;
}
