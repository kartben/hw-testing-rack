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

/* --- Firmware updates (firmware/common/web/update_http.c) ------------------------ */

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
const kb = (n) => `${Math.round(n / 1024)} KB`;
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const UP_NAMES = { wifi: "Wi-Fi", bus: "the rack bus" };

/* Version, image id and size of a signed image (zephyr.signed.bin), as the firmware reads it */
export function imageInfo(bytes) {
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const fail = (why) => { throw new Error(why); };
  if (bytes.length < 32 || v.getUint32(0, true) !== 0x96f3b83d) {
    fail("not a signed image: pick zephyr.signed.bin from a --sysbuild build");
  }
  const hdr = v.getUint16(8, true), prot = v.getUint16(10, true), size = v.getUint32(12, true);
  const tlv = hdr + size + prot;
  if (tlv + 4 > bytes.length || v.getUint16(tlv, true) !== 0x6907) fail("image truncated");
  if (tlv + v.getUint16(tlv + 2, true) !== bytes.length) fail("image truncated, or bytes after it");
  let id = "";
  for (let o = hdr + size + 4; prot && o + 4 <= hdr + size + prot; o += 4 + v.getUint16(o + 2, true)) {
    if (v.getUint16(o, true) === 0xa0) id = new TextDecoder().decode(bytes.subarray(o + 4, o + 4 + v.getUint16(o + 2, true)));
  }
  if (!id) fail("no image id: not built from this repository (firmware/common/sysbuild.cmake)");
  const build = v.getUint32(24, true);
  return { version: `${bytes[20]}.${bytes[21]}.${v.getUint16(22, true)}${build ? `+${build}` : ""}`, id, size: bytes.length };
}

/* A POST with upload progress (fetch has none) */
function postBytes(url, body, progress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => progress?.(e.loaded, e.total);
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status < 300) resolve(data);
      else reject(Object.assign(new Error(data.error ?? `${xhr.status} ${xhr.statusText}`), { status: xhr.status, data }));
    };
    xhr.onerror = () => reject(new Error("upload cut off: connection lost"));
    xhr.send(body);
  });
}

/*
 * Send a signed image: an admin request with its size and SHA-256 opens the
 * update (admin(path, body) is the page's signed request), then the image
 * goes with the ticket it got.  The device answers once it has checked the
 * image, and restarts into it.
 */
export async function sendFirmware(bytes, { admin, force = false, progress }) {
  const { ticket } = await admin("/api/update/begin", { size: bytes.length, sha256: hex(sha256(bytes)), force });
  return postBytes(`/api/update?ticket=${ticket}`, bytes, progress);
}

/* "0.6.0 on trial" and the like, for a page's Firmware line */
export function firmwareLabel(f) {
  if (!f) return "";
  const tag = f.trial ? `<span class="tag warn">on trial</span>`
    : f.last?.result === "rolled back" ? `<span class="tag bad" title="The update to ${f.last.to} did not confirm itself">rolled back</span>` : "";
  return `${f.version}${tag ? ` ${tag}` : ""}`;
}

const STEPS = [
  ["upload", "Send", "signed with the admin key, written to the update slot"],
  ["restart", "Restart", "MCUboot checks the signature and swaps it in"],
  ["trial", "Trial", "the new firmware must get back what worked before"],
  ["done", "Confirmed", "it stays; otherwise MCUboot goes back to the previous one"],
];

/*
 * The firmware dialog, the same on every page: pick zephyr.signed.bin, check
 * it (version, image id) before anything is sent, send it, then follow the
 * restart and the trial until the new firmware confirms itself or the device
 * goes back to the previous one.
 *   admin(path, body)   the page's signed request (claims or unlocks first)
 *   app                 "bay-node" or "power-hub" (where the build puts the image)
 *   force(why)          a reserved device: ask whether to update anyway -> bool
 *   changed(firmware)   the device came back
 */
