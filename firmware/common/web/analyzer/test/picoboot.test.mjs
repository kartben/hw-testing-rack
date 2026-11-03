/*
 * uf2.mjs and picoboot.mjs: a no_flash UF2 read, then loaded into an RP2350
 * bootloader that a fake WebUSB device stands in for.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { loadRam, openBootrom } from "../picoboot.mjs";
import { uf2RamImage } from "../uf2.mjs";

const ARM = 0xe48bff59, ABS = 0xe48bff57, RP2040 = 0xe48bff56, FAM = 0x2000;

/* A UF2 file from [address, data, family, flags] blocks */
function uf2(blocks) {
  const out = new Uint8Array(512 * blocks.length), v = new DataView(out.buffer);
  blocks.forEach(([addr, data, family, flags], i) => {
    [0x0a324655, 0x9e5d5157, flags, addr, data.length, i, blocks.length, family]
      .forEach((x, j) => v.setUint32(512 * i + 4 * j, x, true));
    out.set(data, 512 * i + 32);
    v.setUint32(512 * i + 508, 0x0ab16f30, true);
  });
  return out;
}

/* The bootloader's PICOBOOT interface as WebUSB shows it, and what it was told */
class FakeBootrom {
  constructor() {
    this.sram = new Uint8Array(0x82000);
    this.log = [];
    this.configuration = null;
    this.stallWrite = false;
  }

  async open() {}
  async selectConfiguration() {
    this.configuration = { interfaces: [
      { interfaceNumber: 0, alternates: [{ interfaceClass: 0x08, endpoints: [] }] },
      { interfaceNumber: 1, alternates: [{ interfaceClass: 0xff, endpoints: [
        { endpointNumber: 3, direction: "out", type: "bulk" }, { endpointNumber: 4, direction: "in", type: "bulk" }] }] },
    ] };
  }
  async claimInterface(n) {
    this.log.push(["claim", n]);
  }
  async controlTransferOut(setup) {
    this.log.push(["reset", setup.request, setup.index]);
    return { status: "ok" };
  }
  async transferOut(ep, data) {
    assert.equal(ep, 3);
    if (this.data) {
      const { addr } = this.data;
      if (this.stallWrite) {
        return { status: "stall" };
      }
      this.sram.set(data, addr - 0x20000000);
      this.data = null;
      return { status: "ok", bytesWritten: data.length };
    }
    const v = new DataView(data.buffer, data.byteOffset, 32);
    assert.equal(v.getUint32(0, true), 0x431fd10b);
    const id = data[8], args = [0, 1, 2, 3].map((i) => v.getUint32(16 + 4 * i, true));
    this.log.push(["cmd", id, data[9], v.getUint32(12, true), ...args.slice(0, data[9] / 4 || 1)]);
    if (id === 0x05) {
      this.data = { addr: args[0] };
    }
    return { status: "ok", bytesWritten: 32 };
  }
  async transferIn(ep) {
    assert.equal(ep, 4);
    return { status: "ok", data: new DataView(new ArrayBuffer(0)) };
  }
  async close() {
    this.log.push(["close"]);
  }
}

test("a no_flash UF2: its SRAM image; flash builds and other chips refused", () => {
  const a = Uint8Array.from({ length: 256 }, (_, i) => i), b = a.map((x) => 255 - x);
  assert.deepEqual(uf2RamImage(uf2([[0x10ffff00, new Uint8Array(256), ABS, FAM], [0x20000000, a, ARM, FAM],
                                    [0x20000200, b, ARM, FAM]])),
                   { addr: 0x20000000, body: Uint8Array.from([...a, ...new Uint8Array(256), ...b]) });
  for (const [bad, why] of [[uf2([[0x10000000, a, ARM, FAM]]), /no_flash/], [uf2([[0x20000000, a, RP2040, FAM]]), /RP2350 Arm/],
                            [new Uint8Array(100), /not a UF2/]]) {
    assert.throws(() => uf2RamImage(bad), why);
  }
});

test("the load: reset, EXCLUSIVE_ACCESS, WRITE in 4 KB chunks, REBOOT2 into the RAM image", async () => {
  const body = Uint8Array.from({ length: 10000 }, (_, i) => (i * 7) & 255);
  const dev = new FakeBootrom(), seen = [];
  const boot = await openBootrom(dev);
  await loadRam(boot, { addr: 0x20000000, body }, (sent, total) => seen.push([sent, total]));
  assert.deepEqual(dev.sram.subarray(0, body.length), body);
  const cmds = dev.log.filter((x) => x[0] === "cmd");
  assert.deepEqual(dev.log[0], ["claim", 1]);
  assert.deepEqual(dev.log[1], ["reset", 0x41, 1]);
  assert.deepEqual(cmds[0].slice(0, 4), ["cmd", 0x01, 1, 0]);
  assert.deepEqual(cmds.slice(1, 4).map((c) => c.slice(1)),
                   [[0x05, 8, 4096, 0x20000000, 4096], [0x05, 8, 4096, 0x20001000, 4096], [0x05, 8, 1808, 0x20002000, 1808]]);
  assert.deepEqual(cmds[4].slice(1), [0x0a, 16, 0, 3, 500, 0x20000000, 0x82000]);
  assert.deepEqual(seen.at(-1), [10000, 10000]);
  assert.deepEqual(dev.log.at(-1), ["close"]);
});

test("a stalled WRITE fails the load before any REBOOT2", async () => {
  const dev = new FakeBootrom();
  dev.stallWrite = true;
  const boot = await openBootrom(dev);
  await assert.rejects(loadRam(boot, { addr: 0x20000000, body: new Uint8Array(100) }), /refused a WRITE \(stall\)/);
  assert.ok(!dev.log.some((x) => x[1] === 0x0a));
});
