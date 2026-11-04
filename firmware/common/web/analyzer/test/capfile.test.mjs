/*
 * A capture file: what comes back is what went in, and a bad file says why.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Capture, fromFile, toFile } from "../capture.mjs";
import { i2c, uart } from "../decoders.mjs";
import { DEMO_DECODERS, DEMO_NAMES, demoCapture } from "../demo.mjs";

const fields = (o) => JSON.parse(o);
const small = (Word, channels, words) => new Capture({ channels, rate: 1e6, pre: 1, post: words.length - 1,
                                                       samples: Word.from(words) });
const saved = (over = {}) => JSON.stringify({ ...fields(toFile(small(Uint8Array, [0], [0, 1, 1]), ["TX"], [])), ...over });

test("the demo comes back whole, its decoders reading the same", () => {
  const cap = demoCapture();
  const { cap: back, decoders, source, saved: when } = fromFile(
    toFile(cap, DEMO_NAMES, DEMO_DECODERS, { source: "b3", saved: "2026-11-04T08:00:00.000Z" }));
  assert.deepEqual([...back.samples], [...cap.samples]);
  assert.deepEqual([back.channels, back.rate, back.pre, back.post, back.names],
                   [cap.channels, cap.rate, cap.pre, cap.post, DEMO_NAMES]);
  assert.deepEqual(decoders, DEMO_DECODERS.map((d) => (d.type === "spi" ? { ...d, lines: { ...d.lines, miso: null } } : d)));
  assert.deepEqual([source, when], ["b3", "2026-11-04T08:00:00.000Z"]);
  const texts = (c) => uart(c, { k: 0, baud: 1e6 })[0].items.map((x) => x.text).join("");
  assert.equal(texts(back), texts(cap));
  assert.deepEqual(i2c(back, { sda: 2, scl: 3 })[0].items.map((x) => x.text), i2c(cap, { sda: 2, scl: 3 })[0].items.map((x) => x.text));
});

test("every sample width", () => {
  for (const [Word, words] of [[Uint8Array, [0, 0xff, 0x81]], [Uint16Array, [0, 0xffff, 0x8001]], [Uint32Array, [0, 0xffffffff, 0x80000001]]]) {
    const { cap } = fromFile(toFile(small(Word, [0, 1], words), ["a", "b"], []));
    assert.ok(cap.samples instanceof Word, Word.name);
    assert.deepEqual([...cap.samples], words);
  }
});

test("a file a script can read: base64 of little-endian words", () => {
  const f = fields(toFile(small(Uint16Array, [0, 12], [0x0102, 0x0304]), ["x", "y"], []));
  assert.equal(f.format, "hwtr-analyzer-capture");
  assert.equal(f.bytesPerSample, 2);
  assert.deepEqual([...Buffer.from(f.samples, "base64")], [2, 1, 4, 3]);
});

test("a capture larger than a call's arguments", () => {
  const n = 393216, samples = new Uint8Array(n).map((_, i) => i & 255);
  const { cap } = fromFile(toFile(new Capture({ channels: [0], rate: 1e6, pre: 0, post: n, samples }), ["x"], []));
  assert.equal(cap.count, n);
  assert.equal(cap.samples[n - 1], (n - 1) & 255);
});

test("names missing: the channel's", () => {
  assert.deepEqual(fromFile(saved({ names: undefined })).cap.names, ["CH1"]);
});

test("a bad file says why", () => {
  assert.throws(() => fromFile("nonsense"), /not JSON/);
  assert.throws(() => fromFile("{}"), /not a capture file/);
  assert.throws(() => fromFile("null"), /not a capture file/);
  assert.throws(() => fromFile(saved({ version: 2 })), /version 2/);
  assert.throws(() => fromFile(saved({ rate: 0 })), /damaged/);
  assert.throws(() => fromFile(saved({ bytesPerSample: 3 })), /damaged/);
  assert.throws(() => fromFile(saved({ channels: ["<b>"] })), /damaged/);
  assert.throws(() => fromFile(saved({ pre: 0.5 })), /damaged/);
  assert.throws(() => fromFile(saved({ post: 500 })), /3 bytes of samples, 501 expected/);
  assert.throws(() => fromFile(saved({ samples: "%%%" })), /its samples/);
});

test("a file's decoders: known types, numbers where numbers go, nothing else", () => {
  const { decoders } = fromFile(saved({ decoders: [
    { type: "uart", lines: { rx: 0 }, baud: "<img src=x>", label: "<script>" },
    { type: "uart", lines: { rx: "<b>" }, baud: 9600 },
    { type: "spi", lines: { cs: 0, sck: 1, mosi: 2 }, mode: "<i>" },
    { type: "nope", lines: {} },
    { type: "__proto__", lines: {} },
    null,
  ] }));
  assert.deepEqual(decoders, [
    { type: "uart", lines: { rx: 0 } },
    { type: "uart", lines: { rx: null }, baud: 9600 },
    { type: "spi", lines: { cs: 0, sck: 1, mosi: 2, miso: null } },
  ]);
  assert.deepEqual(fromFile(saved({ decoders: "no" })).decoders, []);
});
