/*
 * The analyzer on a DATA x4 bay, through the node's relay
 * (bay-node/src/analyzer.c): a WebSocket, /analyzer/ws, that carries the
 * analyzer's own bytes both ways.  It opens with a console ticket (POST
 * /api/console/ticket: the Console right); one page holds it at a time.  The
 * same transport as serial.mjs: write(bytes), read() -> bytes, or null once
 * it is closed.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* origin: the node's, "http://bay-b3.local" (this page's by default) */
export async function openRelay(origin = location.origin) {
  const r = await fetch(`${origin}/api/console/ticket`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
  const doc = await r.json().catch(() => ({}));
  if (!r.ok || !doc.ticket) {
    throw new Error(doc.error ?? `no console ticket (${r.status})`);
  }
  const ws = new WebSocket(`${origin.replace(/^http/, "ws")}/analyzer/ws?t=${doc.ticket}`);
  ws.binaryType = "arraybuffer";
  const queue = [];
  let waiter = null, closed = false;
  const settle = (v) => {
    const w = waiter;
    waiter = null;
    w?.(v);
  };
  ws.onmessage = (e) => {
    const b = new Uint8Array(e.data);
    if (waiter) {
      settle(b);
    } else {
      queue.push(b);
    }
  };
  const gone = new Promise((resolve) => {
    ws.onclose = () => {
      closed = true;
      settle(null);
      resolve();
    };
  });
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    /* Refused: no analyzer, USB/IP's, another address on it (GET /api/analyzer says which) */
    ws.onerror = () => reject(new Error("the node did not open the analyzer"));
  });
  return {
    gone,
    write: async (bytes) => ws.send(bytes),
    read: () => (queue.length ? Promise.resolve(queue.shift())
                              : closed ? Promise.resolve(null) : new Promise((resolve) => (waiter = resolve))),
    close: async () => {
      ws.close();
      await gone;
    },
  };
}
