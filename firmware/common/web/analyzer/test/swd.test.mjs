/*
 * The SWD decoder on sequences built here from Arm's protocol description.
 * The bench has no SWD target on the analyzer yet.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { swd } from "../decoders.mjs";
import { captureNotes } from "../decoding.mjs";
import { captureOf } from "./signals.mjs";

const lsb = (v, n) => Array.from({ length: n }, (_, i) => Math.floor(v / 2 ** i) & 1);
const parityOf = (a) => a.reduce((x, y) => x ^ y, 0);

function request(ap, read, addr) {
  const body = [ap ? 1 : 0, read ? 1 : 0, (addr >> 2) & 1, (addr >> 3) & 1];
  return [1, ...body, parityOf(body), 0, 1];
}

const OK = [1, 0, 0], WAIT = [0, 1, 0], FAULT = [0, 0, 1];
const TRN = [0];
/* Bits the target drives */
const target = (a) => a.map((v) => ({ v }));

const read = (ap, addr, data, ack = OK, badParity = false) => [...request(ap, true, addr), ...TRN, ...target(ack),
  ...(ack === OK ? [...target(lsb(data, 32)), ...target([parityOf(lsb(data, 32)) ^ (badParity ? 1 : 0)]), ...TRN] : TRN)];
const write = (ap, addr, data, ack = OK) => [...request(ap, false, addr), ...TRN, ...target(ack), ...TRN,
  ...(ack === OK ? [...lsb(data, 32), parityOf(lsb(data, 32))] : [])];
const idle = (n = 2) => Array(n).fill(0);
const reset = (n = 56) => Array(n).fill(1);

/* The two lanes: the host changes SWDIO while the clock is low, the target just after the rising edge before its bit's */
function wires(stream, { half = 500e-9, rate = 20e6 } = {}) {
  const clock = [], dio = [];
  let t = 2e-6, level = 1;
  for (const x of stream) {
    const b = x.v ?? x;
    if (b !== level) {
      dio.push([x.v === undefined ? t + half / 2 : t - half + 50e-9, b]);
      level = b;
    }
    clock.push([t + half, 1], [t + 2 * half, 0]);
    t += 2 * half;
  }
  return captureOf(rate, t + 4e-6, [[0, clock], [1, dio]]);
}

const decode = (stream, opts) => swd(wires(stream, opts), { swclk: 0, swdio: 1 })[0];

test("connecting: a line reset, JTAG to SWD, a line reset, IDCODE", () => {
  const row = decode([...reset(), ...lsb(0xe79e, 16), ...reset(), ...idle(), ...read(false, 0, 0x2ba01477)]);
  assert.deepEqual(row.frames.map((f) => f.text), ["line reset", "JTAG to SWD", "line reset", "R DP IDCODE OK 0x2BA01477"]);
  const f = row.frames.at(-1);
  assert.deepEqual(f.fields, { ap: false, read: true, addr: 0, ack: "OK", data: 0x2ba01477, parityOk: true });
  assert.equal(f.hex, "2BA01477");
  assert.equal(f.items.at(-1).value, 0x2ba01477);
});

test("a read and a write, every DP register by name, an AP's by number", () => {
  const row = decode([...idle(), ...write(false, 0, 0x1e), ...idle(), ...write(false, 4, 0x50000000), ...idle(), ...write(false, 8, 0xff),
                      ...idle(), ...read(false, 4, 0xf0000040), ...idle(), ...read(false, 8, 1), ...idle(), ...read(false, 12, 2),
                      ...idle(), ...read(true, 0xc, 0x12345678), ...idle(), ...write(true, 4, 0x20000000)]);
  assert.deepEqual(row.frames.map((f) => f.text), [
    "W DP ABORT OK 0x0000001E", "W DP CTRL/STAT OK 0x50000000", "W DP SELECT OK 0x000000FF", "R DP CTRL/STAT OK 0xF0000040",
    "R DP RESEND OK 0x00000001", "R DP RDBUFF OK 0x00000002", "R AP 0xC OK 0x12345678", "W AP 0x4 OK 0x20000000"]);
});

test("a value with its top bit set stays positive", () => {
  assert.equal(decode([...idle(), ...read(false, 0, 0xffffffff)]).frames[0].fields.data, 0xffffffff);
});

