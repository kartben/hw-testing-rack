/*
 * The bay page's Logic analyzer card (index.html): the DATA x4 co-processor
 * running gusmanb's analyzer, through the node's relay (relay.mjs,
 * src/analyzer.c).  Who has it (this page or USB/IP), a capture, "Capture and
 * reset" (the capture starts as a board leaves reset: the node's MARK on
 * CH13), and what panel.mjs shares with the analyzer page.  The node serves it
 * as /analyzer/card.mjs, beside those shared modules.
 *
 * The page holds the analyzer only while it captures: another address can
 * use it in between.  Bus names, settings and decoders stay in this browser.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { $, api, toast } from "/rack.mjs";
import { esc } from "./decoding.mjs";
import { Panel, sorted } from "./panel.mjs";
import { Analyzer, TRIGGER, bytesPerSample, maxSamples } from "./protocol.mjs";
import { openRelay } from "./relay.mjs";
import { fmtTime } from "./viewer.mjs";

const BUSES = [..."ABCDEFGH"]; /* CH1-8: the buses, the co-processor's GPIO2-9 */
const MARK = 12;               /* CH13: the node's MARK, GPIO14 */
/* gusmanb's Pico 2 build, until the analyzer says (Analyzer.identify()) */
const PICO_2 = { maxRate: 100e6, buffer: 393216, channels: 24 };
let panel = null, settings = null, status = null, host = location.hostname, info = PICO_2;
/* The buses' names on the node (the Wires card's, /api/wires): a bus this browser has not named takes its */
let wireNames = [];
let capReset = null, capAt = null;
/* How the last capture went, [text, colour]: the state line keeps it while the analyzer is usable */
let outcome = null;

const busName = (c) => settings.names[c] || wireNames[c] || "";
const chName = (c) => (c === MARK ? "Mark" : busName(c) ? `${BUSES[c]} · ${busName(c)}` : BUSES[c]);
const laneColor = (c) => (c === MARK ? "--mark" : `--lane-${c % 8}`);

/* --- Settings ------------------------------------------------------------------ */

function renderChannels() {
  const chip = (c, label, extra) => `
    <label style="--c: var(${laneColor(c)})"${c === MARK
      ? ' title="CH13: high while the node holds a board\'s RESET or has it off for a power cycle"' : ""}>
      <input type="checkbox" data-ch="${c}" ${settings.on.includes(c) ? "checked" : ""} aria-label="${label}">
      <b>${label}</b>${extra}</label>`;
  $("la-chans").innerHTML = BUSES.map((b, c) => chip(c, b,
    `<input type="text" data-name="${c}" value="${esc(settings.names[c] ?? "")}" placeholder="${esc(wireNames[c] || "name")}"
            aria-label="Bus ${b}: what it carries" maxlength="24">`)).join("") +
    chip(MARK, "Mark", "<small>node events</small>");
}

function renderSettings() {
  const on = sorted(settings.on);
  panel.renderRate(info.maxRate);
  if (!on.includes(Number(settings.trig.split(":")[0])) && on.length) {
    settings.trig = `${on[0]}:fall`;
  }
  $("la-trig").innerHTML = on.flatMap((c) => ["fall", "rise"].map((e) =>
    `<option value="${c}:${e}" ${`${c}:${e}` === settings.trig ? "selected" : ""}>${esc(chName(c))} ${e === "fall" ? "↓" : "↑"}${
      c === MARK ? (e === "fall" ? " (a board starts)" : " (the node acts)") : ""}</option>`)).join("");
  const n = on.length ? maxSamples(info.buffer, on) : 0;
  const [tc, te] = settings.trig.split(":");
  panel.summary([`${settings.rate / 1e6} MS/s`, fmtTime(n / settings.rate), `trigger ${chName(Number(tc))} ${te === "fall" ? "↓" : "↑"}`,
                 `${on.length} channel${on.length === 1 ? "" : "s"}`]);
  $("la-depth").textContent = on.length
    ? `${n.toLocaleString("en-US")} samples (${bytesPerSample(on) * 8}-bit) · ${fmtTime(n / settings.rate)}`
    : "pick at least one channel";
  panel.save();
  renderAvailability();
}

/* What the buttons can do now: the analyzer this page's, no capture running */
function renderAvailability() {
  const a = status?.analyzer;
  const usable = a?.owner === "page" && a.present && !panel.busy;
  $("la-cap").disabled = !usable || !settings.on.length;
  /* MARK is the DATA x4's: a one-board node (a stand-in) has nothing to trigger on */
  $("la-cap-reset").hidden = !(status?.ports?.length > 1);
  $("la-cap-reset").disabled = !usable || !status.ports?.some((p) => p.power.on);
  $("la-cancel").hidden = !panel.busy;
  for (const r of document.querySelectorAll("input[name=la-owner]")) {
    r.disabled = !!panel.busy;
  }
}

