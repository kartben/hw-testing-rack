/*
 * A UF2 file of an RP2350 build that runs from SRAM (pico_set_binary_type
 * no_flash): its address and its bytes, as bayctl coproc load reads it.
 * RP2350 Arm blocks only, all in SRAM; picotool's RP2350-E10 block (family
 * "absolute", at the top of flash) is left out; gaps between blocks are
 * zeros.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

const MAGIC = [0x0a324655, 0x9e5d5157, 0x0ab16f30];
export const FAMILY_RP2350_ARM_S = 0xe48bff59;
const FAMILY_ABSOLUTE = 0xe48bff57;
export const SRAM = [0x20000000, 0x20082000];

export function uf2RamImage(bytes) {
  if (bytes.length < 512 || bytes.length % 512) {
    throw new Error("not a UF2 file");
  }
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), chunks = [];
  for (let off = 0; off < bytes.length; off += 512) {
    const [m0, m1, flags, addr, n] = [0, 4, 8, 12, 16].map((o) => v.getUint32(off + o, true));
    const family = v.getUint32(off + 28, true);
    if (m0 !== MAGIC[0] || m1 !== MAGIC[1] || v.getUint32(off + 508, true) !== MAGIC[2] || n > 476) {
      throw new Error(`not a UF2 file (block ${off / 512})`);
    }
    if (flags & 0x1 || (flags & 0x2000 && family === FAMILY_ABSOLUTE)) {
      continue;
    }
    if (!(flags & 0x2000) || family !== FAMILY_RP2350_ARM_S) {
      throw new Error(`not an RP2350 Arm UF2 (family 0x${family.toString(16).padStart(8, "0")})`);
    }
    if (addr < SRAM[0] || addr + n > SRAM[1]) {
      throw new Error(`block at 0x${addr.toString(16)}: not in the RP2350's SRAM (a no_flash build is needed)`);
    }
    chunks.push([addr, bytes.subarray(off + 32, off + 32 + n)]);
  }
  if (!chunks.length) {
    throw new Error("no data in this UF2");
  }
  const start = Math.min(...chunks.map(([a]) => a));
  const out = new Uint8Array(Math.max(...chunks.map(([a, c]) => a + c.length)) - start);
  for (const [a, c] of chunks) {
    out.set(c, a - start);
  }
  return { addr: start, body: out };
}