test("WAIT and FAULT have no data, and the next request still reads", () => {
  const row = decode([...idle(), ...read(true, 0, 0, WAIT), ...idle(), ...read(true, 0, 0, FAULT), ...idle(), ...read(false, 0, 5)]);
  assert.deepEqual(row.frames.map((f) => [f.text, f.kind]), [["R AP 0x0 WAIT", "data"], ["R AP 0x0 FAULT", "err"], ["R DP IDCODE OK 0x00000005", "data"]]);
});

test("nobody answers", () => {
  const row = decode([...idle(), ...request(false, true, 0), ...TRN, ...target([1, 1, 1]), ...TRN, ...idle(4)]);
  assert.deepEqual(row.frames.map((f) => [f.text, f.kind]), [["R DP IDCODE no ACK", "err"]]);
});

test("a data parity error", () => {
  const f = decode([...idle(), ...read(false, 0, 0x1234, OK, true)]).frames[0];
  assert.equal(f.text, "R DP IDCODE OK 0x00001234 parity");
  assert.equal(f.fields.parityOk, false);
  assert.equal(f.kind, "err");
});

test("TARGETSEL gets no ACK, and its data still reads", () => {
  const stream = [...idle(), ...request(false, false, 12), ...TRN, 1, 1, 1, ...TRN, ...lsb(0x01002927, 32), parityOf(lsb(0x01002927, 32)), ...idle(), ...read(false, 0, 7)];
  const row = decode(stream);
  assert.deepEqual(row.frames.map((f) => f.text), ["W DP TARGETSEL 0x01002927", "R DP IDCODE OK 0x00000007"]);
});

test("idle clocks and a sequence with a bad parity make no request", () => {
  assert.deepEqual(decode([...idle(40)]).frames, []);
  assert.deepEqual(decode([...idle(4), 1, 0, 0, 0, 0, 1, 0, 1, ...idle(20)]).frames, []);
});

test("a capture that stops in the data says so", () => {
  const stream = [...idle(), ...request(false, true, 0), ...TRN, ...target(OK), ...target(lsb(0x55, 10))];
  const f = decode(stream).frames[0];
  assert.equal(f.text, "R DP IDCODE OK cut off");
  assert.equal(f.kind, "err");
});

test("at 4 samples a bit it still reads, and a thinner clock is flagged", () => {
  const stream = [...idle(), ...read(false, 0, 0x2ba01477)];
  assert.equal(decode(stream, { half: 500e-9, rate: 4e6 }).frames[0].fields.data, 0x2ba01477);
  const cap = wires(stream, { half: 100e-9, rate: 20e6 });
  assert.match(captureNotes(cap, [{ type: "swd", lines: { swclk: 0, swdio: 1 } }], () => "SWCLK")[0].text, /^SWCLK's shortest pulse is 2 samples wide: SWD/);
});

const ALERT = [0x92, 0xf3, 0x09, 0x62, 0x95, 0x2d, 0x85, 0x86, 0xe9, 0xaf, 0xdd, 0xe3, 0xa2, 0x0e, 0xbc, 0x19].flatMap((b) => lsb(b, 8));

test("waking from dormant is named, and its bits make no request", () => {
  const row = decode([...reset(8), ...ALERT, ...idle(4), ...lsb(0x1a, 8), ...reset(), ...idle(8), ...read(false, 0, 0x4c013477)]);
  assert.deepEqual(row.frames.map((f) => f.text), ["wake from dormant: SWD", "line reset", "R DP IDCODE OK 0x4C013477"]);
});

test("the alert with another activation code", () => {
  assert.deepEqual(decode([...reset(8), ...ALERT, ...idle(4), ...lsb(0x50, 8), ...idle(4)]).frames.map((f) => f.text), ["selection alert"]);
});

test("nobody answers, and the host clocks on with the line high: each request is still found", () => {
  /* What Zephyr's bit-bang driver does after a bad ACK: a turnaround, 32 bits and a parity's worth of clocks, the line pulled up */
  const silent = (req) => [...req, ...TRN, 1, 1, 1, ...Array(34).fill(1)];
  const row = decode([...idle(), ...silent(request(false, true, 0)), ...silent(request(false, false, 4)), ...silent(request(false, false, 8)),
                      ...silent(request(true, true, 0xc)), ...idle(4)]);
  assert.deepEqual(row.frames.map((f) => f.text), ["R DP IDCODE no ACK", "W DP CTRL/STAT no ACK", "W DP SELECT no ACK", "R AP 0xC no ACK"]);
});

test("a request with five ones of its own still reads", () => {
  assert.equal(decode([...idle(), ...read(true, 0xc, 3)]).frames[0].text, "R AP 0xC OK 0x00000003");
});
