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
