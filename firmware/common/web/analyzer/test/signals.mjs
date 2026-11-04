/*
 * Captures made up for the decoders' tests: lanes given as level changes.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture } from "../capture.mjs";

/*
 * lanes: one per channel, [first level, [[seconds, level], ...]]; the capture
 * has rate samples a second, seconds long, and its time 0 is its first sample.
 */
export function captureOf(rate, seconds, lanes) {
  const n = Math.round(rate * seconds), samples = new Uint8Array(n);
  lanes.forEach(([first, changes], k) => {
    let level = first, from = 0;
    const paint = (to) => {
      if (level) {
        for (let i = from; i < to; i++) {
          samples[i] |= 1 << k;
        }
      }
    };
    for (const [t, lv] of changes) {
      const i = Math.min(n, Math.max(from, Math.round(t * rate)));
      paint(i);
      from = i;
      level = lv;
    }
    paint(n);
  });
  return new Capture({ channels: lanes.map((_, k) => k), rate, pre: 0, post: n, samples });
}

/* A lane from pulses: [level, seconds] one after the other from t, back at rest after */
export function pulses(rest, t, parts) {
  const out = [];
  for (const [level, width] of parts) {
    out.push([t, level]);
    t += width;
  }
  out.push([t, rest]);
  return [rest, out];
}
