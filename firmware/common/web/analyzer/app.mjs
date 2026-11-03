/*
 * The standalone logic analyzer page (index.html): an analyzer on this
 * computer's USB through Web Serial, its capture settings, the viewer.
 * Channel names and settings stay in this browser.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture, depth } from "./capture.mjs";
import { DEMO_NAMES, demoCapture } from "./demo.mjs";
import { Analyzer, MAX_CHANNELS, TRIGGER } from "./protocol.mjs";
import { knownSerial, openSerial, serialSupported } from "./serial.mjs";
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

function showCapture() {
  const rows = cap.channels.map((c, k) => ({ k, name: settings.names[c] || capNames[k] || `CH${c + 1}`,
                                             color: `--lane-${c % 8}` }));
  $("cap-meta").textContent = `${cap.count.toLocaleString("en-US")} samples at ${cap.rate / 1e6} MS/s, ` +
                              `${fmtTime(cap.count / cap.rate)}`;
  viewer.show(cap, rows);
}

$("demo").addEventListener("click", () => {
  cap = demoCapture();
  capNames = DEMO_NAMES;
  setState("Demo capture: made-up signals", "var(--muted)");
  showCapture();
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