/* --- The card from /api/status ------------------------------------------------------- */

function coprocLine(c) {
  if (!c?.image) {
    return "No analyzer image on the node: bayctl coproc load";
  }
  const l = c.load ?? {};
  return `${esc(c.image.name)} in RAM · ${{
    loaded: `loaded in ${l.last_ms} ms`, started: "starting", loading: "loading…",
    failed: `not loaded: ${esc(l.error ?? "")}`, "left to USB/IP": "left to USB/IP after failed loads",
    idle: "waiting for the co-processor",
  }[l.state] ?? esc(l.state ?? "")}`;
}

function update(s, pageHost) {
  status = s;
  host = pageHost;
  const a = s.analyzer;
  if (!panel.busy) {
    for (const r of document.querySelectorAll("input[name=la-owner]")) {
      r.checked = r.value === a.owner;
    }
  }
  $("la-coproc").innerHTML = coprocLine(s.coproc);

  const other = a.page && a.page.ip !== s.access?.you;
  const note = !a.present
    ? ["The analyzer is not on the bus: no image loaded yet, or the DATA ×4 is off.", "var(--idle)"]
    : a.owner === "usbip"
      ? [`<b>Exported over USB/IP</b> as busid <code>${a.busid}</code>, for gusmanb's desktop app or PulseView.
          This page captures again once you switch it back.`, "var(--usbip)"]
      : other && !panel.busy
        ? [`<b>In use by ${a.page.ip}</b> for ${a.page.since_s} s: it is free again after their capture.`, "var(--lease)"]
        : null;
  $("la-note").hidden = !note;
  if (note) {
    $("la-note").style.setProperty("--c", note[1]);
    $("la-note-text").innerHTML = note[0];
  }
  $("la-usbip").hidden = a.owner !== "usbip" || !a.present;
  $("la-usbip-cmd").textContent = `sudo usbip attach -r ${host} -b ${a.busid}`;
  $("la-meta").textContent = panel.busy ? "capturing" : !a.present ? "not there" : a.owner === "usbip" ? "USB/IP"
                           : capAt ? `last capture ${capAt}` : "ready";
  if (!panel.busy) {
    panel.setState(...(a.owner === "page" && a.present ? outcome ?? ["Ready", "var(--ok)"] : ["–"]));
  }
  renderAvailability();
}

/* --- Capturing ------------------------------------------------------------------------- */

/* Why the node would not open the analyzer, from the last /api/status */
function refusal(e) {
  const a = status?.analyzer;
  return !a?.present ? "The analyzer is not there"
       : a.owner !== "page" ? "USB/IP has it: switch it to This page"
       : a.page && a.page.ip !== status.access?.you ? `In use by ${a.page.ip}` : e.message;
}

const withTimeout = (p, ms, why) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error(why)), ms))]);

/* A capture with the settings; with reset ({port, slot}): triggered as that board leaves reset */
async function capture(reset) {
  const on = sorted(reset ? new Set([...settings.on, MARK]) : settings.on);
  const [tc, te] = reset ? [MARK, "fall"] : settings.trig.split(":");
  const trig = { type: TRIGGER.EDGE, channel: Number(tc), inverted: te === "fall" };
  let t = null;
  panel.begin();
  renderAvailability();
  $("la-meta").textContent = "capturing";
  panel.setState("Opening the analyzer…", "var(--service)");
  try {
    try {
      t = await openRelay();
    } catch (e) {
      throw new Error(refusal(e));
    }
    const analyzer = new Analyzer(t);
    /* A node may also accept the WebSocket, then close it at once: why, from the status */
    info = await withTimeout(analyzer.identify(), 3000, "the analyzer does not answer")
      .catch((e) => Promise.reject(new Error(refusal(e))));
    const total = maxSamples(info.buffer, on), pre = Math.round(total * settings.pre);
    const cap = await panel.read(analyzer, { channels: on, rate: settings.rate, pre, post: total - pre, trigger: trig }, () => {
      if (reset) {
        panel.setState(`Resetting ${reset.slot}…`, "var(--service)");
        api("/api/reset", { port: reset.port })
          .then(() => panel.setState(`Waiting for ${reset.slot} to leave reset`, "var(--service)"))
          .catch((e) => panel.setState(`${reset.slot} not reset: ${e.message}`, "var(--fault)"));
      } else {
        panel.setState(`Waiting for ${chName(trig.channel)} ${te === "fall" ? "↓" : "↑"}`, "var(--service)");
      }
    });
    capReset = reset ?? null;
    capAt = new Date().toLocaleTimeString();
    if (reset && !settings.on.includes(MARK)) {
      settings.on = [...settings.on, MARK];
      renderChannels();
    }
    outcome = [`Captured at ${capAt}`, "var(--ok)"];
    panel.captured(cap);
  } catch (e) {
    const cancelled = e.name === "AbortError";
    outcome = cancelled ? ["Cancelled", "var(--muted)"] : [e.message, "var(--fault)"];
  } finally {
    await t?.close();
    panel.end();
    panel.setState(...outcome);
    renderSettings();
    if (status) {
      update(status, host);
    }
  }
}

