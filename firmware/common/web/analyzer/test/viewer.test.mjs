/*
 * What the viewer and the decoded table work out without a page: the box under
 * the pointer, what its tooltip says, the table's list and its search.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Capture } from "../capture.mjs";
import { i2c, uart } from "../decoders.mjs";
import { captureRows, entriesOf, hexOf, matching } from "../decoding.mjs";
import { demoCapture } from "../demo.mjs";
import { itemAt, itemLines, valueText } from "../viewer.mjs";

const items = [{ t0: 0, t1: 1, text: "a" }, { t0: 2, t1: 3, text: "b" }, { t0: 3, t1: 4, text: "c" }];

test("the item under the pointer", () => {
  assert.equal(itemAt(items, 0.5).text, "a");
  assert.equal(itemAt(items, 2).text, "b");
  assert.equal(itemAt(items, 3.5).text, "c");
  assert.equal(itemAt(items, 1.5), null, "between two boxes");
  assert.equal(itemAt(items, 5), null, "after the last");
  assert.equal(itemAt([], 1), null);
});

test("slack makes a thin box easier to hit", () => {
  assert.equal(itemAt(items, 1.2, 0.3).text, "a");
  assert.equal(itemAt(items, 1.8, 0.3).text, "b");
  assert.equal(itemAt(items, 1.5, 0.3), null);
});

test("a value in hex, decimal and, while short, binary", () => {
  assert.equal(valueText(0x41), "0x41 · 65 · 0b01000001");
  assert.equal(valueText(5), "0x05 · 5 · 0b00000101");
  assert.equal(valueText(0x123456), "0x123456 · 1193046");
});

test("a tooltip's lines", () => {
  assert.deepEqual(itemLines({ t0: 1e-3, t1: 1.5e-3, text: "A", value: 0x41 }),
                   ["A", "0x41 · 65 · 0b01000001", "1.000 ms, lasts 500.00 µs"]);
  assert.deepEqual(itemLines({ t0: 0, t1: 2e-6, text: "reset" }), ["reset", "0 ns, lasts 2.00 µs"]);
});

test("I²C boxes carry their value", () => {
  const cap = demoCapture();
  const { items: decoded } = i2c(cap, { sda: 2, scl: 3 })[0];
  const addr = decoded.find((x) => x.kind === "addr"), data = decoded.find((x) => x.kind === "data");
  assert.match(addr.text, new RegExp(`0x${addr.value.toString(16).toUpperCase().padStart(2, "0")} `));
  assert.match(data.text, new RegExp(`^0x${data.value.toString(16).toUpperCase().padStart(2, "0")} `));
});

const rows = [
  { k: 0, name: "TX", color: "--lane-0" },
  { label: "UART 1 MBd", lane: "TX", items: [{ t0: 2, t1: 3, text: "A", value: 0x41, kind: "data" },
                                             { t0: 5, t1: 6, text: "B parity", value: 0x42, kind: "err" }] },
  { label: "I²C", lane: "SDA", items: [{ t0: 1, t1: 1.5, text: "S", kind: "ctl" },
                                       { t0: 4, t1: 4.5, text: "W 0x3C ACK", value: 0x3c, kind: "addr" }] },
];

test("the table's list: every decoded row, in time order", () => {
  const e = entriesOf(rows);
  assert.deepEqual(e.map((x) => x.it.text), ["S", "A", "W 0x3C ACK", "B parity"]);
  assert.deepEqual([e[0].label, e[0].lane, e[0].hex], ["I²C", "SDA", ""]);
  assert.deepEqual([e[1].label, e[1].lane, e[1].hex], ["UART 1 MBd", "TX", "0x41"]);
  assert.deepEqual(entriesOf([{ k: 0, name: "lane only" }]), []);
});

test("hex as the table shows it", () => {
  assert.equal(hexOf(5), "0x05");
  assert.equal(hexOf(0x123456), "0x123456");
  assert.equal(hexOf(undefined), "");
});

test("a search keeps what holds every word, in any case", () => {
  const e = entriesOf(rows), texts = (q) => matching(e, q).map((x) => x.it.text);
  assert.equal(matching(e, ""), e, "no words: the whole list");
  assert.equal(matching(e, "   "), e);
  assert.deepEqual(texts("parity"), ["B parity"]);
  assert.deepEqual(texts("0X41"), ["A"], "the hex column");
  assert.deepEqual(texts("i²c"), ["S", "W 0x3C ACK"], "the decoder");
  assert.deepEqual(texts("tx"), ["A", "B parity"], "the lane");
  assert.deepEqual(texts("sda ack"), ["W 0x3C ACK"], "two words");
  assert.deepEqual(texts("nothing"), []);
});

test("a decoded row knows the lane it sits under", () => {
  const cap = demoCapture();
  const out = captureRows(cap, [{ type: "uart", lines: { rx: 0 }, baud: 1e6 }], (k) => `L${k}`);
  assert.equal(out.find((r) => r.items).lane, "L0");
  assert.ok(!("lane" in out[0]), "a lane is not its own");
});

/* A UART's bytes, 10 µs each, from this time on */
function bytes(text, t = 0, width = 10e-6) {
  return [...text].map((c, i) => ({ t0: t + i * width, t1: t + (i + 1) * width, value: c.charCodeAt(0),
                                    text: c === "\n" ? "\\n" : c === "\r" ? "\\r" : c, kind: "data" }));
}

