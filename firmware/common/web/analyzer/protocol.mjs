/*
 * gusmanb's LogicAnalyzer firmware (v6.0) as seen from the host: requests,
 * replies and the capture's data, written from the wire format.  The
 * transport is anything with write(bytes) and read() -> bytes or null: Web
 * Serial on a PC (serial.mjs), the bay node's WebSocket relay.
 *
 *   request   0x55 0xAA, the command and its data, 0xAA 0x55; inside, 0xAA,
 *             0x55 and 0xF0 go as 0xF0 then the byte XOR 0xF0
 *   0  ID     -> "LOGIC_ANALYZER_<board>_V<version>", "FREQ:<Hz>",
 *                "BLASTFREQ:<Hz>", "BUFFER:<bytes>", "CHANNELS:<n>", a line each
 *   1  capture (48 bytes, below) -> "CAPTURE_STARTED" or "CAPTURE_ERROR", then
 *             when it ends: the sample count (u32), the samples (1, 2 or 4
 *             bytes each, bit i = the i-th channel asked for), the burst
 *             stamps count (u8) and, if more than 1, the stamps (u32 each)
 *   4  reboot into the USB bootloader -> "RESTARTING_BOOTLOADER"
 *   any byte while it waits for the trigger: the capture is cancelled
 *
 * SPDX-License-Identifier: Apache-2.0
 */

export const CMD = { ID: 0, CAPTURE: 1, BOOTLOADER: 4 };
/* Edge, pattern (two kinds, GPIO0 wired to GPIO1), blast: no samples before the trigger */
export const TRIGGER = { EDGE: 0, COMPLEX: 1, FAST: 2, BLAST: 3 };
export const MAX_CHANNELS = 24;

const START = [0x55, 0xaa];
const STOP = [0xaa, 0x55];
const ESC = 0xf0;
const REQUEST_SIZE = 48;

/* A request as it goes on the wire */
export function frame(cmd, data = new Uint8Array(0)) {
  const out = [...START];
  for (const b of [cmd, ...data]) {
    if (b === 0xaa || b === 0x55 || b === ESC) {
      out.push(ESC, b ^ ESC);
    } else {
      out.push(b);
    }
  }
  out.push(...STOP);
  return Uint8Array.from(out);
}

/* Bytes per sample: the highest channel asked for sets it */
export function bytesPerSample(channels) {
  const hi = Math.max(...channels);
  return hi < 8 ? 1 : hi < 16 ? 2 : 4;
}

/* How many samples the analyzer holds with these channels */
export function maxSamples(bufferBytes, channels) {
  return Math.floor(bufferBytes / bytesPerSample(channels));
}

/*
 * The capture request: channels are 0-based (CH1 is 0), rate in samples a
 * second, pre and post sample counts around the trigger.  trigger: {type,
 * channel, inverted} for an edge (inverted: falling), {type, channel, count,
 * value} for a pattern.  info (from identify()) bounds what is asked.
 */
export function captureRequest({ channels, rate, pre, post, trigger = {}, loops = 0, measure = false },
                               info) {
  const type = trigger.type ?? TRIGGER.EDGE;
  if (!channels.length || channels.some((c) => !Number.isInteger(c) || c < 0 || c >= MAX_CHANNELS)) {
    throw new Error(`channels: 1 to ${MAX_CHANNELS}, numbered from 0`);
  }
  if (info && channels.length > info.channels) {
    throw new Error(`this analyzer has ${info.channels} channels`);
  }
  if (!(rate > 0) || (info && rate > (type === TRIGGER.BLAST ? info.blastRate : info.maxRate))) {
    throw new Error(`sample rate: up to ${info?.maxRate ?? "?"} S/s`);
  }
  if (info && pre + post > maxSamples(info.buffer, channels)) {
    throw new Error(`${pre + post} samples: ${maxSamples(info.buffer, channels)} at most with these channels`);
  }
  const b = new ArrayBuffer(REQUEST_SIZE);
  const v = new DataView(b);
  v.setUint8(0, type);
  v.setUint8(1, trigger.channel ?? 0);
  v.setUint8(2, type === TRIGGER.EDGE || type === TRIGGER.BLAST ? (trigger.inverted ? 1 : 0)
                                                                : (trigger.count ?? 1));
  v.setUint16(4, trigger.value ?? 0, true);
  channels.forEach((c, i) => v.setUint8(6 + i, c));
  v.setUint8(30, channels.length);
  v.setUint32(32, rate, true);
  v.setUint32(36, pre, true);
  v.setUint32(40, post, true);
  v.setUint8(44, loops);
  v.setUint8(45, measure ? 1 : 0);
  v.setUint8(46, Math.log2(bytesPerSample(channels)));
  return new Uint8Array(b);
}

