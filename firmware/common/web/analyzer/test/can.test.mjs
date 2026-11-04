/*
 * The CAN decoder on frames built here from ISO 11898-1's format: stuff bits,
 * CRC-15 and all.  The bench has no CAN yet.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { can } from "../decoders.mjs";
import { rateNeeds } from "../decoding.mjs";
import { captureOf } from "./signals.mjs";

const bits = (v, n) => Array.from({ length: n }, (_, i) => Math.floor(v / 2 ** (n - 1 - i)) & 1);

function crc15(stream) {
  let crc = 0;
  for (const b of stream) {
    const top = b ^ ((crc >> 14) & 1);
    crc = (crc << 1) & 0x7fff;
    if (top) {
      crc ^= 0x4599;
    }
  }
  return crc;
}

/* The bits on the wire of a frame, stuffed from the start of frame to the end of the CRC */
function frameBits({ id, ext = false, rtr = false, data = [], dlc = data.length, ack = true, badCrc = false, fd = false }) {
  const head = [0, ...(ext ? [...bits(Math.floor(id / 2 ** 18), 11), 1, 1, ...bits(id % 2 ** 18, 18), rtr ? 1 : 0, fd ? 1 : 0, 0]
                           : [...bits(id, 11), rtr ? 1 : 0, 0, fd ? 1 : 0]), ...bits(dlc, 4), ...data.flatMap((v) => bits(v, 8))];
  const crc = crc15(head) ^ (badCrc ? 1 : 0), plain = [...head, ...bits(crc, 15)];
  const wire = [];
  let run = 0, last = -1;
  for (const b of plain) {
    wire.push(b);
    run = b === last ? run + 1 : 1;
    last = b;
    if (run === 5) {
      last = b ? 0 : 1;
      wire.push(last);
      run = 1;
    }
  }
  return [...wire, 1, ack ? 0 : 1, 1, 1, 1, 1, 1, 1, 1, 1];
}

/* Frames on a line, a few recessive bits apart */
function line(frames, { baud = 500e3, rate = 10e6, drift = 1, gap = 5 } = {}) {
  const t = 1 / baud * drift, changes = [];
  let at = 20e-6, level = 1;
  for (const f of frames) {
    for (const b of Array.isArray(f) ? f : frameBits(f)) {
      if (b !== level) {
        changes.push([at, b]);
        level = b;
      }
      at += t;
    }
    at += gap * t;
  }
  return captureOf(rate, at + 50e-6, [[1, changes]]);
}

const decode = (frames, opts = {}) => can(line(frames, opts), { k: 0, baud: opts.baud ?? 500e3 })[0];

test("a base frame: identifier, data, CRC, ACK", () => {
  const row = decode([{ id: 0x123, data: [0xde, 0xad, 0xbe, 0xef] }]);
  assert.deepEqual(row.items.map((x) => x.text), ["0x123 [4]", "0xDE", "0xAD", "0xBE", "0xEF", "CRC", "ACK"]);
  assert.deepEqual(row.frames[0].fields, { id: 0x123, extended: false, rtr: false, dlc: 4, data: [0xde, 0xad, 0xbe, 0xef], crcOk: true, ack: true });
  assert.equal(row.frames[0].text, "0x123 [4] 0xDE 0xAD 0xBE 0xEF");
  assert.equal(row.frames[0].hex, "DE AD BE EF");
  assert.equal(row.label, "CAN 500 kbit/s");
});

test("an extended frame", () => {
  const row = decode([{ id: 0x18daf110, ext: true, data: [0x02, 0x10] }]);
  assert.equal(row.frames[0].fields.id, 0x18daf110);
  assert.equal(row.frames[0].fields.extended, true);
  assert.equal(row.items[0].text, "0x18DAF110 [2]");
  assert.equal(row.frames[0].fields.crcOk, true);
});

test("a remote frame has no data, whatever its DLC", () => {
  const row = decode([{ id: 0x7ff, rtr: true, dlc: 8 }]);
  assert.deepEqual(row.items.map((x) => x.text), ["0x7FF RTR [8]", "CRC", "ACK"]);
  assert.deepEqual(row.frames[0].fields.data, []);
});

test("a DLC over 8 still means 8 bytes", () => {
  const row = decode([{ id: 1, data: [1, 2, 3, 4, 5, 6, 7, 8], dlc: 15 }]);
  assert.equal(row.frames[0].fields.dlc, 15);
  assert.equal(row.frames[0].fields.data.length, 8);
  assert.equal(row.frames[0].fields.crcOk, true);
});

