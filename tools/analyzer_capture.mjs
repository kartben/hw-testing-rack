/*
 * bayctl capture's other half (tools/bayctl.py): one capture through a bay
 * node's relay, with no browser, saved as the page saves it and decoded by the
 * page's own decoders, so that a test asserts what the viewer would show.
 * What to do comes as JSON on stdin:
 *
 *   {"origin": "http://bay-b3.local", "source": "B3", "channels": [0, 1], "names": ["A", "B"],
 *    "rate": 10000000, "seconds": 0.02, "pre": 0.2, "trigger": {"channel": 0, "edge": "fall"},
 *    "reset": {"port": 2, "slot": "B3.2"}, "decoders": [{"type": "uart", "lines": {"rx": 0}, "baud": 115200}],
 *    "timeout": 10, "out": "run1"}
 *
 * It prints "armed" once the analyzer waits for its trigger, and writes
 * <out>.capture.json and <out>.decoded.json.  Exits 0; 1 with why on stderr; 3
 * if the trigger did not come in time.  Node 22 or later, for its WebSocket.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { writeFileSync } from "node:fs";

import { Capture, timing, toFile } from "../firmware/common/web/analyzer/capture.mjs";
import { DECODERS } from "../firmware/common/web/analyzer/decoders.mjs";
import { captureNotes, captureRows, rateNeeds } from "../firmware/common/web/analyzer/decoding.mjs";
import { Analyzer, TRIGGER } from "../firmware/common/web/analyzer/protocol.mjs";
import { openRelay } from "../firmware/common/web/analyzer/relay.mjs";
import { fmtTime } from "../firmware/common/web/analyzer/viewer.mjs";

const NO_TRIGGER = 3;

class Failed extends Error {
  constructor(message, code = 1) {
    super(message);
    this.code = code;
  }
}

const withTimeout = (p, ms, why) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Failed(why)), ms))]);

async function get(origin, path) {
  const r = await fetch(`${origin}${path}`);
  return r.ok ? r.json() : null;
}

/* Why the node would not open the analyzer */
async function refusal(origin, e) {
  const a = await get(origin, "/api/analyzer").catch(() => null);
  return !a ? `no analyzer on this node (${e.message})`
       : !a.present ? "the analyzer is not on the bus: no image loaded yet, or the DATA ×4 is off"
       : a.owner !== "page" ? "USB/IP has the analyzer: POST /api/analyzer or the bay page switches it back"
       : a.page ? `${a.page.ip} is using the analyzer` : e.message;
}

/* The decoders asked for, each with what it reads */
function check(decoders, channels) {
  for (const d of decoders) {
    const spec = DECODERS[d.type];
    if (!spec) {
      throw new Failed(`no decoder "${d.type}": ${Object.keys(DECODERS).join(", ")}`);
    }
    for (const line of spec.lines) {
      const role = line.replace("?", ""), c = d.lines[role];
      if (c === undefined || c === null) {
        if (!line.endsWith("?")) {
          throw new Failed(`${d.type} needs ${role}=`);
        }
      } else if (!channels.includes(c)) {
        throw new Failed(`${d.type} ${role}: channel ${c + 1} is not captured`);
      }
    }
  }
}

/* The decoded rows as a script reads them: the boxes, and the values in order */
function decodedDoc(cap, rows, spec, saved) {
  return {
    format: "hwtr-analyzer-decoded", version: 1, source: spec.source, saved,
    rate: cap.rate, samples: cap.count, pre: cap.pre,
    rows: rows.filter((r) => r.items).map((r) => ({
      label: r.label, lane: r.lane,
      items: r.items.map(({ t0, t1, text, kind, value }) => ({ t0, t1, text, kind, value })),
      values: r.items.filter((it) => it.value !== undefined && it.kind !== "err").map((it) => it.value),
    })),
  };
}

const rowText = (r) => r.items.map((it) => it.text).join(r.label.startsWith("UART") ? "" : " ");

async function run(spec) {
  const { origin, channels, names, rate, decoders } = spec;
  if (!globalThis.WebSocket) {
    throw new Failed(`bayctl capture needs Node 22 or later (this is ${process.version})`);
  }
  check(decoders, channels);
  let t;
  try {
    t = await openRelay(origin);
  } catch (e) {
    throw new Failed(await refusal(origin, e));
  }
  try {
    const analyzer = new Analyzer(t);
    const info = await withTimeout(analyzer.identify(), 3000, "the analyzer does not answer");
    if (rate > info.maxRate) {
      throw new Failed(`${rate / 1e6} MS/s: this analyzer goes up to ${info.maxRate / 1e6} MS/s`);
    }
    const plan = timing(info, channels, rate, spec.seconds);
    if (!plan.fits) {
      console.error(`warning: at ${rate / 1e6} MS/s the buffer holds ${fmtTime(plan.held)} of the ${fmtTime(spec.seconds)} asked`);
    }
    for (const n of rateNeeds(decoders, rate)) {
      console.error(`warning: ${n.text}`);
    }
    const pre = Math.round(plan.samples * spec.pre), signal = AbortSignal.timeout(spec.timeout * 1000);
    let raw;
    try {
      raw = await analyzer.capture({
        channels, rate, pre, post: plan.samples - pre,
        trigger: { type: TRIGGER.EDGE, channel: spec.trigger.channel, inverted: spec.trigger.edge === "fall" },
      }, {
        signal,
        onStarted: () => {
          console.log("armed");
          if (spec.reset) {
            fetch(`${origin}/api/reset`, { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ port: spec.reset.port }) })
              .then((r) => r.ok || console.error(`warning: ${spec.reset.slot} not reset: ${r.status}`))
              .catch((e) => console.error(`warning: ${spec.reset.slot} not reset: ${e.message}`));
          }
        },
      });
    } catch (e) {
      throw signal.aborted ? new Failed(`no trigger in ${spec.timeout} s`, NO_TRIGGER) : e;
    }
    const cap = new Capture(raw), saved = new Date().toISOString();
    const rows = captureRows(cap, decoders, (k) => names[k]);
    const name = (c) => names[channels.indexOf(c)];
    for (const n of captureNotes(cap, decoders, name)) {
      console.error(`warning: ${n.text}`);
    }
    writeFileSync(`${spec.out}.capture.json`, toFile(cap, names, decoders, { source: spec.source, saved }));
    writeFileSync(`${spec.out}.decoded.json`, JSON.stringify(decodedDoc(cap, rows, spec, saved), null, 1));
    console.log(`${spec.source}: ${cap.count.toLocaleString("en-US")} samples at ${rate / 1e6} MS/s, ${fmtTime(cap.count / rate)}`);
    for (const r of rows.filter((x) => x.items)) {
      console.log(`  ${r.label} (${r.lane}), ${r.items.length}: ${rowText(r).slice(0, 200)}`);
    }
    console.log(`wrote ${spec.out}.capture.json, ${spec.out}.decoded.json`);
  } finally {
    await t.close();
  }
}

let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) {
  input += chunk;
}
try {
  await run(JSON.parse(input));
  process.exit(0);
} catch (e) {
  console.error(`bayctl capture: ${e.message}`);
  process.exit(e.code ?? 1);
}
