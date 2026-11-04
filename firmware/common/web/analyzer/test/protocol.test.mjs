/*
 * protocol.mjs and capture.mjs against the fake analyzer:
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Capture, timing } from "../capture.mjs";
import { Analyzer, TRIGGER, bytesPerSample, captureRequest, frame } from "../protocol.mjs";
import { FakeAnalyzer } from "./fake_analyzer.mjs";

const PICO2 = { board: "PICO_2", version: "6.0", maxRate: 100e6, blastRate: 200e6, buffer: 393216, channels: 24 };

test("a request on the wire: framed, 0x55 0xAA 0xF0 escaped", () => {
  assert.deepEqual([...frame(1, Uint8Array.of(0x55, 0xaa, 0xf0, 7))],
                   [0x55, 0xaa, 1, 0xf0, 0xa5, 0xf0, 0x5a, 0xf0, 0x00, 7, 0xaa, 0x55]);
  assert.deepEqual([...frame(0)], [0x55, 0xaa, 0, 0xaa, 0x55]);
});

test("the capture request: 48 bytes, the firmware's layout", () => {
  const r = captureRequest({ channels: [0, 1, 13], rate: 10e6, pre: 1000, post: 9000,
                             trigger: { type: TRIGGER.EDGE, channel: 1, inverted: true } }, PICO2);
  const v = new DataView(r.buffer);
  assert.equal(r.length, 48);
  assert.deepEqual([v.getUint8(0), v.getUint8(1), v.getUint8(2)], [0, 1, 1]);
  assert.deepEqual([...r.subarray(6, 9)], [0, 1, 13]);
  assert.equal(v.getUint8(30), 3);
  assert.deepEqual([v.getUint32(32, true), v.getUint32(36, true), v.getUint32(40, true)], [10e6, 1000, 9000]);
  assert.equal(v.getUint8(46), 1, "CH14 (13): 16-bit samples");
  assert.equal(bytesPerSample([0, 7]), 1);
  assert.equal(bytesPerSample([16]), 4);
});

test("what the request refuses before it goes", () => {
  const ok = { channels: [0], rate: 1e6, pre: 10, post: 10 };
  assert.throws(() => captureRequest({ ...ok, channels: [] }, PICO2), /channels/);
  assert.throws(() => captureRequest({ ...ok, channels: [24] }, PICO2), /channels/);
  assert.throws(() => captureRequest({ ...ok, rate: 200e6 }, PICO2), /sample rate/);
  assert.doesNotThrow(() => captureRequest({ ...ok, rate: 200e6, trigger: { type: TRIGGER.BLAST } }, PICO2));
  assert.throws(() => captureRequest({ ...ok, pre: 200000, post: 193217 }, PICO2), /393216 at most/);
  assert.throws(() => captureRequest({ ...ok, channels: [8], pre: 100000, post: 96609 }, PICO2), /196608 at most/);
});

test("identify, then capture 8 channels in uneven chunks", async () => {
  const fake = new FakeAnalyzer({ chunk: 7 });
  const a = new Analyzer(fake.transport());
  assert.deepEqual(await a.identify(), PICO2);

  let started = false;
  const p = a.capture({ channels: [0, 2, 5], rate: 1e6, pre: 100, post: 300 }, { onStarted: () => (started = true) });
  await new Promise((r) => setTimeout(r, 10));
  assert.ok(started);
  assert.equal(fake.last.size, 48);
  /* Channel 0 toggles each sample, channel 2 high from sample 100, channel 5 low */
  fake.trigger((i) => (i & 1) | (i >= 100 ? 4 : 0));
  const c = new Capture(await p);
  assert.equal(c.count, 400);
  assert.ok(c.samples instanceof Uint8Array);
  assert.equal(c.level(0, 3), 1);
  assert.equal(c.edges(0).length, 400);
  assert.deepEqual([...c.edges(1)], [0, 100]);
  assert.equal(c.firstLevel(1), 0);
  assert.deepEqual([...c.edges(2)], [0]);
  assert.equal(c.time(100), 0, "the trigger is at sample pre");
  assert.equal(c.index(-1e-4), 0);
});

test("16-bit samples (a channel past CH8) and burst stamps", async () => {
  const fake = new FakeAnalyzer({ chunk: 1000 });
  const a = new Analyzer(fake.transport());
  await a.identify();
  const p = a.capture({ channels: [1, 12], rate: 2e6, pre: 10, post: 54, loops: 2, measure: true });
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(fake.last.mode, 1);
  fake.trigger((i) => (i >= 32 ? 1 << 12 : 2), [0, 1000, 2000]);
  const r = await p;
  assert.ok(r.samples instanceof Uint16Array);
  const c = new Capture(r);
  assert.deepEqual([...c.edges(0)], [0, 32]);
  assert.equal(c.firstLevel(0), 1);
  assert.deepEqual([...c.edges(1)], [0, 32]);
  assert.deepEqual([...r.stamps], [0, 1000, 2000]);
});

test("a refused capture, and a cancelled one", async () => {
  const fake = new FakeAnalyzer();
  const a = new Analyzer(fake.transport());
  await a.identify();
  fake.refuse = true;
  await assert.rejects(a.capture({ channels: [0], rate: 1e6, pre: 1, post: 1 }), /refused/);

  fake.refuse = false;
  const stop = new AbortController();
  const p = a.capture({ channels: [0], rate: 1e6, pre: 1, post: 1 }, { signal: stop.signal });
  await new Promise((r) => setTimeout(r, 5));
  stop.abort();
  await assert.rejects(p, { name: "AbortError" });
  assert.equal(fake.cancelled, 1);
  /* The analyzer answers the next request as before */
  assert.equal((await a.identify()).board, "PICO_2");
});

test("timing: the samples a capture holds", () => {
  const t = timing(PICO2, [0, 7], 10e6);
  assert.deepEqual([t.samples, t.bits], [393216, 8]);
  assert.equal(t.held, 393216 / 10e6);
  assert.equal(timing(PICO2, [0, 12], 1e6).samples, 196608);
  assert.equal(timing(PICO2, [20], 1e6).samples, 98304);
});
