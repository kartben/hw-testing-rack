/*
 * The standalone logic analyzer page (index.html): an analyzer on this
 * computer's USB through Web Serial, its capture settings, the viewer, the
 * decoders, the .vcd export.  Channel names, settings and decoders stay in
 * this browser.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture, depth } from "./capture.mjs";
import { BAUDS, DECODERS } from "./decoders.mjs";
import { DEMO_DECODERS, DEMO_NAMES, demoCapture } from "./demo.mjs";
import { Analyzer, MAX_CHANNELS, TRIGGER } from "./protocol.mjs";
import { knownSerial, openSerial, serialSupported } from "./serial.mjs";
import { toVcd } from "./vcd.mjs";
import { Viewer, fmtTime } from "./viewer.mjs";

const $ = (id) => document.getElementById(id);
const RATES = [1e6, 2e6, 5e6, 10e6, 20e6, 25e6, 50e6, 100e6];
const LENGTHS = [1000, 10000, 50000, 100000, 200000];
const STORE = "hwtr-analyzer";

const saved = (() => {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? "{}");
  } catch {
    return {};
  }
})();
const settings = {
  names: saved.names ?? {},
  on: saved.on ?? [0, 1, 2, 3, 4, 5, 6, 7],
  rate: saved.rate ?? 10e6,
  length: saved.length ?? 100000,
  pre: saved.pre ?? 0.2,
  trig: saved.trig ?? 0,
  edge: saved.edge ?? "fall",
  decoders: saved.decoders ?? [],
};
const save = () => {
  try {
    localStorage.setItem(STORE, JSON.stringify(settings));
  } catch {
    /* private window: settings last as long as the page */
  }
};

const viewer = new Viewer($("wave"), { onReadout: (t) => ($("readout").textContent = t) });
let analyzer = null, transport = null, info = null, busy = null, cap = null, capNames = [];
/* The demo brings its own decoders, the user's stay as they are */
let demoDecoders = null;
const decoders = () => demoDecoders ?? settings.decoders;
let wide = settings.on.some((c) => c >= 8);

const chName = (c) => settings.names[c] || `CH${c + 1}`;

function setState(text, color = "var(--muted)") {
  $("state").style.setProperty("--c", color);
  $("state").querySelector("span").textContent = text;
}

function setPill(text, color) {
  $("pill").style.setProperty("--c", color);
  $("pill-text").textContent = text;
}

/* --- Settings ------------------------------------------------------------------ */

function renderChannels() {
  const n = wide ? MAX_CHANNELS : 8;
  $("chans").innerHTML = Array.from({ length: n }, (_, c) => `
    <label style="--c: var(--lane-${c % 8})">
      <input type="checkbox" data-ch="${c}" ${settings.on.includes(c) ? "checked" : ""} aria-label="CH${c + 1}">
      <small>CH${c + 1}</small>
      <input type="text" data-name="${c}" value="${(settings.names[c] ?? "").replace(/"/g, "&quot;")}"
             placeholder="name" aria-label="CH${c + 1} name" maxlength="24">
    </label>`).join("");
  $("more-ch").textContent = wide ? "Channels 1–8 only" : "Channels 9–24";
}

function renderSettings() {
  const max = info?.maxRate ?? 100e6;
  $("rate").innerHTML = RATES.filter((r) => r <= max).map((r) =>
    `<option value="${r}" ${r === settings.rate ? "selected" : ""}>${r / 1e6} MS/s</option>`).join("");
  const on = [...settings.on].sort((a, b) => a - b);
  const d = info && on.length ? depth(info, on, settings.rate) : null;
  const lengths = [...LENGTHS.filter((l) => !d || l < d.samples), ...(d ? [d.samples] : [])];
  if (!lengths.includes(settings.length)) {
    settings.length = lengths.at(-1);
  }
  $("length").innerHTML = lengths.map((l) =>
    `<option value="${l}" ${l === settings.length ? "selected" : ""}>${l.toLocaleString("en-US")}${d && l === d.samples ? " (all)" : ""}</option>`).join("");
  $("pre").value = String(settings.pre);
  $("trig-ch").innerHTML = on.map((c) =>
    `<option value="${c}" ${c === settings.trig ? "selected" : ""}>${chName(c)}</option>`).join("");
  if (!on.includes(settings.trig) && on.length) {
    settings.trig = on[0];
  }
  $("trig-edge").value = settings.edge;
  $("depth").textContent = d
    ? `${settings.length.toLocaleString("en-US")} samples (${d.bits}-bit) · ${fmtTime(settings.length / settings.rate)}`
    : on.length ? "" : "pick at least one channel";
  $("capture").disabled = !analyzer || !!busy || !on.length;
  save();
}

