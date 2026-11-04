/*
 * The standalone logic analyzer page (index.html): an analyzer on this
 * computer's USB through Web Serial, and what panel.mjs shares with the bay
 * page's card.  Channel names, settings and decoders stay in this browser.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { esc } from "./decoding.mjs";
import { DEMO_DECODERS, DEMO_NAMES, demoCapture } from "./demo.mjs";
import { Panel, sorted } from "./panel.mjs";
import { loadRam, openBootrom, usbSupported } from "./picoboot.mjs";
import { Analyzer, MAX_CHANNELS, TRIGGER } from "./protocol.mjs";
import { knownSerial, openSerial, serialSupported } from "./serial.mjs";
import { uf2RamImage } from "./uf2.mjs";
import { fmtTime } from "./viewer.mjs";

const $ = (id) => document.getElementById(id);

let analyzer = null, transport = null, info = null, capNames = [];

const panel = new Panel({
  store: "hwtr-analyzer",
  defaults: { names: {}, on: [0, 1, 2, 3, 4, 5, 6, 7], rate: 10e6, duration: 10e-3, pre: 0.2, trig: 0, edge: "fall",
              decoders: [] },
  chName: (c) => settings().names[c] || `CH${c + 1}`,
  laneName: (k) => settings().names[panel.cap.channels[k]] || capNames[k] || `CH${panel.cap.channels[k] + 1}`,
  laneColor: (c) => `--lane-${c % 8}`,
  onSettings: () => renderSettings(),
  fileStem: () => "capture",
  readColor: "var(--accent)",
});
function settings() {
  return panel.settings;
}
const chName = panel.chName;

let wide = settings().on.some((c) => c >= 8);

function setPill(text, color) {
  $("pill").style.setProperty("--c", color);
  $("pill-text").textContent = text;
}

/* --- Settings ------------------------------------------------------------------ */

function renderChannels() {
  const s = settings(), n = wide ? MAX_CHANNELS : 8;
  $("la-chans").innerHTML = Array.from({ length: n }, (_, c) => `
    <label style="--c: var(--lane-${c % 8})">
      <input type="checkbox" data-ch="${c}" ${s.on.includes(c) ? "checked" : ""} aria-label="CH${c + 1}">
      <small>CH${c + 1}</small>
      <input type="text" data-name="${c}" value="${esc(s.names[c] ?? "")}"
             placeholder="name" aria-label="CH${c + 1} name" maxlength="24">
    </label>`).join("");
  $("more-ch").textContent = wide ? "Channels 1–8 only" : "Channels 9–24";
}

function renderSettings() {
  const s = settings(), on = sorted(s.on);
  const t = panel.renderTiming(on);
  $("trig-ch").innerHTML = on.map((c) =>
    `<option value="${c}" ${c === s.trig ? "selected" : ""}>${esc(chName(c))}</option>`).join("");
  if (!on.includes(s.trig) && on.length) {
    s.trig = on[0];
  }
  $("trig-edge").value = s.edge;
  panel.summary([`${s.rate / 1e6} MS/s`, fmtTime(t.seconds), `trigger ${chName(s.trig)} ${s.edge === "fall" ? "↓" : "↑"}`,
                 `${on.length} channel${on.length === 1 ? "" : "s"}`]);
  $("la-cap").disabled = !analyzer || !!panel.busy || !on.length;
  panel.save();
}

