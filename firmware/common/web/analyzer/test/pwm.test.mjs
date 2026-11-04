/*
 * The PWM and clock decoder on made-up signals.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { pwm } from "../decoders.mjs";
import { captureNotes, captureRows, entriesOf } from "../decoding.mjs";
import { itemLines } from "../viewer.mjs";
import { captureOf, pulses } from "./signals.mjs";

const square = (high, low, n) => Array.from({ length: n }, () => [[1, high], [0, low]]).flat();

test("a steady signal is one box, with its frequency and duty cycle", () => {
  const cap = captureOf(10e6, 1e-3, [pulses(0, 1e-6, square(25e-6, 75e-6, 9))]);
  const [row] = pwm(cap, { k: 0 });
  assert.equal(row.items.length, 1);
  assert.equal(row.items[0].text, "10.000 kHz · 25.0 %");
  assert.equal(row.items[0].count, 8, "from rising edge to rising edge: the last high has no end");
  assert.ok(Math.abs(row.stats.freq.mean - 10e3) < 1);
  assert.ok(Math.abs(row.stats.duty.mean - 25) < 0.01);
  assert.equal(row.stats.periods, 8);
  assert.deepEqual(itemLines(row.items[0]).slice(0, 2), ["10.000 kHz · 25.0 %", "8 periods, 100.00 µs each"]);
});

test("a change of duty cycle or frequency starts a new box", () => {
  const parts = [...square(25e-6, 75e-6, 4), ...square(50e-6, 50e-6, 4), ...square(10e-6, 10e-6, 4)];
  const cap = captureOf(10e6, 2e-3, [pulses(0, 1e-6, parts)]);
  const [row] = pwm(cap, { k: 0 });
  assert.deepEqual(row.items.map((x) => x.text), ["10.000 kHz · 25.0 %", "10.000 kHz · 50.0 %", "50.000 kHz · 50.0 %"]);
  assert.equal(row.stats.freq.max, 50e3);
  assert.equal(row.stats.freq.min, 10e3);
  assert.equal(row.stats.periods, 11, "12 rising edges");
});

test("a sample's wobble does not split a box", () => {
  const parts = [[1, 2.0e-6], [0, 2.1e-6], [1, 2.0e-6], [0, 2.0e-6], [1, 2.1e-6], [0, 2.0e-6], [1, 2.0e-6], [0, 2.0e-6]];
  const cap = captureOf(10e6, 40e-6, [pulses(0, 1e-6, parts)]);
  assert.equal(pwm(cap, { k: 0 })[0].items.length, 1);
});

test("a level that never changes, or one pulse: no period", () => {
  for (const lane of [[0, []], [1, []], pulses(0, 1e-6, [[1, 1e-6]])]) {
    const [row] = pwm(captureOf(1e6, 1e-4, [lane]), { k: 0 });
    assert.deepEqual([row.items, row.stats], [[], { periods: 0 }]);
  }
});

test("it starts at a rising edge, whatever the first level", () => {
  const cap = captureOf(1e6, 2e-3, [pulses(1, 100e-6, square(100e-6, 100e-6, 3))]);
  const [row] = pwm(cap, { k: 0 });
  assert.ok(row.items.length >= 1);
  assert.equal(row.items[0].text, "5.000 kHz · 50.0 %");
});

test("in the table, and flagged when the rate is too low", () => {
  const cap = captureOf(10e6, 20e-6, [pulses(0, 1e-6, square(100e-9, 100e-9, 40))]);
  const d = [{ type: "pwm", lines: { in: 0 } }];
  const e = entriesOf(captureRows(cap, d, () => "CLK"));
  assert.equal(e[0].it.text, "5.000 MHz · 50.0 %");
  assert.match(captureNotes(cap, d, () => "CLK")[0].text, /^CLK's shortest pulse is 1 sample wide/);
});