$("chans").addEventListener("change", (e) => {
  const c = Number(e.target.dataset.ch);
  if (Number.isInteger(c)) {
    settings.on = e.target.checked ? [...new Set([...settings.on, c])] : settings.on.filter((x) => x !== c);
    renderSettings();
  }
});
$("chans").addEventListener("input", (e) => {
  const c = Number(e.target.dataset.name);
  if (Number.isInteger(c)) {
    settings.names[c] = e.target.value.trim();
    renderSettings();
    if (cap) {
      showCapture();
    }
  }
});
$("more-ch").addEventListener("click", () => {
  wide = !wide;
  if (!wide) {
    settings.on = settings.on.filter((c) => c < 8);
  }
  renderChannels();
  renderSettings();
});
for (const id of ["rate", "length", "pre", "trig-ch", "trig-edge"]) {
  $(id).addEventListener("change", () => {
    settings.rate = Number($("rate").value);
    settings.length = Number($("length").value);
    settings.pre = Number($("pre").value);
    settings.trig = Number($("trig-ch").value);
    settings.edge = $("trig-edge").value;
    renderSettings();
  });
}

/* --- The analyzer --------------------------------------------------------------- */

async function connect(port) {
  try {
    transport = await openSerial(port);
    analyzer = new Analyzer(transport);
    info = await Promise.race([analyzer.identify(),
      new Promise((_, no) => setTimeout(() => no(new Error("no answer: is it gusmanb's analyzer?")), 3000))]);
  } catch (e) {
    if (e.name !== "NotFoundError") {   /* the chooser closed with no port: nothing to say */
      setState(e.message, "var(--fault)");
    }
    await transport?.close();
    transport = analyzer = info = null;
    return;
  }
  $("i-board").textContent = info.board.replace(/_/g, " ");
  $("i-version").textContent = info.version;
  $("i-rate").textContent = `${info.maxRate / 1e6} MS/s`;
  $("i-buffer").textContent = `${(info.buffer / 1024).toLocaleString("en-US")} KB`;
  $("i-channels").textContent = info.channels;
  $("info").hidden = false;
  $("connect").hidden = true;
  $("disconnect").hidden = false;
  $("connect-hint").hidden = true;
  $("where").textContent = "this computer's USB";
  setPill(`Connected · ${info.board.replace(/_/g, " ")} v${info.version}`, "var(--ok)");
  setState("Ready", "var(--ok)");
  renderSettings();
}

async function disconnect() {
  busy?.abort();
  await transport?.close();
  transport = analyzer = info = null;
  $("info").hidden = true;
  $("connect").hidden = false;
  $("disconnect").hidden = true;
  $("connect-hint").hidden = false;
  $("where").textContent = "–";
  setPill("Not connected", "var(--muted)");
  setState("Connect an analyzer, or load the demo");
  renderSettings();
}

$("connect").addEventListener("click", () => connect());
$("disconnect").addEventListener("click", disconnect);
if (serialSupported()) {
  navigator.serial.addEventListener("disconnect", (e) => {
    if (transport && e.target === transport.port) {
      disconnect();
      setState("The analyzer was unplugged", "var(--warn)");
    }
  });
}

