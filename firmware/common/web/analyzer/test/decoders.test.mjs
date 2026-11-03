/*
 * decoders.mjs and vcd.mjs on the demo capture (demo.mjs: UART, I²C, SPI,
 * WS2812B made up) and on made-up faults.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Capture } from "../capture.mjs";
import { i2c, spi, uart, ws2812 } from "../decoders.mjs";
import { demoCapture } from "../demo.mjs";
import { toVcd } from "../vcd.mjs";

const demo = demoCapture();
const texts = (rows, r = 0) => rows[r].items.map((x) => x.text);

/* One channel from [seconds, level] edges, sampled at rate */
function lane(edges, rate, seconds) {
  const n = Math.round(seconds * rate), s = new Uint8Array(n);
  let j = 0, lv = edges[0][1];
  for (let i = 0; i < n; i++) {
    while (j < edges.length && edges[j][0] <= i / rate) {
      lv = edges[j++][1];
    }
    s[i] = lv;
  }
  return new Capture({ channels: [0], rate, pre: 0, post: n, samples: s });
}

test("UART: the demo's text, then its answer", () => {
  assert.equal(texts(uart(demo, { k: 0, baud: 1e6 })).join(""), "Hello from B3.2\\r\\n");
  assert.equal(texts(uart(demo, { k: 1, baud: 1e6 })).join(""), "ack\\r\\n");
  const first = uart(demo, { k: 0, baud: 1e6 })[0].items[0];
  assert.ok(Math.abs(first.t0) < 1e-7, "the trigger is the first start bit");
  assert.ok(Math.abs(first.t1 - first.t0 - 10e-6) < 1e-7, "10 bits at 1 Mbd");
  assert.throws(() => uart(demo, { k: 0, baud: 10e6 }), /MS\/s at least/);
});

test("UART: a stop bit that is not high, a parity error", () => {
  const bit = 1e-5;   /* 100 kBd */
  /* 0x55 with its stop bit low, then 0x41 with even parity right, then wrong */
  const frame = (t, b, extra) => [0, ...Array.from({ length: 8 }, (_, i) => (b >> i) & 1), ...extra]
    .map((v, i) => [t + i * bit, v]);
  const c1 = lane([[0, 1], ...frame(1e-5, 0x55, [0]), [1.2e-4, 1]], 1e6, 3e-4);
  assert.deepEqual(texts(uart(c1, { k: 0, baud: 1e5 })), ["U framing"]);
  const c2 = lane([[0, 1], ...frame(1e-5, 0x41, [0, 1]), ...frame(2e-4, 0x41, [1, 1]), [3.2e-4, 1]], 1e6, 4e-4);
  assert.deepEqual(texts(uart(c2, { k: 0, baud: 1e5, parity: "even" })), ["A", "A parity"]);
});

test("I²C: a register read with a repeated start", () => {
  assert.deepEqual(texts(i2c(demo, { sda: 2, scl: 3 })),
                   ["S", "W 0x48 ACK", "0x00 ACK", "Sr", "R 0x48 ACK", "0x1A ACK", "0x60 NACK", "P"]);
  const kinds = i2c(demo, { sda: 2, scl: 3 })[0].items.map((x) => x.kind);
  assert.deepEqual(kinds, ["ctl", "addr", "data", "ctl", "addr", "data", "data", "ctl"]);
});

test("SPI: a flash ID read, MOSI (no MISO in the demo)", () => {
  const rows = spi(demo, { cs: 4, sck: 5, mosi: 6 });
  assert.equal(rows.length, 1);
  assert.deepEqual(texts(rows), ["0x9F", "0x00", "0x00", "0x00"]);
  /* MISO on the MOSI lane: two rows, the same words */
  assert.deepEqual(texts(spi(demo, { cs: 4, sck: 5, mosi: 6, miso: 6 }), 1), ["0x9F", "0x00", "0x00", "0x00"]);
  /* Sampled on the other edge: the bits shift */
  assert.notDeepEqual(texts(spi(demo, { cs: 4, sck: 5, mosi: 6, mode: 1 })), ["0x9F", "0x00", "0x00", "0x00"]);
});

test("WS2812B: three LEDs in G R B, then the reset", () => {
  assert.deepEqual(texts(ws2812(demo, { k: 7 })),
                   ["LED 1 · G 80 R FF B 00", "LED 2 · G 40 R 00 B FF", "LED 3 · G C8 R 18 B 28", "reset"]);
  const rows = ws2812(demo, { k: 7 });
  assert.equal(rows[0].items[3].kind, "ctl");
  /* A frame cut short: its bits marked, not a LED */
  const pulses = Array.from({ length: 10 }, (_, i) => [[i * 1.25e-6, 1], [i * 1.25e-6 + 0.8e-6, 0]]).flat();
  const short = lane([[0, 0], ...pulses.map(([t, v]) => [t + 1e-6, v])], 20e6, 80e-6);
  assert.deepEqual(texts(ws2812(short, { k: 0 })), ["10 bits", "reset"]);
});

test("VCD: the header, then every change of every channel", () => {
  const vcd = toVcd(demo, ["TX", "RX", "SDA", "SCL", "CS", "SCK", "MOSI", "DIN"], { date: new Date(0) });
  assert.match(vcd, /\$timescale 1 ns \$end/);
  assert.match(vcd, /\$var wire 1 ! TX \$end/);
  assert.match(vcd, /trigger at sample 400/);
  /* Read it back: every channel's changes, at 50 ns a sample */
  const changes = new Map();
  let t = 0;
  for (const line of vcd.split("\n").slice(vcd.split("\n").indexOf("$end") + 1)) {
    if (line.startsWith("#")) {
      t = Number(line.slice(1));
    } else if (line) {
      const k = line.charCodeAt(1) - 33;
      changes.set(k, [...(changes.get(k) ?? []), t / 50]);
    }
  }
  demo.channels.forEach((_, k) => assert.deepEqual(changes.get(k) ?? [], [...demo.edges(k).subarray(1)]));
});
