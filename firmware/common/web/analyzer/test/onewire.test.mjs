/*
 * The 1-Wire decoder on signals made from the bus's published timings.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { onewire } from "../decoders.mjs";
import { rateNeeds } from "../decoding.mjs";
import { captureOf, pulses } from "./signals.mjs";

const us = (n) => n * 1e-6;
const RESET = [[0, us(480)], [1, us(30)], [0, us(120)], [1, us(330)]];
const NO_DEVICE = [[0, us(480)], [1, us(480)]];
/* A slot of 70 µs: a 1 is low for 6 µs, a 0 for 60 */
const bit = (b) => (b ? [[0, us(6)], [1, us(64)]] : [[0, us(60)], [1, us(10)]]);
const byte = (v) => Array.from({ length: 8 }, (_, i) => bit((v >> i) & 1)).flat();
const bus = (parts, rate = 1e6) => {
  const seconds = parts.reduce((a, [, w]) => a + w, 0) + us(200);
  return captureOf(rate, seconds, [pulses(1, us(100), parts)]);
};
const decode = (parts, rate) => onewire(bus(parts, rate), { k: 0 })[0];
const texts = (row) => row.items.map((x) => x.text);

test("a reset, its presence, SKIP ROM, a function command", () => {
  const row = decode([...RESET, ...byte(0xcc), ...byte(0x44)]);
  assert.deepEqual(texts(row), ["reset", "presence", "0xCC SKIP ROM", "0x44"]);
  assert.deepEqual(row.items.slice(2).map((x) => x.value), [0xcc, 0x44]);
  assert.deepEqual(row.frames.map((f) => [f.text, f.kind, f.hex]), [["0xCC SKIP ROM 0x44", "data", "CC 44"]]);
  assert.deepEqual(row.frames[0].fields, { presence: true, command: "SKIP ROM", rom: null, bytes: [0x44] });
});

test("no device answers", () => {
  const row = decode([...NO_DEVICE]);
  assert.deepEqual(texts(row), ["reset", "no presence"]);
  assert.equal(row.frames[0].kind, "err");
  assert.equal(row.frames[0].fields.presence, false);
});

/* The worked example of Maxim's application note 27, as it goes on the wire: family 0x02, CRC 0xA2 */
const ROM = [0x02, 0x1c, 0xb8, 0x01, 0x00, 0x00, 0x00, 0xa2];

test("READ ROM: the code, whole, CRC checked, then bytes", () => {
  const row = decode([...RESET, ...byte(0x33), ...ROM.flatMap(byte), ...byte(0xbe), ...byte(0x50)]);
  assert.deepEqual(texts(row), ["reset", "presence", "0x33 READ ROM", "ROM A200000001B81C02", "0xBE", "0x50"]);
  assert.equal(row.frames[0].fields.rom, "A200000001B81C02");
  assert.equal(row.frames[0].kind, "data");
});

test("a ROM code with a bad CRC, or cut short, says so", () => {
  const bad = [...ROM.slice(0, 7), 0x00];
  assert.equal(texts(decode([...RESET, ...byte(0x55), ...bad.flatMap(byte)])).at(-1), "ROM 0000000001B81C02 CRC bad");
  const cut = decode([...RESET, ...byte(0x55), ...ROM.slice(0, 3).flatMap(byte), ...RESET]);
  assert.deepEqual(texts(cut).slice(3, 4), ["ROM cut after 3 bytes"]);
  assert.equal(cut.frames[0].kind, "err");
});

test("SEARCH ROM makes bits, not bytes", () => {
  const row = decode([...RESET, ...byte(0xf0), ...Array.from({ length: 12 }, () => bit(1)).flat(), ...RESET]);
  assert.deepEqual(texts(row).slice(0, 4), ["reset", "presence", "0xF0 SEARCH ROM", "12 search bits"]);
  assert.equal(row.frames.length, 2);
});

test("a byte cut short, and a low that is neither a bit nor a reset", () => {
  const row = decode([...RESET, ...byte(0xcc), bit(1)[0], bit(1)[1], bit(0)[0], bit(0)[1], ...RESET]);
  assert.deepEqual(texts(row).slice(3, 4), ["2 bits"]);
  const odd = decode([[0, us(200)], [1, us(100)]]);
  assert.deepEqual(texts(odd), ["low 200 µs"]);
});

test("each frame runs from a reset to the next", () => {
  const row = decode([...RESET, ...byte(0xcc), ...RESET, ...byte(0xcc), ...byte(0xbe)]);
  assert.deepEqual(row.frames.map((f) => f.text), ["0xCC SKIP ROM", "0xCC SKIP ROM 0xBE"]);
});

test("a faster capture reads the same", () => {
  assert.deepEqual(texts(decode([...RESET, ...byte(0xcc)], 10e6)), ["reset", "presence", "0xCC SKIP ROM"]);
});

test("the rate: flagged under 1 MS/s, refused when a bit cannot be read", () => {
  assert.deepEqual(rateNeeds([{ type: "onewire", lines: { dq: 0 } }], 1e6), []);
  assert.equal(rateNeeds([{ type: "onewire", lines: { dq: 0 } }], 500e3)[0].need, 1e6);
  assert.throws(() => onewire(bus(RESET, 50e3), { k: 0 }), /1-Wire needs/);
});
