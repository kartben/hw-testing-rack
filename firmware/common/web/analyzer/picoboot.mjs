/*
 * An RP2350 in its USB bootloader (2e8a:000f) through WebUSB: what picotool
 * load -x does for an image in SRAM, as the bay node's loader does
 * (bay-node/src/coproc.c).  On the PICOBOOT interface (vendor class, a bulk
 * endpoint each way, RP2350 datasheet 5.6): an interface reset, then
 * EXCLUSIVE_ACCESS, WRITE in 4 KB chunks, REBOOT2 into the RAM image.  Each
 * command is 32 bytes OUT, its data OUT, then an empty IN as the
 * bootloader's acknowledgment.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { SRAM } from "./uf2.mjs";

export const BOOTROM_ID = { vendorId: 0x2e8a, productId: 0x000f };
export const usbSupported = () => typeof navigator !== "undefined" && "usb" in navigator;

const MAGIC = 0x431fd10b;
const IF_RESET = 0x41;
const PC_EXCLUSIVE_ACCESS = 0x01;
const PC_WRITE = 0x05;
const PC_REBOOT2 = 0x0a;
const REBOOT2_RAM_IMAGE = 0x3;
const CHUNK = 4096;

/* Open the bootloader (device, or ask for one: a click must start this) */
export async function openBootrom(device) {
  device ??= await navigator.usb.requestDevice({ filters: [BOOTROM_ID] });
  await device.open();
  if (device.configuration === null) {
    await device.selectConfiguration(1);
  }
  const iface = device.configuration.interfaces.find((i) => i.alternates.some((a) => a.interfaceClass === 0xff));
  if (!iface) {
    throw new Error("no PICOBOOT interface: is it an RP2350 in its bootloader?");
  }
  const alt = iface.alternates.find((a) => a.interfaceClass === 0xff);
  await device.claimInterface(iface.interfaceNumber);
  const ep = (dir) => alt.endpoints.find((e) => e.direction === dir && e.type === "bulk")?.endpointNumber;
  const boot = { device, iface: iface.interfaceNumber, out: ep("out"), in: ep("in"), token: 0 };
  if (boot.out === undefined || boot.in === undefined) {
    throw new Error("the PICOBOOT interface has no bulk endpoints");
  }
  await device.controlTransferOut({ requestType: "vendor", recipient: "interface", request: IF_RESET,
                                    value: 0, index: boot.iface });
  return boot;
}

function ok(r, what) {
  if (r.status !== "ok") {
    throw new Error(r.status === "stall" ? `the bootloader refused ${what} (stall)` : `${what}: ${r.status}`);
  }
}

async function command(boot, id, args, data) {
  const c = new Uint8Array(32), v = new DataView(c.buffer);
  v.setUint32(0, MAGIC, true);
  v.setUint32(4, ++boot.token, true);
  c[8] = id;
  c[9] = args.byteLength;
  v.setUint32(12, data?.length ?? 0, true);
  c.set(new Uint8Array(args.buffer, args.byteOffset, args.byteLength), 16);
  const name = { [PC_EXCLUSIVE_ACCESS]: "EXCLUSIVE_ACCESS", [PC_WRITE]: "a WRITE", [PC_REBOOT2]: "REBOOT2" }[id];
  ok(await boot.device.transferOut(boot.out, c), name);
  if (data) {
    ok(await boot.device.transferOut(boot.out, data), name);
  }
  const r = await boot.device.transferIn(boot.in, 64);
  ok(r, name);
  if (r.data.byteLength !== 0) {
    throw new Error(`the bootloader answered ${name} with data`);
  }
}

/*
 * Load {addr, body} (uf2RamImage()) into SRAM and start it; onProgress(sent,
 * total).  The device then leaves the bus and comes back as what it runs.
 */
export async function loadRam(boot, { addr, body }, onProgress) {
  await command(boot, PC_EXCLUSIVE_ACCESS, Uint8Array.of(1));
  for (let off = 0; off < body.length; off += CHUNK) {
    const chunk = body.subarray(off, off + CHUNK);
    await command(boot, PC_WRITE, Uint32Array.of(addr + off, chunk.length), chunk);
    onProgress?.(off + chunk.length, body.length);
  }
  /* Run what is in SRAM from addr to its end (picotool's region), 500 ms from now */
  await command(boot, PC_REBOOT2, Uint32Array.of(REBOOT2_RAM_IMAGE, 500, addr, SRAM[1] - addr));
  await boot.device.close().catch(() => {});
}