export function firmwareDialog({ admin, app, force: askForce = async () => false, changed = () => {} }) {
  const dlg = document.createElement("dialog");
  dlg.className = "small-dlg fw-dlg";
  dlg.innerHTML = `<form method="dialog">
    <h3>Firmware</h3>
    <div class="fw-now"><b data-f="version"></b><code data-f="id"></code>
      <span class="tag warn" data-f="testkey" hidden title="Signed with MCUboot's public test key: any image signed with it boots on this device. Build with your own key (HWTR_SIGNING_KEY) for a rack.">test key</span></div>
    <p class="hint" data-f="last"></p>
    <label class="pick"><input type="file" accept=".bin" data-f="file">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V4m0 0-4 4m4-4 4 4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg>
      <span class="what"><b data-f="pick">Choose zephyr.signed.bin</b><small data-f="pick-sub">build/${app}/zephyr/zephyr.signed.bin, from <code>west build --sysbuild</code></small></span></label>
    <ol class="steps" data-f="steps" hidden>${STEPS.map(([k, name, what]) =>
      `<li data-step="${k}" data-s="wait"><span class="dot"></span><b>${name}</b><small>${what}</small></li>`).join("")}</ol>
    <p class="err" data-f="err"></p>
    <div class="btns"><button value="close" data-f="close">Close</button><button type="button" class="primary" data-f="go" disabled>Update</button></div>
  </form>`;
  document.body.append(dlg);
  const f = (name) => dlg.querySelector(`[data-f="${name}"]`);
  let fw = null, bytes = null, busy = false;

  function showNow(x) {
    fw = x;
    f("version").textContent = x.version;
    f("id").textContent = x.id;
    f("testkey").hidden = !x.test_key;
    const l = x.last;
    f("last").textContent = !l ? "Flashed over USB; no update over the network yet."
      : l.result === "on trial" ? `${l.to} on trial (was ${l.from || "?"}).`
      : l.result === "confirmed" ? `Last update: ${l.from ? `${l.from} → ` : ""}${l.to}, confirmed.`
      : `Last update: ${l.to} did not stay; back on ${x.version}.`;
  }

  function step(name, state, text, title) {
    const li = dlg.querySelector(`[data-step="${name}"]`);
    li.dataset.s = state;
    li.querySelector("b").textContent = title ?? STEPS.find(([k]) => k === name)[1];
    if (text !== undefined) li.querySelector("small").textContent = text;
    f("steps").hidden = false;
  }

  function trialText(t) {
    const missing = t.need.filter((n) => !t.up.includes(n)).map((n) => UP_NAMES[n]);
    return `${missing.length ? `waiting for ${missing.join(" and ")}` : `${t.need.map((n) => UP_NAMES[n]).join(" and ")} back: confirming`} · ${mmss(t.left_s)} left`;
  }

  /* After the upload, or when opened on a firmware on trial */
  async function follow(t0) {
    let back = !!fw?.trial;
    for (let deadline = Date.now() + 10 * 60e3; dlg.open && Date.now() < deadline;) {
      await sleep(1500);
      let x;
      try {
        x = await api("/api/update");
      } catch {
        if (back) step("trial", "run", "restarting…");
        continue;
      }
      if (x.state === "rebooting") continue;
      if (!back) {
        back = true;
        step("restart", "ok", `back after ${Math.round((Date.now() - t0) / 1000)} s, running ${x.version}`);
      }
      showNow(x);
      changed(x);
      if (x.trial) {
        step("trial", "run", trialText(x.trial));
      } else if (x.last?.result === "confirmed") {
        step("trial", "ok", "what worked before works again");
        step("done", "ok", `${x.version} confirmed itself: it stays`);
        return;
      } else {
        step("trial", "bad", `${x.last?.to ?? "the new firmware"} did not confirm itself`);
        step("done", "bad", `MCUboot went back: running ${x.version}`, "Rolled back");
        return;
      }
    }
  }

  f("file").addEventListener("change", async () => {
    const file = f("file").files[0];
    const pick = dlg.querySelector(".pick");
    bytes = null;
    f("go").disabled = true;
    f("err").textContent = "";
    delete pick.dataset.ok;
    delete pick.dataset.bad;
    if (!file) return;
    try {
      const b = new Uint8Array(await file.arrayBuffer());
      const info = imageInfo(b);
      if (info.id !== fw.id) throw new Error(`this image is for ${info.id}; this device runs ${fw.id}`);
      bytes = b;
      pick.dataset.ok = "";
      f("pick").textContent = `${fw.version} → ${info.version}${info.version === fw.version ? " (same version)" : ""}`;
      f("pick-sub").textContent = `${file.name} · ${kb(info.size)} · ${info.id}`;
      f("go").disabled = false;
    } catch (e) {
      pick.dataset.bad = "";
      f("pick").textContent = file.name;
      f("pick-sub").textContent = e.message;
    }
  });

  f("go").addEventListener("click", async () => {
    if (!bytes || busy) return;
    busy = true;
    f("go").disabled = true;
    dlg.querySelector(".pick").inert = true;
    f("err").textContent = "";
    STEPS.forEach(([k, , what]) => step(k, "wait", what));
    step("upload", "run", `0 of ${kb(bytes.length)}`);
    try {
      let r, forced = false;
      for (;;) {
        try {
          r = await sendFirmware(bytes, { admin, force: forced,
            progress: (sent, total) => step("upload", "run", `${kb(sent)} of ${kb(total)}`) });
          break;
        } catch (e) {
          if (e.status === 409 && !forced && /force/.test(e.message) && await askForce(e.message)) forced = true;
          else throw e;
        }
      }
      step("upload", "ok", `${kb(bytes.length)} sent; ${r.version} for ${r.id} checked`);
      step("restart", "run", "restarting into it…");
      await follow(Date.now());
    } catch (e) {
      if (e.quiet) {
        f("steps").hidden = true;       /* no admin key: the claim or unlock was cancelled */
      } else {
        step("upload", "bad", e.message);
        f("err").textContent = e.message;
      }
      dlg.querySelector(".pick").inert = false;
      f("go").disabled = false;
    } finally {
      busy = false;
    }
  });

  return {
    /* x: the page's last status, a fallback: the dialog asks the device itself (fresher) */
    async open(x) {
      x = await api("/api/update").catch(() => x);
      if (!x) return;
      showNow(x);
      if (!busy) {
        bytes = null;
        f("file").value = "";
        f("go").disabled = true;
        f("err").textContent = "";
        const pick = dlg.querySelector(".pick");
        pick.inert = !!x.trial;
        delete pick.dataset.ok;
        delete pick.dataset.bad;
        f("pick").textContent = "Choose zephyr.signed.bin";
        f("pick-sub").innerHTML = `build/${app}/zephyr/zephyr.signed.bin, from <code>west build --sysbuild</code>`;
        f("steps").hidden = true;
      }
      dlg.showModal();
      if (x.trial && !busy) {
        STEPS.forEach(([k, , what]) => step(k, "wait", what));
        step("upload", "ok", `${x.last?.to ?? x.version} sent earlier`);
        step("restart", "ok", `running ${x.version}`);
        step("trial", "run", trialText(x.trial));
        busy = true;
        follow(Date.now()).finally(() => { busy = false; });
      }
    },
  };
}
