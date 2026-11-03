/*
 * The bay page's Wires card (index.html): the DATA x4's pin matrix
 * (/api/wires, src/wires.c).  Each port's header as printed on the board;
 * a P pin tapped goes on one of the buses A-H, which the analyzer reads as
 * CH1-8.  Changes are staged here and applied together (the node opens what
 * moves before it closes anything); the buses' names live on the node.
 * The node serves it as /wires-card.mjs.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { $, api, toast } from "/rack.mjs";

const BUSES = [..."ABCDEFGH"];
/* The 2 x 6 header as printed: upper row, then lower row */
const UPPER = ["VREF", "P1", "P2", "P3", "P4", "BOOT"];
const LOWER = ["GND", "P5", "P6", "P7", "P8", "RST"];
const VREF_MIN_MV = 650;
const REFRESH_MS = 10000;

let status = null, host = location.hostname, boardName = () => "";
let doc = null;                 /* GET /api/wires */
let applied = {}, staged = {};  /* "2/1" (port/pin) -> "A" */
let names = [], stagedNames = [];
let fetchedAt = 0, seen = "", picking = null, busy = false;
/* Edited here and not applied: a reading of the node leaves the edits alone */
let dirty = false;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
const key = (port, pin) => `${port}/${pin}`;
const portOf = (k) => Number(k.split("/")[0]);
const slot = (port) => status?.ports?.find((p) => p.port === port)?.slot ?? `${port}`;
const label = (k) => `${slot(portOf(k))}·P${k.split("/")[1]}`;
const pinsOn = (map, b) => Object.keys(map).filter((k) => map[k] === b).sort();
const portDoc = (port) => doc?.ports.find((p) => p.port === port);
const lane = (b) => `var(--lane-${BUSES.indexOf(b)})`;
/* 1.8 V and 3.3 V boards: what the port's VREF says, when the node has a reading */
const level = (port) => {
  const mv = portDoc(port)?.vref_mv;
  return mv == null ? null : mv < 2500 ? "low" : "high";
};

function fromDoc(d) {
  doc = d;
  applied = Object.fromEntries(d.pins.map((p) => [key(p.port, p.pin), p.bus]));
  names = [...d.names];
  document.dispatchEvent(new CustomEvent("hwtr-wires", { detail: d }));
}

function changes() {
  const keys = new Set([...Object.keys(applied), ...Object.keys(staged)]);
  return [...keys].filter((k) => (applied[k] ?? "") !== (staged[k] ?? "")).length +
    stagedNames.filter((n, i) => n !== (names[i] ?? "")).length;
}

async function load() {
  try {
    fromDoc(await api("/api/wires"));
    fetchedAt = Date.now();
    if (!dirty) {
      staged = { ...applied };
      stagedNames = [...names];
    }
    render();
  } catch (e) {
    $("wire-meta").textContent = e.status === 404 ? "no matrix" : `not read: ${e.message}`;
  }
}

/* --- Rendering ------------------------------------------------------------------ */