/* --- The viewer ------------------------------------------------------------------------- */

/* MARK's pulses as a row under its lane: what the node did, the one this page asked for named */
function markRow(cap) {
  const k = cap.channels.indexOf(MARK);
  if (k < 0) {
    return null;
  }
  /* edges(k): where each run of one level starts; the first run's level is firstLevel(k) */
  const e = cap.edges(k), first = cap.firstLevel(k), items = [];
  for (let i = 0; i < e.length; i++) {
    if ((first ^ (i & 1)) === 1) {
      const t0 = cap.time(e[i]), t1 = cap.time(i + 1 < e.length ? e[i + 1] : cap.count - 1);
      /* The trigger is its fall: the reset this page asked for */
      const asked = capReset && Math.abs(t1) <= 2 / cap.rate;
      items.push({ t0, t1, kind: "ctl", text: asked ? `reset ${capReset.slot}` : "node" });
    }
  }
  return { k, row: { label: "Node", items } };
}

/* --- Wiring ------------------------------------------------------------------------- */

export function mount() {
  panel = new Panel({
    store: "hwtr-bay-analyzer",
    defaults: { on: [0, 1, 2, 3, 4, 5, 6, 7], names: {}, rate: 10e6, pre: 0.2, trig: "0:fall", decoders: [] },
    chName,
    laneName: (k) => chName(panel.cap.channels[k]),
    laneColor,
    moreRows: (cap, rows) => {
      const mark = markRow(cap);
      if (mark) {
        rows.splice(rows.findIndex((r) => r.k === mark.k) + 1, 0, mark.row);
      }
    },
    onShow: () => {
      $("la-view").hidden = false;
      $("la-empty").hidden = true;
    },
    onSettings: renderSettings,
    fileStem: () => (status?.id || "bay").toLowerCase(),
    readColor: "var(--usbip)",
  });
  settings = panel.settings;
  /* The Wires card read the node's names: placeholders here, nothing re-drawn under the typing */
  document.addEventListener("hwtr-wires", (e) => {
    wireNames = e.detail.names ?? [];
    for (const input of $("la-chans").querySelectorAll("input[data-name]")) {
      input.placeholder = wireNames[Number(input.dataset.name)] || "name";
    }
    if (!panel.busy) {
      renderSettings();
      if (panel.cap) {
        panel.show();
      }
    }
  });
  renderChannels();
  renderSettings();
  panel.renderDecoders();

  $("la-trig").addEventListener("change", () => {
    settings.trig = $("la-trig").value;
    renderSettings();
  });

  for (const r of document.querySelectorAll("input[name=la-owner]")) {
    r.addEventListener("change", async () => {
      try {
        status.analyzer = await api("/api/analyzer", { owner: r.value });
        toast(r.value === "usbip" ? "Analyzer exported over USB/IP" : "Analyzer back on this page");
      } catch (e) {
        toast(`Failed: ${e.message}`);
      }
      update(status, host);
    });
  }

  $("la-cap").addEventListener("click", () => capture());
  $("la-reset").addEventListener("beforetoggle", (e) => {
    if (e.newState !== "open") {
      return;
    }
    $("la-reset-ports").innerHTML = (status?.ports ?? []).map((p) =>
      `<button class="small" data-port="${p.port}" data-slot="${esc(p.slot)}" ${p.power.on ? "" : "disabled"}
               title="${p.power.on ? `Reset ${esc(p.slot)} and capture its start` : `${esc(p.slot)} is off`}">${esc(p.slot)}</button>`).join("");
  });
  $("la-reset-ports").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-port]");
    if (b) {
      $("la-reset").hidePopover();
      capture({ port: Number(b.dataset.port), slot: b.dataset.slot });
    }
  });

  return { update };
}