/* What uart() makes of a capture of these bytes: a capture carries them for real */
function line(rate, baud, chunks) {
  const per = rate / baud, gaps = [];
  let i = Math.round(5 * per);
  for (const [text, pause] of chunks) {
    for (const c of text) {
      gaps.push([i, c.charCodeAt(0)]);
      i += Math.round(10 * per);
    }
    i += Math.round((pause ?? 0) * per);
  }
  const samples = new Uint8Array(i + Math.round(5 * per)).fill(1);
  for (const [at, v] of gaps) {
    [0, ...Array.from({ length: 8 }, (_, b) => (v >> b) & 1), 1].forEach((b, n) =>
      samples.fill(b, at + Math.round(n * per), at + Math.round((n + 1) * per)));
  }
  return new Capture({ channels: [0], rate, pre: 0, post: samples.length, samples });
}

test("a UART's table rows: a line of text, whole", () => {
  const cap = line(1e7, 1e6, [["Booting Zephyr\r\n"], ["*** ready\r\n"], ["no end yet"]]);
  const [row] = uart(cap, { k: 0, baud: 1e6 });
  assert.deepEqual(row.frames.map((f) => f.text), ["Booting Zephyr\\r\\n", "*** ready\\r\\n", "no end yet"]);
  assert.equal(row.frames[1].hex.split(" ")[0], "2A");
  assert.deepEqual(row.frames[1].fields.bytes.slice(0, 3), [0x2a, 0x2a, 0x2a]);
  assert.equal(row.frames[0].items.length, 16);
  assert.equal(row.items.length, 16 + 11 + 10, "the viewer keeps a box a byte");
});

test("a pause ends a binary message", () => {
  const cap = line(1e7, 1e6, [["\x01\x02\x03", 50], ["\x04\x05", 150], ["\x06"]]);
  const [row] = uart(cap, { k: 0, baud: 1e6 });
  assert.deepEqual(row.frames.map((f) => f.hex), ["01 02 03 04 05", "06"], "50 bit times is 5 bytes: not a pause");
});

test("a framing error marks its line", () => {
  const cap = line(1e7, 1e6, [["ok\n"], ["bad"]]);
  /* The stop bit of the last byte held low */
  const per = 10, n = cap.samples.length, end = n - 5 * per - per;
  cap.samples.fill(0, end, end + per);
  const [row] = uart(new Capture({ channels: [0], rate: 1e7, pre: 0, post: n, samples: cap.samples }), { k: 0, baud: 1e6 });
  assert.deepEqual(row.frames.map((f) => f.kind), ["data", "err"]);
});

test("the table searches a whole word, and both spellings of hex", () => {
  const cap = line(1e7, 1e6, [["Booting Zephyr\r\n"], ["*** ready\r\n"]]);
  const e = entriesOf(captureRows(cap, [{ type: "uart", lines: { rx: 0 }, baud: 1e6 }], () => "TX"));
  assert.equal(e.length, 2);
  assert.deepEqual(matching(e, "booting").map((x) => x.it.t0), [e[0].it.t0]);
  assert.equal(matching(e, "ready").length, 1);
  assert.equal(matching(e, "0x42").length, 1, "B, written the way C does");
  assert.equal(matching(e, "2A 2A").length, 1, "the hex column as shown");
  assert.equal(e[0].items.length, 16, "a row marks all its boxes");
});

test("a row without frames: a table row a box", () => {
  const e = entriesOf([{ label: "x", items: bytes("ab") }]);
  assert.deepEqual(e.map((x) => [x.it.text, x.items.length, x.hex]), [["a", 1, "0x61"], ["b", 1, "0x62"]]);
});