$("capture").addEventListener("click", async () => {
  const on = [...settings.on].sort((a, b) => a - b);
  const pre = Math.round(settings.length * settings.pre);
  busy = new AbortController();
  $("capture").disabled = true;
  $("cancel").hidden = false;
  setState("Sending the settings…", "var(--warn)");
  try {
    const r = await analyzer.capture({
      channels: on, rate: settings.rate, pre, post: settings.length - pre,
      trigger: { type: TRIGGER.EDGE, channel: settings.trig, inverted: settings.edge === "fall" },
    }, {
      signal: busy.signal,
      onStarted: () => setState(`Waiting for ${chName(settings.trig)} ${settings.edge === "fall" ? "↓" : "↑"}`,
                                "var(--warn)"),
      onData: (got, total) => {
        $("progress").hidden = false;
        $("progress").value = got / total;
        setState(`Reading ${Math.round(got / 1024)} of ${Math.round(total / 1024)} KB`, "var(--accent)");
      },
    });
    cap = new Capture(r);
    capNames = on.map(chName);
    demoDecoders = null;
    setState(`Captured at ${new Date().toLocaleTimeString()}`, "var(--ok)");
    showCapture();
  } catch (e) {
    setState(e.name === "AbortError" ? "Cancelled" : e.message, e.name === "AbortError" ? "var(--muted)" : "var(--fault)");
  } finally {
    busy = null;
    $("progress").hidden = true;
    $("cancel").hidden = true;
    renderSettings();
  }
});
$("cancel").addEventListener("click", () => busy?.abort());

/* --- The viewer ------------------------------------------------------------------ */

const laneName = (k) => settings.names[cap.channels[k]] || capNames[k] || `CH${cap.channels[k] + 1}`;

/* A decoder's rows, under the last lane it reads; a decoder that cannot run says why */
function decode(d) {
  const spec = DECODERS[d.type], k = {};
  let anchor = -1;
  for (const line of spec.lines) {
    const role = line.replace("?", ""), c = d.lines[role];
    if (c === undefined || c === null) {
      if (!line.endsWith("?")) {
        return { anchor, rows: [] };
      }
      continue;
    }
    k[role] = cap.channels.indexOf(c);
    if (k[role] < 0) {
      return { anchor: cap.channels.length - 1, rows: [{ label: spec.name, items: [
        { t0: cap.time(0), t1: cap.time(cap.count - 1), kind: "err", text: `CH${c + 1} is not in this capture` }] }] };
    }
    anchor = Math.max(anchor, k[role]);
  }
  try {
    return { anchor, rows: spec.run(cap, d, k) };
  } catch (e) {
    return { anchor, rows: [{ label: spec.name, items: [
      { t0: cap.time(0), t1: cap.time(cap.count - 1), kind: "err", text: e.message }] }] };
  }
}

function showCapture() {
  const decoded = decoders().map(decode);
  const rows = [];
  cap.channels.forEach((c, k) => {
    rows.push({ k, name: laneName(k), color: `--lane-${c % 8}` });
    for (const d of decoded.filter((x) => x.anchor === k)) {
      rows.push(...d.rows);
    }
  });
  $("cap-meta").textContent = `${cap.count.toLocaleString("en-US")} samples at ${cap.rate / 1e6} MS/s, ` +
                              `${fmtTime(cap.count / cap.rate)}`;
  $("vcd").disabled = false;
  viewer.show(cap, rows);
  renderDecoders();
}

$("demo").addEventListener("click", () => {
  cap = demoCapture();
  capNames = DEMO_NAMES;
  demoDecoders = structuredClone(DEMO_DECODERS);
  setState("Demo capture: made-up signals", "var(--muted)");
  showCapture();
});

