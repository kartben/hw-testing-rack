/*
 * The analyzer's side of the wire format (protocol.mjs), for the tests: it
 * reads framed requests, answers ID and capture, cancels a capture on any
 * byte, and sends its replies in chunks of a set size.  trigger() ends the
 * capture it waits on, with the samples a function gives per sample index
 * as a word of the 24 channels.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

export class FakeAnalyzer {
  constructor({ board = "PICO_2", version = "6_0", maxRate = 100_000_000, blastRate = 200_000_000,
                buffer = 393_216, channels = 24, chunk = 61 } = {}) {
    Object.assign(this, { board, version, maxRate, blastRate, buffer, channels, chunk });
    this.out = [];
    this.waiters = [];
    this.inbox = [];
    this.request = null;   /* the capture waiting for its trigger */
    this.cancelled = 0;
    this.refuse = false;
  }

  transport() {
    return {
      write: async (bytes) => this.#input(bytes),
      read: () => new Promise((resolve) => {
        if (this.out.length) {
          resolve(this.out.shift());
        } else {
          this.waiters.push(resolve);
        }
      }),
    };
  }

  #send(bytes) {
    for (let i = 0; i < bytes.length; i += this.chunk) {
      const piece = bytes.slice(i, i + this.chunk);
      const w = this.waiters.shift();
      if (w) {
        w(piece);
      } else {
        this.out.push(piece);
      }
    }
  }

  #line(text) {
    this.#send(new TextEncoder().encode(`${text}\n`));
  }

  #input(bytes) {
    for (const b of bytes) {
      if (this.request) {             /* waiting for the trigger: any byte cancels */
        this.request = null;
        this.cancelled++;
        this.inbox = [];
        continue;
      }
      this.inbox.push(b);
      const n = this.inbox.length;
      if (n === 1 && b !== 0x55 || n === 2 && b !== 0xaa) {
        this.inbox = [];
      } else if (n > 3 && this.inbox[n - 2] === 0xaa && b === 0x55) {
        this.#message(this.inbox.slice(2, -2));
        this.inbox = [];
      }
    }
  }

  #message(escaped) {
    const m = [];
    for (let i = 0; i < escaped.length; i++) {
      m.push(escaped[i] === 0xf0 ? escaped[++i] ^ 0xf0 : escaped[i]);
    }
    if (m[0] === 0) {
      this.#line(`LOGIC_ANALYZER_${this.board}_V${this.version}`);
      this.#line(`FREQ:${this.maxRate}`);
      this.#line(`BLASTFREQ:${this.blastRate}`);
      this.#line(`BUFFER:${this.buffer}`);
      this.#line(`CHANNELS:${this.channels}`);
    } else if (m[0] === 1) {
      const v = new DataView(Uint8Array.from(m.slice(1)).buffer);
      const req = {
        type: v.getUint8(0), trigger: v.getUint8(1), inverted: v.getUint8(2), value: v.getUint16(4, true),
        channels: m.slice(1 + 6, 1 + 6 + v.getUint8(30)), rate: v.getUint32(32, true),
        pre: v.getUint32(36, true), post: v.getUint32(40, true), loops: v.getUint8(44),
        measure: v.getUint8(45), mode: v.getUint8(46), size: m.length - 1,
      };
      this.last = req;
      if (this.refuse) {
        this.#line("CAPTURE_ERROR");
      } else {
        this.request = req;
        this.#line("CAPTURE_STARTED");
      }
    } else if (m[0] === 4) {
      this.#line("RESTARTING_BOOTLOADER");
    } else {
      this.#line("ERR_UNKNOWN_MSG");
    }
  }

  /* The trigger: send pre + post samples, word(i) the 24 channels at sample i; stamps for bursts */
  trigger(word, stamps = []) {
    const r = this.request;
    this.request = null;
    const n = r.pre + r.post, bps = 1 << r.mode;
    const out = new Uint8Array(4 + n * bps + 1 + (stamps.length > 1 ? stamps.length * 4 : 0));
    const v = new DataView(out.buffer);
    v.setUint32(0, n, true);
    for (let i = 0; i < n; i++) {
      const w = word(i);
      let packed = 0;
      r.channels.forEach((c, k) => {
        packed |= ((w >>> c) & 1) << k;
      });
      for (let b = 0; b < bps; b++) {
        out[4 + i * bps + b] = (packed >>> (8 * b)) & 0xff;
      }
    }
    out[4 + n * bps] = stamps.length;
    if (stamps.length > 1) {
      stamps.forEach((s, i) => v.setUint32(4 + n * bps + 1 + 4 * i, s, true));
    }
    this.#send(out);
  }
}