function renderPorts() {
  $("wire-ports").innerHTML = (status?.ports ?? []).map((sp) => {
    const p = portDoc(sp.port) ?? { on: sp.power.on, vref_mv: null, held: !sp.power.on };
    const cell = (n) => {
      if (!n.startsWith("P")) {
        return `<span class="fix">${n}</span>`;
      }
      const k = key(sp.port, n.slice(1)), b = staged[k] ?? "", pend = (applied[k] ?? "") !== b;
      const closed = doc?.pins.find((x) => key(x.port, x.pin) === k)?.closed;
      return `<button type="button" class="pin${b ? " on" : ""}${pend ? " pending" : ""}" ${b ? `style="--c: ${lane(b)}"` : ""}
        data-key="${k}" popovertarget="wire-pick" aria-label="${esc(sp.slot)} ${n}${b ? `, bus ${b}` : ", free"}${
        b && !pend && closed === false ? ", held open" : ""}"><small>${n}</small><b>${b || "·"}</b></button>`;
    };
    const why = !p.on ? "off" : p.vref_mv != null && p.vref_mv < VREF_MIN_MV ? "no VREF" : "";
    const vref = why ? `<span class="vref low" title="Its pins stay open while it is ${why === "off" ? "off" : "under 0.65 V"}">${why}</span>`
      : p.vref_mv != null ? `<span class="vref" title="VREF read by the co-processor">${(p.vref_mv / 1000).toFixed(2)} V</span>`
      : `<span class="vref none" title="No VREF reading: the co-processor runs the analyzer. The port's power alone decides">VREF ?</span>`;
    return `<div class="port"${p.held ? " data-held" : ""}>
      <div class="port-h"><b>${esc(sp.slot)}</b><span class="board">${esc(boardName(sp.slot) || "")}</span>${vref}</div>
      <div class="hdr">${UPPER.map(cell).join("")}${LOWER.map(cell).join("")}</div></div>`;
  }).join("");
}

function renderBuses() {
  $("wire-buses").innerHTML = BUSES.map((b, i) => {
    const on = pinsOn(staged, b), was = new Set(pinsOn(applied, b));
    const levels = new Set(on.map((k) => level(portOf(k))).filter(Boolean));
    const ports = new Set(on.map(portOf));
    let tags = "";
    if (levels.size > 1) {
      tags += '<span class="tag warn" title="Each port\'s level shifter translates: 1.8 V and 3.3 V boards on one wire, up to about 1–2 MHz">1.8 ↔ 3.3 V</span>';
    }
    if (on.length === 1) {
      tags += '<span class="tag" title="One pin: the analyzer listens, no other board is joined">probe only</span>';
    } else if (on.length > 1 && ports.size === 1) {
      tags += '<span class="tag" title="Two pins of the same board joined">loop on one board</span>';
    }
    const pins = on.map((k) => `<code class="${was.has(k) ? "" : "pending"}">${esc(label(k))}</code>`).join("");
    return `<li class="${on.length ? "" : "free"}" style="--c: ${lane(b)}">
      <span class="bdot">${b}</span>
      <input type="text" data-bus="${i}" value="${esc(stagedNames[i] ?? "")}" maxlength="23"
             placeholder="${on.length ? "name this wire" : "free"}" aria-label="Bus ${b}: what it carries">
      <span class="ch" title="The analyzer's channel">CH${i + 1}</span>
      <div class="bpins">${pins || "no pin"}${tags}</div></li>`;
  }).join("");
}

function renderFoot() {
  const n = changes(), pins = Object.keys(applied).length, buses = new Set(Object.values(applied)).size;
  const control = !status?.access || status.access.allow?.includes("control");
  $("wire-pending").textContent = busy ? "Applying…" : n ? `${n} change${n > 1 ? "s" : ""} not applied` : "All applied";
  $("wire-pending").classList.toggle("dirty", n > 0);
  $("wire-apply").disabled = busy || !n || !control;
  $("wire-discard").disabled = busy || !n;
  $("wire-open-all").disabled = busy || !control || !Object.keys(staged).length;
  $("wire-meta").textContent = !doc?.matrix ? "the matrix does not answer"
    : pins ? `${pins} pin${pins > 1 ? "s" : ""} on ${buses} bus${buses > 1 ? "es" : ""}` : "no wire";
  $("wire-note").hidden = doc?.matrix !== false && !doc?.error;
  $("wire-note-text").textContent = doc?.error ?? "The matrix does not answer: the DATA ×4 is off, or it is a base board.";
  const bay = (status?.ports?.[0]?.slot ?? "").split(".")[0] || "B3";
  const parts = BUSES.map((b) => [b, pinsOn(staged, b)]).filter(([, on]) => on.length)
    .map(([b, on]) => `${b}=${on.map((k) => `${portOf(k)}:P${k.split("/")[1]}`).join(",")}`);
  $("wire-cli").textContent = `bayctl wire ${bay} ${parts.join(" ") || "--open-all"}`;
}

