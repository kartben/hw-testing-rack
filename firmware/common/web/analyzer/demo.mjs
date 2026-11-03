/*
 * A made-up capture to show the page without an analyzer: a UART line at
 * 1 Mbd and its answer, an I²C register read at 400 kHz, an SPI flash ID
 * read at 4 MHz, three WS2812B LEDs.  20 MS/s, 8 channels.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture } from "./capture.mjs";

const RATE = 20e6;

function uart(bytes, baud, t0) {
  const e = [[0, 1]], bit = 1 / baud;
  let t = t0;
  for (const b of bytes) {
    for (const v of [0, ...Array.from({ length: 8 }, (_, i) => (b >> i) & 1), 1]) {
      e.push([t, v]);
      t += bit;
    }
    t += bit * 0.5;
  }
  return { edges: e, end: t };
}

function i2c(addr, reg, data, rate, t0) {
  const q = 1 / rate / 4, sda = [[0, 1]], scl = [[0, 1]];
  let t = t0;
  const bit = (v) => {
    sda.push([t, v]);
    t += q;
    scl.push([t, 1]);
    t += 2 * q;
    scl.push([t, 0]);
    t += q;
  };
  const start = () => {
    sda.push([t, 1]);
    scl.push([t, 1]);
    t += q;
    sda.push([t, 0]);
    t += q;
    scl.push([t, 0]);
    t += q;
  };
  const byte = (b, ack) => {
    for (let i = 7; i >= 0; i--) {
      bit((b >> i) & 1);
    }
    bit(ack);
  };
  start();
  byte(addr << 1, 0);
  byte(reg, 0);
  start();
  byte((addr << 1) | 1, 0);
  data.forEach((d, i) => byte(d, i === data.length - 1 ? 1 : 0));
  sda.push([t, 0]);
  t += q;
  scl.push([t, 1]);
  t += q;
  sda.push([t, 1]);
  t += q;
  return { sda, scl, end: t };
}

function spi(mosi, miso, rate, t0) {
  const h = 1 / rate / 2, cs = [[0, 1]], sck = [[0, 0]], mo = [[0, 0]], mi = [[0, 1]];
  let t = t0;
  cs.push([t, 0]);
  t += 4 * h;
  mosi.forEach((b, j) => {
    for (let i = 7; i >= 0; i--) {
      mo.push([t, (b >> i) & 1]);
      mi.push([t, (miso[j] >> i) & 1]);
      t += h;
      sck.push([t, 1]);
      t += h;
      sck.push([t, 0]);
    }
    t += 2 * h;
  });
  t += 2 * h;
  cs.push([t, 1]);
  return { cs, sck, mo, mi, end: t };
}

/* WS2812B: 1.25 µs a bit, high 0.4 µs for a 0, 0.8 µs for a 1; green, red, blue, MSB first */
function ws2812(colors, t0) {
  const e = [[0, 0]];
  let t = t0;
  for (const [r, g, b] of colors) {
    for (const byte of [g, r, b]) {
      for (let i = 7; i >= 0; i--) {
        const hi = (byte >> i) & 1 ? 0.8e-6 : 0.4e-6;
        e.push([t, 1], [t + hi, 0]);
        t += 1.25e-6;
      }
    }
  }
  return { edges: e, end: t };
}

/* Channels' edges ([seconds, level]) to samples, bit k = channel k */
function rasterize(lanes, count, pre) {
  const samples = new Uint8Array(count);
  lanes.forEach((edges, k) => {
    let j = 0, lv = edges[0][1];
    for (let i = 0; i < count; i++) {
      const t = (i - pre) / RATE;
      while (j < edges.length && edges[j][0] <= t) {
        lv = edges[j++][1];
      }
      samples[i] |= lv << k;
    }
  });
  return samples;
}

export const DEMO_NAMES = ["UART TX", "UART RX", "I²C SDA", "I²C SCL", "SPI CS", "SPI SCK", "SPI MOSI",
                           "WS2812B DIN"];

export function demoCapture() {
  const text = [..."Hello from B3.2\r\n"].map((c) => c.charCodeAt(0));
  const u = uart(text, 1e6, 0);
  const u2 = uart([..."ack\r\n"].map((c) => c.charCodeAt(0)), 1e6, u.end + 8e-6);
  const i = i2c(0x48, 0x00, [0x1a, 0x60], 400e3, u2.end + 25e-6);
  const s = spi([0x9f, 0, 0, 0], [0xff, 0xef, 0x40, 0x18], 4e6, i.end + 25e-6);
  const w = ws2812([[255, 128, 0], [0, 64, 255], [24, 200, 40]], s.end + 25e-6);
  const pre = Math.round(20e-6 * RATE), post = Math.round((w.end + 30e-6) * RATE);
  const samples = rasterize([u.edges, u2.edges, i.sda, i.scl, s.cs, s.sck, s.mo, w.edges], pre + post, pre);
  return new Capture({ channels: [0, 1, 2, 3, 4, 5, 6, 7], rate: RATE, pre, post, samples });
}