$("vcd").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([toVcd(cap, cap.channels.map((_, k) => laneName(k)))],
                                           { type: "text/plain" }));
  const a = Object.assign(document.createElement("a"), {
    href: url, download: `capture-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.vcd`,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

/* --- Decoders ---------------------------------------------------------------------- */

const lineText = (d) => Object.entries(d.lines).filter(([, c]) => c !== null && c !== undefined)
  .map(([role, c]) => `${role.toUpperCase()} ${chName(c)}`).join(", ");

function renderDecoders() {
  $("decs").innerHTML = decoders().map((d, i) => `
    <span class="dec-chip"><b>${DECODERS[d.type].name}</b> ${lineText(d)}${d.baud ? ` · ${d.baud >= 1e6 ? `${d.baud / 1e6} M` : `${d.baud} `}Bd` : ""}${d.type === "spi" ? ` · mode ${d.mode ?? 0}` : ""}
      <button class="small" data-remove="${i}" aria-label="Remove this decoder">✕</button></span>`).join("") +
    `<button class="small" id="add-dec">+ Decoder</button>`;
}

$("decs").addEventListener("click", (e) => {
  const rm = e.target.closest("[data-remove]");
  if (rm) {
    decoders().splice(Number(rm.dataset.remove), 1);
    save();
    if (cap) {
      showCapture();
    }
  } else if (e.target.closest("#add-dec")) {
    openDecoderDialog();
  }
});

/* The channels a decoder can read: the capture's, else the ones picked for the next */
const pickable = () => (cap ? [...cap.channels] : [...settings.on].sort((a, b) => a - b));

function renderDecoderForm() {
  const type = $("dec-type").value, spec = DECODERS[type], chans = pickable();
  $("dec-lines").innerHTML = spec.lines.map((line, i) => {
    const role = line.replace("?", ""), optional = line.endsWith("?");
    return `<label>${role.toUpperCase()}${optional ? " (optional)" : ""}
      <select data-line="${role}">${optional ? '<option value="">none</option>' : ""}${chans.map((c) =>
        `<option value="${c}" ${!optional && chans[i] === c ? "selected" : ""}>${chName(c)}</option>`).join("")}</select></label>`;
  }).join("") + (type === "uart" ? `<label>Baud rate <select id="dec-baud">${BAUDS.map((b) =>
    `<option value="${b}" ${b === 115200 ? "selected" : ""}>${b.toLocaleString("en-US")}</option>`).join("")}</select></label>` : "")
    + (type === "spi" ? `<label>Mode <select id="dec-mode">${[0, 1, 2, 3].map((m) =>
    `<option value="${m}">${m}</option>`).join("")}</select></label>` : "");
}

function openDecoderDialog() {
  $("dec-type").innerHTML = Object.entries(DECODERS).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("");
  renderDecoderForm();
  $("dec-dlg").showModal();
}

$("dec-type").addEventListener("change", renderDecoderForm);
$("dec-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (e.submitter?.value === "cancel") {
    $("dec-dlg").close();
    return;
  }
  const d = { type: $("dec-type").value, lines: {} };
  for (const sel of $("dec-lines").querySelectorAll("select[data-line]")) {
    d.lines[sel.dataset.line] = sel.value === "" ? null : Number(sel.value);
  }
  if (d.type === "uart") {
    d.baud = Number($("dec-baud").value);
  }
  if (d.type === "spi") {
    d.mode = Number($("dec-mode").value);
  }
  decoders().push(d);
  save();
  $("dec-dlg").close();
  if (cap) {
    showCapture();
  } else {
    renderDecoders();
  }
});
for (const b of document.querySelectorAll("[data-zoom]")) {
  b.addEventListener("click", () => (b.dataset.zoom === "fit" ? viewer.fit()
                                                              : viewer.zoom(b.dataset.zoom === "in" ? 0.5 : 2)));
}
$("clear-cursors").addEventListener("click", () => viewer.clearCursors());

/* --- Start ---------------------------------------------------------------------- */

renderChannels();
renderSettings();
if (!serialSupported()) {
  $("no-serial").hidden = false;
  $("connect").disabled = true;
} else {
  knownSerial().then((p) => p && connect(p));
}
/* The page opens on something to look at */
$("demo").click();