function render() {
  renderPorts();
  renderBuses();
  renderFoot();
}

/* --- Wiring ------------------------------------------------------------------------ */

function update(s, pageHost, nameOf) {
  status = s;
  host = pageHost;
  boardName = nameOf ?? boardName;
  /* The ports' power decides what is held: read the matrix again when it changes, else now and then */
  const now = (s.ports ?? []).map((p) => `${p.port}:${p.power.on}`).join(",");
  if (now !== seen || Date.now() - fetchedAt > REFRESH_MS) {
    seen = now;
    load();
  } else {
    render();
  }
}

export function mount() {
  $("wire-ports").addEventListener("click", (e) => {
    const btn = e.target.closest(".pin");
    if (!btn) {
      return;
    }
    picking = btn.dataset.key;
    const port = portOf(picking), cur = staged[picking] ?? "", p = portDoc(port);
    $("wire-pick-t").textContent = label(picking);
    $("wire-pick-s").textContent = [boardName(slot(port)),
      p?.vref_mv != null ? `VREF ${(p.vref_mv / 1000).toFixed(2)} V` : "no VREF reading"].filter(Boolean).join(", ");
    $("wire-pick-grid").innerHTML = BUSES.map((b, i) => {
      const on = pinsOn(staged, b).filter((k) => k !== picking);
      const text = stagedNames[i] || (on.length ? on.map(label).join(", ") : "free");
      return `<button type="button" data-bus="${b}" style="--c: ${lane(b)}" aria-current="${cur === b}"><i>${b}</i><span>${esc(text)}</span></button>`;
    }).join("") + `<button type="button" data-bus="" class="free" aria-current="${!cur}">Off the buses</button>`;
    $("wire-pick-note").hidden = true;
  });
  $("wire-pick-grid").addEventListener("pointerover", (e) => {
    const btn = e.target.closest("button[data-bus]");
    const me = picking && level(portOf(picking));
    const other = btn?.dataset.bus && me &&
      pinsOn(staged, btn.dataset.bus).some((k) => k !== picking && level(portOf(k)) && level(portOf(k)) !== me);
    $("wire-pick-note").hidden = !other;
  });
  $("wire-pick-grid").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-bus]");
    if (!btn || !picking) {
      return;
    }
    if (btn.dataset.bus) {
      staged[picking] = btn.dataset.bus;
    } else {
      delete staged[picking];
    }
    dirty = true;
    $("wire-pick").hidePopover();
    render();
  });
  $("wire-buses").addEventListener("input", (e) => {
    const i = Number(e.target.dataset.bus);
    if (Number.isInteger(i)) {
      stagedNames[i] = e.target.value;
      dirty = true;
      renderFoot();
    }
  });
  $("wire-apply").addEventListener("click", async () => {
    busy = true;
    renderFoot();
    try {
      const d = await api("/api/wires", {
        pins: Object.entries(staged).map(([k, bus]) => ({ port: portOf(k), pin: Number(k.split("/")[1]), bus })),
        names: stagedNames.map((n) => n.trim()),
      });
      fromDoc(d);
      staged = { ...applied };
      stagedNames = [...names];
      dirty = false;
      toast(d.changed ? `${d.changed} switch${d.changed > 1 ? "es" : ""} moved, break-before-make` : "Applied");
    } catch (e) {
      toast(`Not applied: ${e.message}`);
    } finally {
      busy = false;
      render();
    }
  });
  $("wire-discard").addEventListener("click", () => {
    staged = { ...applied };
    stagedNames = [...names];
    dirty = false;
    render();
  });
  $("wire-open-all").addEventListener("click", () => {
    staged = {};
    dirty = true;
    render();
    toast("Every pin off the buses: Apply to open the switches");
  });
  return { update };
}