/* The ID reply: "LOGIC_ANALYZER_PICO_2_V6_0" and its four values */
export function parseId(lines) {
  const m = /^LOGIC_ANALYZER_(.+)_V(\d+)_(\d+)$/.exec(lines[0] ?? "");
  if (!m) {
    throw new Error(`not gusmanb's LogicAnalyzer: "${lines[0] ?? ""}"`);
  }
  const val = (key) => {
    const line = lines.find((l) => l.startsWith(`${key}:`));
    if (!line) {
      throw new Error(`the analyzer did not say its ${key}`);
    }
    return Number(line.slice(key.length + 1));
  };
  return {
    board: m[1], version: `${m[2]}.${m[3]}`,
    maxRate: val("FREQ"), blastRate: val("BLASTFREQ"), buffer: val("BUFFER"), channels: val("CHANNELS"),
  };
}

const aborted = (signal) => new Promise((_, reject) => {
  const fail = () => reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
  if (signal.aborted) {
    fail();
  }
  signal.addEventListener("abort", fail, { once: true });
});

/* Bytes as they come, read by lines or by counts; a wait can be given up (signal) */
export class ByteReader {
  constructor(read) {
    this.read = read;
    this.buf = new Uint8Array(0);
    this.pending = null;   /* a read that outlived a given-up wait: the next one takes its bytes */
  }

  async #more(signal) {
    this.pending ??= this.read();
    const chunk = await (signal ? Promise.race([this.pending, aborted(signal)]) : this.pending);
    this.pending = null;
    if (chunk == null) {
      throw new Error("the analyzer went away");
    }
    const b = new Uint8Array(this.buf.length + chunk.length);
    b.set(this.buf);
    b.set(chunk, this.buf.length);
    this.buf = b;
  }

  async line(signal) {
    let i;
    while ((i = this.buf.indexOf(0x0a)) < 0) {
      await this.#more(signal);
    }
    const text = new TextDecoder().decode(this.buf.subarray(0, i)).replace(/\r$/, "");
    this.buf = this.buf.slice(i + 1);
    return text;
  }

  async bytes(n, { signal, progress } = {}) {
    while (this.buf.length < n) {
      await this.#more(signal);
      progress?.(Math.min(this.buf.length, n), n);
    }
    const out = this.buf.slice(0, n);
    this.buf = this.buf.slice(n);
    return out;
  }

  /* What came and was not read goes */
  drop() {
    this.buf = new Uint8Array(0);
  }
}

/* One analyzer on one transport, one request at a time */
export class Analyzer {
  constructor(transport) {
    this.transport = transport;
    this.reader = new ByteReader(() => transport.read());
    this.info = null;
  }

  async identify() {
    this.reader.drop();
    await this.transport.write(frame(CMD.ID));
    const lines = [await this.reader.line()];
    if (!lines[0].startsWith("LOGIC_ANALYZER_")) {
      throw new Error(`not gusmanb's LogicAnalyzer: "${lines[0]}"`);
    }
    for (let i = 0; i < 4; i++) {
      lines.push(await this.reader.line());
    }
    this.info = parseId(lines);
    return this.info;
  }

  /*
   * Ask for a capture, wait for its trigger and its data.  onStarted() once
   * the analyzer waits for the trigger; onData(got, total) as the samples
   * come; signal aborted while it waits: the capture is cancelled.  Resolves
   * to {channels, rate, pre, post, samples, stamps}: samples a Uint8Array,
   * Uint16Array or Uint32Array of words, bit i = channels[i].
   */
  async capture(settings, { onStarted, onData, signal } = {}) {
    const req = captureRequest(settings, this.info);
    this.reader.drop();
    await this.transport.write(frame(CMD.CAPTURE, req));
    const answer = await this.reader.line();
    if (answer !== "CAPTURE_STARTED") {
      throw new Error(answer === "CAPTURE_ERROR" ? "the analyzer refused these settings" : `unexpected "${answer}"`);
    }
    onStarted?.();
    let head;
    try {
      head = await this.reader.bytes(4, { signal });
    } catch (e) {
      if (signal?.aborted) {
        await this.cancel();
      }
      throw e;
    }
    const count = new DataView(head.buffer).getUint32(0, true);
    const bps = bytesPerSample(settings.channels);
    const raw = await this.reader.bytes(count * bps, { progress: onData });
    const nStamps = (await this.reader.bytes(1))[0];
    const stamps = nStamps > 1 ? new Uint32Array((await this.reader.bytes(nStamps * 4)).buffer) : new Uint32Array(0);
    const samples = bps === 1 ? raw : bps === 2 ? new Uint16Array(raw.buffer, 0, count)
                                                : new Uint32Array(raw.buffer, 0, count);
    return { channels: [...settings.channels], rate: settings.rate, pre: settings.pre, post: settings.post,
             samples, stamps };
  }

  /* While it waits for its trigger: any byte stops it, and it says nothing */
  async cancel() {
    await this.transport.write(Uint8Array.of(0));
    this.reader.drop();
  }

  async rebootToBootloader() {
    await this.transport.write(frame(CMD.BOOTLOADER));
  }
}
