/*
 * Settings in time: what a duration takes of the buffer, and what the page warns
 * about a rate.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Capture, fastestFor, slowestOver, timing } from "../capture.mjs";
import { captureNotes, rateNeeds } from "../decoding.mjs";
import { demoCapture } from "../demo.mjs";

const PICO_2 = { maxRate: 100e6, buffer: 393216, channels: 24 };
const BYTE = [0, 1, 2, 3, 4, 5, 6, 7];

test("a duration in samples", () => {
  const t = timing(PICO_2, BYTE, 10e6, 10e-3);
  assert.deepEqual([t.samples, t.fits, t.bits], [100000, true, 8]);
  assert.equal(t.seconds, 10e-3);
  assert.equal(t.held, 393216 / 10e6);
});

test("0 asks for all the buffer holds", () => {
  const t = timing(PICO_2, BYTE, 10e6);
  assert.deepEqual([t.samples, t.fits], [393216, true]);
});

test("longer than the buffer: what fits, and it says so", () => {
  const t = timing(PICO_2, BYTE, 10e6, 1);
  assert.deepEqual([t.samples, t.fits], [393216, false]);
});

test("a channel past CH8 widens the samples, so less fits", () => {
  const t = timing(PICO_2, [0, 12], 10e6, 30e-3);
  assert.deepEqual([t.samples, t.bits, t.fits], [196608, 16, false]);
});

test("too short still takes some samples", () => {
  assert.equal(timing(PICO_2, BYTE, 1e6, 100e-6).samples, 1000);
});

test("the fastest rate for a duration, the slowest for a need", () => {
  assert.equal(fastestFor(PICO_2, BYTE, 100e-3), 2e6);
  assert.equal(fastestFor(PICO_2, BYTE, 1e-3), 100e6);
  assert.equal(fastestFor(PICO_2, BYTE, 10), null);
  assert.equal(slowestOver(PICO_2, 11.52e6), 20e6);
  assert.equal(slowestOver(PICO_2, 1e9), null);
  assert.equal(slowestOver({ ...PICO_2, maxRate: 50e6 }, 60e6), null);
});

test("a known speed against the rate", () => {
  const uart = { type: "uart", lines: { rx: 0 }, baud: 1e6 }, led = { type: "ws2812", lines: { din: 1 } };
  const i2c = { type: "i2c", lines: { sda: 2, scl: 3 } };
  assert.deepEqual(rateNeeds([uart, led, i2c], 10e6), []);
  const low = rateNeeds([uart, led, i2c], 5e6);
  assert.deepEqual(low.map((n) => n.need), [10e6, 10e6], "I²C's speed is not known beforehand");
  assert.match(low[0].text, /1,000,000 Bd reads well from 10 MS\/s up, 5 MS\/s is low/);
  assert.match(low[1].text, /^WS2812B reads well/);
  assert.equal(rateNeeds([{ type: "uart", lines: { rx: 0 } }], 1e6)[0].need, 1152000, "115200 Bd by default");
});

/* A clock on channel 3: a low and a high of this many samples, repeated */
function clocked(width) {
  const samples = new Uint8Array(400);
  for (let i = 0; i < samples.length; i++) {
    samples[i] = (Math.floor(i / width) & 1) << 0;
  }
  return new Capture({ channels: [3], rate: 10e6, pre: 0, post: samples.length, samples });
}

test("a thin clock pulse, after the capture", () => {
  const d = [{ type: "i2c", lines: { sda: null, scl: 3 } }];
  const name = (c) => `CH${c + 1}`;
  assert.deepEqual(captureNotes(clocked(3), d, name), []);
  const [n] = captureNotes(clocked(2), d, name);
  assert.match(n.text, /^CH4's shortest pulse is 2 samples wide: I²C may read wrong at 10 MS\/s\.$/);
  assert.equal(n.need, 20e6);
  const [one] = captureNotes(clocked(1), [{ type: "spi", lines: { sck: 3 } }], name);
  assert.match(one.text, /is 1 sample wide: SPI/);
  assert.equal(one.need, 40e6);
  assert.deepEqual(captureNotes(clocked(1), [{ type: "uart", lines: { rx: 3 } }], name), [], "a UART has no clock");
  assert.deepEqual(captureNotes(clocked(1), [{ type: "i2c", lines: { sda: 0, scl: 9 } }], name), [], "not captured");
});

test("the demo's clocks are not flagged", () => {
  const cap = demoCapture();
  assert.deepEqual(captureNotes(cap, [{ type: "i2c", lines: { sda: 2, scl: 3 } }], String), []);
});