$("more-ch").addEventListener("click", () => {
  wide = !wide;
  if (!wide) {
    settings().on = settings().on.filter((c) => c < 8);
  }
  renderChannels();
  renderSettings();
});
for (const id of ["trig-ch", "trig-edge"]) {
  $(id).addEventListener("change", () => {
    const s = settings();
    s.trig = Number($("trig-ch").value);
    s.edge = $("trig-edge").value;
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
      panel.setState(e.message, "var(--fault)");
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
  panel.setInfo(info);
  $("info").hidden = false;
  $("connect").hidden = true;
  $("disconnect").hidden = false;
  $("connect-hint").hidden = true;
  $("where").textContent = "this computer's USB";
  setPill(`Connected · ${info.board.replace(/_/g, " ")} v${info.version}`, "var(--ok)");
  panel.setState("Ready", "var(--ok)");
  renderSettings();
}

async function disconnect() {
  panel.busy?.abort();
  await transport?.close();
  transport = analyzer = info = null;
  panel.setInfo(null);
  $("info").hidden = true;
  $("connect").hidden = false;
  $("disconnect").hidden = true;
  $("connect-hint").hidden = false;
  $("where").textContent = "–";
  setPill("Not connected", "var(--muted)");
  panel.setState("Connect an analyzer, or load the demo");
  renderSettings();
}

$("connect").addEventListener("click", () => connect());
$("disconnect").addEventListener("click", disconnect);
if (serialSupported()) {
  navigator.serial.addEventListener("disconnect", (e) => {
    if (transport && e.target === transport.port) {
      disconnect();
      panel.setState("The analyzer was unplugged", "var(--warn)");
    }
  });
}

$("la-cap").addEventListener("click", async () => {
  const s = settings(), on = sorted(s.on);
  panel.begin();
  $("la-cap").disabled = true;
  $("la-cancel").hidden = false;
  panel.setState("Sending the settings…", "var(--warn)");
  try {
    const cap = await panel.read(analyzer, {
      ...panel.request(on),
      trigger: { type: TRIGGER.EDGE, channel: s.trig, inverted: s.edge === "fall" },
    }, () => panel.setState(`Waiting for ${chName(s.trig)} ${s.edge === "fall" ? "↓" : "↑"}`, "var(--warn)"));
    capNames = on.map(chName);
    panel.ownDecoders = null;
    panel.setState(`Captured at ${new Date().toLocaleTimeString()}`, "var(--ok)");
    panel.captured(cap);
  } catch (e) {
    panel.setState(e.name === "AbortError" ? "Cancelled" : e.message, e.name === "AbortError" ? "var(--muted)" : "var(--fault)");
  } finally {
    panel.end();
    $("la-cancel").hidden = true;
    renderSettings();
  }
});

$("demo").addEventListener("click", () => {
  capNames = DEMO_NAMES;
  panel.ownDecoders = structuredClone(DEMO_DECODERS);
  panel.setState("Demo capture: made-up signals", "var(--muted)");
  panel.show(demoCapture());
});

/* --- A blank RP2350: the analyzer into its RAM (WebUSB) -------------------------------- */

let ramImage = null;

$("ram-file").addEventListener("change", async () => {
  const f = $("ram-file").files[0];
  if (!f) {
    return;
  }
  ramImage = null;
  try {
    ramImage = uf2RamImage(new Uint8Array(await f.arrayBuffer()));
    $("ram-what").textContent = `${f.name}: ${ramImage.body.length.toLocaleString("en-US")} bytes at 0x${ramImage.addr.toString(16)}`;
  } catch (e) {
    $("ram-what").textContent = `${f.name}: ${e.message}`;
  }
  $("ram-load").disabled = !ramImage;
});

$("ram-load").addEventListener("click", async () => {
  $("ram-load").disabled = true;
  try {
    const boot = await openBootrom();
    await loadRam(boot, ramImage, (sent, total) => panel.setState(`Loading ${Math.round(sent / 1024)} of ${Math.round(total / 1024)} KB`,
                                                                  "var(--accent)"));
    panel.setState("Loaded: the analyzer starts, then Connect… and pick it", "var(--ok)");
    /* A port this page was given before comes back by itself */
    setTimeout(() => !analyzer && serialSupported() && knownSerial().then((p) => p && connect(p)), 1500);
  } catch (e) {
    if (e.name !== "NotFoundError") {
      panel.setState(`Not loaded: ${e.message}`, "var(--fault)");
    }
  } finally {
    $("ram-load").disabled = !ramImage;
  }
});

/* --- Start ---------------------------------------------------------------------- */

renderChannels();
renderSettings();
$("ram").hidden = !usbSupported();
if (!serialSupported()) {
  $("no-serial").hidden = false;
  $("connect").disabled = true;
} else {
  knownSerial().then((p) => p && connect(p));
}
/* The page opens on something to look at */
$("demo").click();
