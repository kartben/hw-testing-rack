/*
 * A capture as the viewer and the decoders read it: each channel's level
 * changes, times from the trigger.  Built from what Analyzer.capture()
 * resolves to (protocol.mjs).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { bytesPerSample } from "./protocol.mjs";

export const RATES = [1e6, 2e6, 5e6, 10e6, 20e6, 25e6, 50e6, 100e6];
/* The fewest samples a capture takes: a shorter one says nothing */
const MIN_SAMPLES = 1000;

export class Capture {
  /* channels: the analyzer's channel numbers, 0-based; samples: words, bit i = channels[i] */
  constructor({ channels, rate, pre, post, samples, stamps = new Uint32Array(0) }) {
    Object.assign(this, { channels, rate, pre, post, samples, stamps });
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
