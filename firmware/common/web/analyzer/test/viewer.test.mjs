/*
 * What viewer.mjs works out without a canvas: the box under the pointer and
 * what its tooltip says.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { i2c } from "../decoders.mjs";
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
