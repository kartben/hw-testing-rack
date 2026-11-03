/*
 * A capture as a Value Change Dump (IEEE 1364), for PulseView, GTKWave and
 * sigrok's decoders: a 1-bit wire per channel, its changes in time order.
 * Time 0 is the capture's first sample; the trigger's time is in the header.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* VCD identifiers: printable ASCII from '!' (24 channels at most) */
const ident = (k) => String.fromCharCode(33 + k);

/* names: one per captured channel, in cap.channels' order */
export function toVcd(cap, names, { date = new Date() } = {}) {
  /* A sample period in whole ns when it is one (all of gusmanb's rates), else ps */
  const ns = 1e9 / cap.rate;
  const [unit, step] = Number.isInteger(ns) ? ["1 ns", ns] : ["1 ps", Math.round(1e12 / cap.rate)];
  const out = [
    `$date ${date.toISOString()} $end`,
    "$version hw-testing-rack logic analyzer $end",
    `$comment ${cap.count} samples at ${cap.rate} S/s, trigger at sample ${cap.pre} $end`,
    `$timescale ${unit} $end`,
    "$scope module analyzer $end",
    ...cap.channels.map((c, k) =>
      `$var wire 1 ${ident(k)} ${(names[k] || `CH${c + 1}`).replace(/\s+/g, "_")} $end`),
    "$upscope $end",
    "$enddefinitions $end",
    "#0",
    "$dumpvars",
    ...cap.channels.map((_, k) => `${cap.firstLevel(k)}${ident(k)}`),
    "$end",
  ];
  /* Merge the channels' changes, in time order */
  const edges = cap.channels.map((_, k) => cap.edges(k));
  const pos = edges.map(() => 1), level = cap.channels.map((_, k) => cap.firstLevel(k));
  for (;;) {
    let next = Infinity;
    edges.forEach((e, k) => {
      if (pos[k] < e.length && e[pos[k]] < next) {
        next = e[pos[k]];
      }
    });
    if (next === Infinity) {
      break;
    }
    out.push(`#${next * step}`);
    edges.forEach((e, k) => {
      if (pos[k] < e.length && e[pos[k]] === next) {
        level[k] ^= 1;
        out.push(`${level[k]}${ident(k)}`);
        pos[k]++;
      }
    });
  }
  out.push(`#${cap.count * step}`);
  return `${out.join("\n")}\n`;
}
