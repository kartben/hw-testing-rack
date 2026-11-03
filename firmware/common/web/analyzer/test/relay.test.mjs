/*
 * relay.mjs: the ticket, then the WebSocket as a byte transport, with a fake
 * fetch and WebSocket standing in for the node.
 *
 *   node --test "firmware/common/web/analyzer/test/*.test.mjs"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { openRelay } from "../relay.mjs";

/* The node: a ticket for anyone, a WebSocket that accepts or refuses */
function fakeNode({ refuse = false } = {}) {
  const seen = { posts: [], sent: [], sockets: [] };
  globalThis.fetch = async (url, opts) => {
    seen.posts.push([url, opts.method]);
    return { ok: true, status: 200, json: async () => ({ ticket: "00112233aabbccdd" }) };
  };
  globalThis.WebSocket = class {
    constructor(url) {
      this.url = url;
      seen.sockets.push(this);
      setTimeout(() => (refuse ? (this.onerror?.(), this.onclose?.()) : this.onopen?.()), 1);
    }
    send(b) {
      seen.sent.push([...b]);
    }
    close() {
      setTimeout(() => this.onclose?.(), 1);
    }
    /* What the analyzer sends */
    feed(bytes) {
      this.onmessage?.({ data: Uint8Array.from(bytes).buffer });
    }
  };
  return seen;
}

test("a ticket, then the WebSocket: bytes both ways, in order; null once it closes", async () => {
  const seen = fakeNode();
  const t = await openRelay("http://bay-b3.local");
  assert.deepEqual(seen.posts, [["http://bay-b3.local/api/console/ticket", "POST"]]);
  const ws = seen.sockets[0];
  assert.equal(ws.url, "ws://bay-b3.local/analyzer/ws?t=00112233aabbccdd");
  assert.equal(ws.binaryType, "arraybuffer");

  await t.write(Uint8Array.of(0x55, 0xaa, 0x00, 0xaa, 0x55));
  assert.deepEqual(seen.sent, [[0x55, 0xaa, 0x00, 0xaa, 0x55]]);

  /* Bytes that came before the read, and a read that waits for them */
  ws.feed([1, 2]);
  assert.deepEqual([...(await t.read())], [1, 2]);
  const later = t.read();
  ws.feed([3]);
  assert.deepEqual([...(await later)], [3]);

  const pending = t.read();
  await t.close();
  assert.equal(await pending, null);
  assert.equal(await t.read(), null);
});

test("a WebSocket the node refuses: an error, no transport", async () => {
  fakeNode({ refuse: true });
  await assert.rejects(openRelay("http://bay-b3.local"), /did not open the analyzer/);
});