test("stuff bits: long runs of one level come back whole", () => {
  for (const data of [[0, 0, 0, 0], [0xff, 0xff, 0xff, 0xff], [0xf0, 0x0f, 0x83, 0xe0], [0, 0, 0, 0, 0, 0, 0, 0]]) {
    const row = decode([{ id: 0, data }]);
    assert.deepEqual(row.frames[0].fields.data, data);
    assert.equal(row.frames[0].fields.crcOk, true, JSON.stringify(data));
    assert.equal(row.frames[0].kind, "data");
  }
});

test("every identifier's CRC holds, over a run of frames", () => {
  const frames = Array.from({ length: 64 }, (_, i) => ({ id: (i * 97) & 0x7ff, data: Array.from({ length: i % 9 }, (_, j) => (i * (j + 3)) & 255) }));
  const row = decode(frames);
  assert.equal(row.frames.length, frames.length);
  row.frames.forEach((f, i) => {
    assert.equal(f.fields.id, frames[i].id);
    assert.deepEqual(f.fields.data, frames[i].data);
    assert.equal(f.fields.crcOk, true);
  });
});

test("a bad CRC, and no ACK, are told apart", () => {
  const bad = decode([{ id: 0x10, data: [1], badCrc: true }]);
  assert.match(bad.items.at(-2).text, /^CRC 0x[0-9A-F]{4}, 0x[0-9A-F]{4} expected$/);
  assert.equal(bad.frames[0].kind, "err");
  const lone = decode([{ id: 0x10, data: [1], ack: false }]);
  assert.equal(lone.frames[0].kind, "data", "a sender's own TX pin shows no ACK");
  assert.equal(lone.frames[0].fields.ack, false);
  assert.match(lone.frames[0].text, /\(no ACK\)$/);
});

test("clocks a little apart: the edges keep it in step", () => {
  const row = decode([{ id: 0x555, data: [0x55, 0xaa, 0x33, 0xcc, 0x0f, 0xf0, 0x12, 0x34] }], { drift: 1.01 });
  assert.equal(row.frames[0].fields.crcOk, true);
});

test("a stuff error stops the frame, and the next one still reads", () => {
  const broken = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1];
  const row = decode([broken, { id: 0x42, data: [7] }], { gap: 12 });
  assert.equal(row.frames[0].text, "stuff error");
  assert.equal(row.frames[0].kind, "err");
  assert.equal(row.frames.at(-1).fields.id, 0x42);
});

test("an FD frame is named, not read, and the next one still reads", () => {
  const row = decode([{ id: 0x100, fd: true, data: [1, 2] }, { id: 0x42, data: [7] }], { gap: 12 });
  assert.equal(row.frames[0].text, "CAN FD frame: not read");
  assert.equal(row.frames.at(-1).fields.id, 0x42);
});

test("a capture that starts inside a frame finds the next one", () => {
  const whole = frameBits({ id: 0x321, data: [9, 8, 7] });
  const row = decode([whole.slice(25), { id: 0x42, data: [7] }], { gap: 12 });
  assert.equal(row.frames.at(-1).fields.id, 0x42);
  assert.equal(row.frames.at(-1).fields.crcOk, true);
});

test("a frame cut by the end of the capture says so", () => {
  const cap = line([{ id: 0x123, data: [1, 2, 3, 4] }]);
  const cut = captureOf(cap.rate, 60e-6, [[1, []]]);
  cut.samples.set(cap.samples.subarray(0, cut.samples.length));
  const row = can(cut, { k: 0, baud: 500e3 })[0];
  assert.equal(row.frames[0].text, "0x123 [4] cut off", "what was read, then why it stops");
});

test("other bit rates, and the rate it needs", () => {
  for (const baud of [125e3, 250e3, 1e6]) {
    const row = decode([{ id: 0x77, data: [0xa5] }], { baud, rate: 20e6 });
    assert.equal(row.frames[0].fields.crcOk, true, String(baud));
    assert.equal(row.label, `CAN ${baud / 1e3} kbit/s`);
  }
  assert.deepEqual(rateNeeds([{ type: "can", lines: { rx: 0 }, baud: 500e3 }], 5e6), []);
  assert.equal(rateNeeds([{ type: "can", lines: { rx: 0 } }], 2e6)[0].need, 5e6, "500 kbit/s by default");
  assert.throws(() => decode([{ id: 1 }], { rate: 1e6 }), /CAN at 500 kbit\/s needs 2\.0 MS\/s/);
});
