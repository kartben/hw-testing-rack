/*
 * An analyzer on this computer's USB, through Web Serial (Chrome and Edge on
 * a desktop): gusmanb's firmware is a CDC ACM port, 1209:3020.  The
 * transport protocol.mjs drives: write(bytes), read() -> bytes or null.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

export const USB_ID = { usbVendorId: 0x1209, usbProductId: 0x3020 };

export const serialSupported = () => typeof navigator !== "undefined" && "serial" in navigator;

/* Ask the user for the port (a click must start this), open it */
export async function openSerial(port) {
  port ??= await navigator.serial.requestPort({ filters: [USB_ID] });
  /* The firmware ignores the baud rate; its USB stack waits for DTR */
  await port.open({ baudRate: 115200, bufferSize: 1 << 20 });
  await port.setSignals({ dataTerminalReady: true, requestToSend: true });
  const reader = port.readable.getReader();
  const writer = port.writable.getWriter();
  return {
    port,
    name: "USB",
    async write(bytes) {
      await writer.write(bytes);
    },
    async read() {
      const { value, done } = await reader.read();
      return done ? null : value;
    },
    async close() {
      await reader.cancel().catch(() => {});
      reader.releaseLock();
      writer.releaseLock();
      await port.close().catch(() => {});
    },
  };
}

/* A port this page was given before, if it is plugged in */
export async function knownSerial() {
  const ports = await navigator.serial.getPorts();
  return ports.find((p) => {
    const i = p.getInfo();
    return i.usbVendorId === USB_ID.usbVendorId && i.usbProductId === USB_ID.usbProductId;
  }) ?? null;
}
