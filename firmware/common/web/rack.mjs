/*
 * hw-testing-rack web pages: the helpers the bay node and the power hub
 * pages share (served as /rack.mjs, gzipped in flash).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

export const $ = (id) => document.getElementById(id);

/* GET without a body, POST with one; errors carry the HTTP status and the board's reply */
export async function api(path, body, headers = {}) {
  const text = typeof body === "string" ? body : body === undefined ? undefined : JSON.stringify(body);
  const init = text === undefined ? { headers } : {
    method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: text,
  };
  const res = await fetch(path, { ...init, signal: AbortSignal.timeout(text ? 10000 : 4000) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error ?? `${res.status} ${res.statusText}`),
    { status: res.status, data });
  return data;
}

/* milli-units -> units with d decimals */
export const fix = (v, d) => (v / 1000).toFixed(d);
export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function uptime(s) {
  const d = Math.floor(s / 86400), h = Math.floor(s / 3600) % 24, m = Math.floor(s / 60) % 60;
  return d ? `${d} d ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}

export function ago(s) {
  return s < 60 ? `${Math.round(s)} s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${uptime(s)} ago`;
}

/* A sparkline in an <svg viewBox="0 0 120 40"> holding a <polygon> and a <polyline> */
export class Spark {
  constructor(svg, { length = 60, floor = 100 } = {}) {
    this.line = svg.querySelector("polyline");
    this.fill = svg.querySelector("polygon");
    this.length = length;
    this.floor = floor;
    this.samples = [];
  }

  push(v) {
    this.samples.push(v);
    if (this.samples.length > this.length) this.samples.shift();
    const data = this.samples.length > 1 ? this.samples : [v, v];
    const max = Math.max(this.floor, ...data) * 1.1;
    const step = 120 / (data.length - 1);
    const pts = data.map((x, i) => `${(i * step).toFixed(1)},${(40 - x / max * 38).toFixed(1)}`);
    this.line.setAttribute("points", pts.join(" "));
    this.fill.setAttribute("points", `0,40 ${pts.join(" ")} 120,40`);
  }
}

/* <div popover id="toast"> */
export function toast(text, ms = 2600) {
  const el = $("toast");
  el.textContent = text;
  el.showPopover?.();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.hidePopover?.(), ms);
}

/* <dialog id="confirm"> with a <p> and OK / Cancel buttons (value "ok") */
export function confirmed(text) {
  const dlg = $("confirm");
  dlg.querySelector("p").textContent = text;
  dlg.returnValue = "";
  dlg.showModal();
  return new Promise((resolve) => dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"),
    { once: true }));
}

/* Buttons with data-copy="<element id>" copy that element's text */
export function copyButtons(root = document) {
  root.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-copy]");
    if (!btn) return;
    await navigator.clipboard.writeText($(btn.dataset.copy).textContent);
    toast("Copied");
  });
}

/* Poll fn every ms while the page is visible; fn throws -> onError */
export function poll(fn, ms, onError) {
  let timer;
  const run = async () => {
    clearTimeout(timer);
    try {
      await fn();
    } catch (e) {
      onError?.(e);
    }
    if (!document.hidden) timer = setTimeout(run, ms);
  };
  document.addEventListener("visibilitychange", () => { if (!document.hidden) run(); });
  run();
  return run;
}

/* --- Admin requests: the bay nodes and the hub sign them the same way ------------ */

/*
 * SHA-256 and HMAC for signed admin requests: crypto.subtle only exists in
 * secure contexts, and http://bay-b3.local or http://rack.local is not one.
 */
const SHA_K = Uint32Array.from({ length: 64 }, (_, i) => {
  const primes = [];
  for (let n = 2; primes.length < 64; n++) if (primes.every((p) => n % p)) primes.push(n);
  return (Math.cbrt(primes[i]) % 1) * 2 ** 32;
});
const SHA_H = Uint32Array.from([2, 3, 5, 7, 11, 13, 17, 19], (p) => (Math.sqrt(p) % 1) * 2 ** 32);

export function sha256(bytes) {
  const n = ((bytes.length + 72) >> 6) << 6;
  const m = new Uint8Array(n);
  m.set(bytes);
  m[bytes.length] = 0x80;
  const dv = new DataView(m.buffer);
  dv.setUint32(n - 8, Math.floor(bytes.length / 2 ** 29));
  dv.setUint32(n - 4, bytes.length * 8);
  const H = SHA_H.slice(), W = new Uint32Array(64);
  const rotr = (x, r) => (x >>> r) | (x << (32 - r));
  for (let off = 0; off < n; off += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(off + 4 * i);
    for (let i = 16; i < 64; i++) {
      const a = W[i - 15], b = W[i - 2];
      W[i] = W[i - 16] + (rotr(a, 7) ^ rotr(a, 18) ^ (a >>> 3)) + W[i - 7] + (rotr(b, 17) ^ rotr(b, 19) ^ (b >>> 10));
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + SHA_K[i] + W[i]) >>> 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      [h, g, f, e, d, c, b, a] = [g, f, e, (d + t1) >>> 0, c, b, a, (t1 + t2) >>> 0];
    }
    [a, b, c, d, e, f, g, h].forEach((v, i) => (H[i] += v));
  }
  const out = new Uint8Array(32);
  H.forEach((v, i) => new DataView(out.buffer).setUint32(4 * i, v));
  return out;
}

export function hmac(key, msg) {
  const block = new Uint8Array(64);
  block.set(key.length > 64 ? sha256(key) : key);
  const pad = (x) => {
    const b = block.map((v) => v ^ x);
    return (data) => { const all = new Uint8Array(64 + data.length); all.set(b); all.set(data, 64); return all; };
  };
  return sha256(pad(0x5c)(sha256(pad(0x36)(msg))));
}

export const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
export const unhex = (text) => Uint8Array.from(text.match(/../g) ?? [], (h) => parseInt(h, 16));
/* The admin key of this page's device (localStorage is per origin: one per device) */
export function storedKey() {
  try { return localStorage.getItem("bay-admin-key") ?? ""; } catch { return ""; }
}

export function storeKey(key) {
  try { key ? localStorage.setItem("bay-admin-key", key) : localStorage.removeItem("bay-admin-key"); } catch { /* private window */ }
}

/* An admin request: X-Bay-Auth = <nonce>:<HMAC(key, nonce \n method \n path \n body)> */
export async function signed(path, body, key = storedKey()) {
  const { nonce } = await api("/api/access/nonce");
  const text = body === undefined ? "" : JSON.stringify(body);
  const mac = hmac(unhex(key), new TextEncoder().encode(`${nonce}\n${body === undefined ? "GET" : "POST"}\n${path}\n${text}`));
  return api(path, body === undefined ? undefined : text, { "X-Bay-Auth": `${nonce}:${hex(mac)}` });
}

/*
 * Claim the device: POST /api/access/claim (with the rack's key, or none for
 * a new one), then poll until someone presses its BOOT button.  Returns the
 * key (also stored), or "" if the dialog was closed meanwhile.
 * ui: started(), waiting(remaining_s), open() -> still waiting?
 */
export async function claimKey(key, ui) {
  const start = await api("/api/access/claim", key ? { key } : {});
  ui.started?.();
  while (ui.open()) {
    const r = await api("/api/access/claim", { ticket: start.ticket });
    if (r.state === "done") {
      storeKey(r.key);
      return r.key;
    }
    ui.waiting?.(r.remaining_s);
    await new Promise((ok) => setTimeout(ok, 1000));
  }
  return "";
}
