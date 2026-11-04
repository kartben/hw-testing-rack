/*
 * What the analyzer page (app.mjs) and the bay page's card
 * (bay-node/web/analyzer-card.mjs) share: the settings kept in this browser,
 * the state line, the channels' events, the sample rate and the share before
 * the trigger, the settings folding away after a capture, a capture's
 * progress, the viewer and its tools, the decoded table, the decoders, the
 * .vcd.  Both pages hold the same element ids (la-*), and a #la-view it fills.
 * What stays theirs: how they reach the analyzer, their channels' chips, names
 * and colours, their trigger.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture } from "./capture.mjs";
import { captureRows, decoderFields, decoderFrom, decoderLabel, decoderTypes, entriesOf, esc, matching } from "./decoding.mjs";
import { toVcd } from "./vcd.mjs";
import { Viewer, fmtTime } from "./viewer.mjs";

const $ = (id) => document.getElementById(id);
const RATES = [1e6, 2e6, 5e6, 10e6, 20e6, 25e6, 50e6, 100e6];

const TABLE_ROW = 27; /* px, for the rows it draws: only those in sight */

const VIEW_HTML = `
  <div class="la-viewer">
    <div class="la-vtools">
      <button data-la-zoom="in" aria-label="Zoom in">＋</button>
      <button data-la-zoom="out" aria-label="Zoom out">－</button>
      <button data-la-zoom="fit">Fit</button>
      <button id="la-clear">Clear cursors</button>
      <button id="la-vcd" disabled title="For PulseView, GTKWave and sigrok's decoders">Download .vcd</button>
      <button id="la-full">Full screen</button>
      <span class="la-cap-meta" id="la-cap-meta"></span>
      <output id="la-readout"></output>
    </div>
    <canvas id="la-wave" aria-label="Captured signals, one lane per channel"></canvas>
  </div>
  <div class="la-table" id="la-table" hidden>
    <div class="la-ttools">
      <input type="search" id="la-search" placeholder="Search the decoded data" aria-label="Search the decoded data">
      <span id="la-tcount"></span>
    </div>
    <div class="la-thead" aria-hidden="true"><span>Time</span><span>Decoder</span><span>Data</span><span>Hex</span></div>
    <div class="la-tscroll" id="la-tscroll" tabindex="0" aria-label="Decoded data: the arrows walk through it">
      <div class="la-trows" id="la-trows"></div>
    </div>
  </div>
  <p class="hint">Drag to pan, Ctrl + wheel or pinch to zoom; click for cursor 1, again for cursor 2 and the time
    between them.  A box's value shows on hover.  Once clicked: + and − zoom, ← and → pan, 0 fits, Esc clears the
    cursors.  A row of the table jumps there.</p>`;

/* The viewer's block and the fold: the same on both pages */
const VIEW_CSS = `
#la-fold > summary { cursor: pointer; font-size: 0.88rem; color: var(--muted); font-variant-numeric: tabular-nums; }
#la-fold[open] > summary { margin-bottom: 12px; }
#la-fold > div { display: flex; flex-direction: column; gap: 14px; }
#la-view { display: flex; flex-direction: column; gap: 10px; scroll-margin-top: 12px; min-width: 0; }
#la-view[hidden] { display: none; }
#la-view:fullscreen { background: var(--card); padding: 10px; overflow: auto; }
#la-view .la-viewer { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--card); }
#la-view .la-vtools { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: center; padding: 8px 10px;
  border-bottom: 1px solid var(--line); background: var(--soft); }
#la-view .la-vtools button { padding: 3px 9px; font-size: 0.8rem; border-radius: 8px; font-weight: 500; }
#la-view .la-cap-meta { font-size: 0.78rem; color: var(--muted); }
#la-view output { margin-left: auto; font: 0.78rem var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
#la-view canvas { display: block; width: 100%; touch-action: pan-y; cursor: crosshair; }
#la-view .la-table { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--card); }
#la-view .la-ttools { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 8px 10px;
  border-bottom: 1px solid var(--line); background: var(--soft); font-size: 0.78rem; color: var(--muted); }
#la-view .la-ttools input { font: inherit; font-size: 0.85rem; padding: 4px 8px; border-radius: 8px; color: var(--text);
  border: 1px solid var(--line); background: var(--card); flex: 1 1 200px; min-width: 0; max-width: 360px; }
#la-view .la-thead, #la-view .la-trow { display: grid; align-items: center; gap: 10px; padding-inline: 10px;
  grid-template-columns: 104px minmax(0, 1.2fr) minmax(0, 2fr) 84px; }
#la-view .la-thead { font-size: 0.72rem; font-weight: 600; color: var(--muted); padding-block: 5px;
  border-bottom: 1px solid var(--line); }
#la-view .la-tscroll { height: 216px; overflow-y: auto; position: relative; }
#la-view:fullscreen .la-table { flex: 1 1 26vh; display: flex; flex-direction: column; min-height: 0; }
#la-view:fullscreen .la-tscroll { flex: 1 1 0; height: auto; min-height: 0; }
#la-view:fullscreen .hint { display: none; }
#la-view .la-trows { position: relative; }
#la-view .la-trow { position: absolute; inset-inline: 0; height: ${TABLE_ROW}px; font-size: 0.82rem; cursor: pointer;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 50%, transparent); }
#la-view .la-trow:hover { background: var(--soft); }
#la-view .la-trow[aria-selected=true] { background: color-mix(in srgb, var(--cursor) 16%, transparent); }
#la-view .la-trow.err b { color: var(--fault); }
#la-view .la-trow span, #la-view .la-trow b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 400; }
#la-view .la-trow .t, #la-view .la-trow .x { font-family: var(--mono); font-size: 0.76rem; color: var(--muted);
  font-variant-numeric: tabular-nums; }
#la-view .la-trow .d small { color: var(--muted); }
#la-view .la-trow b { font-family: var(--mono); font-size: 0.78rem; }
@media (max-width: 560px) {
  #la-view output { margin-left: 0; flex-basis: 100%; }
  #la-view .la-thead, #la-view .la-trow { grid-template-columns: 88px minmax(0, 1fr) 70px; }
  #la-view .la-thead :nth-child(2), #la-view .la-trow .d { display: none; }
}`;

export const sorted = (on) => [...on].sort((a, b) => a - b);

export class Panel {
  /*
   * store: the settings' localStorage key, defaults: the settings it does not hold;
   * chName(c): a channel's name; laneName(k): the capture's k-th lane's; laneColor(c): its custom property;
   * moreRows(cap, rows): the page's own rows; onShow(): a capture is on screen; onSettings(): a setting changed;
   * fileStem(): the start of a file's name; readColor: the state line's while a capture is read
   */
  constructor({ store, defaults, chName, laneName, laneColor, moreRows, onShow, onSettings, fileStem, readColor }) {
    Object.assign(this, { store, chName, laneName, laneColor, moreRows, onShow, onSettings, fileStem, readColor });
    this.settings = { ...defaults, ...this.#load() };
    this.cap = null;
    this.busy = null;
    /* The demo brings its own decoders, the user's stay as they are */
    this.ownDecoders = null;
    this.entries = [];
    this.found = [];
    this.picked = null;
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(VIEW_CSS);
    document.adoptedStyleSheets.push(sheet);
    $("la-view").innerHTML = VIEW_HTML;
    this.viewer = new Viewer($("la-wave"), { onReadout: (t) => ($("la-readout").textContent = t) });
    this.#listen();
  }

  #load() {
    try {
      return JSON.parse(localStorage.getItem(this.store) ?? "{}");
    } catch {
      return {};
    }
  }

  save() {
    try {
      localStorage.setItem(this.store, JSON.stringify(this.settings));
    } catch {
      /* private window: settings last as long as the page */
    }
  }

  setState(text, color = "var(--muted)") {
    $("la-state").style.setProperty("--c", color);
    $("la-state").querySelector("span").textContent = text;
  }

  renderRate(maxRate) {
    $("la-rate").innerHTML = RATES.filter((r) => r <= maxRate).map((r) =>
      `<option value="${r}" ${r === this.settings.rate ? "selected" : ""}>${r / 1e6} MS/s</option>`).join("");
    $("la-pre").value = String(this.settings.pre);
  }

  /* The settings in one line, on the fold */
  summary(parts) {
    $("la-sum").textContent = parts.join(" · ");
  }

  get decoders() {
    return this.ownDecoders ?? this.settings.decoders;
  }

  /* --- A capture ------------------------------------------------------------------- */

  begin() {
    this.busy = new AbortController();
  }

  /* The capture, its progress on the state line; throws as Analyzer.capture() does */
  async read(analyzer, request, onStarted) {
    return new Capture(await analyzer.capture(request, {
      signal: this.busy.signal,
      onStarted,
      onData: (got, total) => {
        $("la-prog").hidden = false;
        $("la-prog").value = got / total;
        this.setState(`Reading ${Math.round(got / 1024)} of ${Math.round(total / 1024)} KB`, this.readColor);
      },
    }));
  }

  end() {
    this.busy = null;
    $("la-prog").hidden = true;
  }

  show(cap = this.cap) {
    this.cap = cap;
    const rows = captureRows(cap, this.decoders, this.laneName, this.laneColor);
    this.moreRows?.(cap, rows);
    $("la-cap-meta").textContent = `${cap.count.toLocaleString("en-US")} samples at ${cap.rate / 1e6} MS/s, ` +
                                   `${fmtTime(cap.count / cap.rate)}`;
    $("la-vcd").disabled = false;
    this.onShow?.();
    this.viewer.show(cap, rows);
    this.renderDecoders();
    this.entries = entriesOf(rows);
    this.picked = null;
    this.#renderTable();
  }

  /* A capture to read: the settings fold away, the viewer comes up */
  captured(cap) {
    this.show(cap);
    $("la-fold").open = false;
    $("la-view").scrollIntoView({ block: "start" });
  }

  /* After a change a capture on screen shows */
  refresh() {
    if (this.cap) {
      this.show();
    } else {
      this.renderDecoders();
    }
  }

  /* --- The decoded table ----------------------------------------------------------- */

  #renderTable() {
    this.found = matching(this.entries, $("la-search").value);
    $("la-table").hidden = !this.entries.length;
    const all = this.entries.length, n = this.found.length;
    $("la-tcount").textContent = n === all ? `${all.toLocaleString("en-US")} decoded`
                                           : `${n.toLocaleString("en-US")} of ${all.toLocaleString("en-US")}`;
    $("la-trows").style.height = `${n * TABLE_ROW}px`;
    this.#drawTable();
  }

  #drawTable() {
    const box = $("la-tscroll"), first = Math.floor(box.scrollTop / TABLE_ROW);
    const last = Math.min(this.found.length, first + Math.ceil(box.clientHeight / TABLE_ROW) + 1);
    let html = "";
    for (let i = first; i < last; i++) {
      const e = this.found[i];
      html += `<div class="la-trow${e.it.kind === "err" ? " err" : ""}" style="top: ${i * TABLE_ROW}px" data-i="${i}"
        aria-selected="${e === this.picked}"><span class="t">${fmtTime(e.it.t0)}</span>
        <span class="d">${esc(e.label)}${e.lane ? ` <small>${esc(e.lane)}</small>` : ""}</span>
        <b>${esc(e.it.text ?? "")}</b><span class="x">${e.hex}</span></div>`;
    }
    $("la-trows").innerHTML = html;
  }

  #pick(i) {
    const e = this.found[i];
    if (!e) {
      return;
    }
    this.picked = e;
    const box = $("la-tscroll"), y = i * TABLE_ROW;
    if (y < box.scrollTop) {
      box.scrollTop = y;
    } else if (y + TABLE_ROW > box.scrollTop + box.clientHeight) {
      box.scrollTop = y + TABLE_ROW - box.clientHeight;
    }
    this.#drawTable();
    this.viewer.reveal(e.it);
  }

  /* --- Decoders ------------------------------------------------------------------- */

  renderDecoders() {
    $("la-decs").innerHTML = this.decoders.map((d, i) => `
      <span class="dec-chip">${decoderLabel(d, this.chName)}
        <button class="small" data-remove="${i}" aria-label="Remove this decoder">✕</button></span>`).join("") +
      `<button class="small" id="la-add-dec">+ Decoder</button>`;
  }

  /* The channels a decoder can read: the capture's, else the ones picked for the next */
  #renderDecoderForm() {
    $("la-dec-lines").innerHTML = decoderFields($("la-dec-type").value,
                                                this.cap ? [...this.cap.channels] : sorted(this.settings.on), this.chName);
  }

  /* --- Events ---------------------------------------------------------------------- */

  #listen() {
    const s = this.settings;
    $("la-chans").addEventListener("change", (e) => {
      const c = Number(e.target.dataset.ch);
      if (Number.isInteger(c)) {
        s.on = e.target.checked ? [...new Set([...s.on, c])] : s.on.filter((x) => x !== c);
        this.onSettings();
      }
    });
    $("la-chans").addEventListener("input", (e) => {
      const c = Number(e.target.dataset.name);
      if (Number.isInteger(c)) {
        s.names[c] = e.target.value.trim();
        this.onSettings();
        if (this.cap) {
          this.show();
        }
      }
    });
    for (const id of ["la-rate", "la-pre"]) {
      $(id).addEventListener("change", () => {
        s.rate = Number($("la-rate").value);
        s.pre = Number($("la-pre").value);
        this.onSettings();
      });
    }
    $("la-cancel").addEventListener("click", () => this.busy?.abort());

    $("la-decs").addEventListener("click", (e) => {
      const rm = e.target.closest("[data-remove]");
      if (rm) {
        this.decoders.splice(Number(rm.dataset.remove), 1);
        this.save();
        this.refresh();
      } else if (e.target.closest("#la-add-dec")) {
        $("la-dec-type").innerHTML = decoderTypes();
        this.#renderDecoderForm();
        $("la-dec-dlg").showModal();
      }
    });
    $("la-dec-type").addEventListener("change", () => this.#renderDecoderForm());
    $("la-dec-form").addEventListener("submit", (e) => {
      e.preventDefault();
      if (e.submitter?.value === "cancel") {
        $("la-dec-dlg").close();
        return;
      }
      this.decoders.push(decoderFrom($("la-dec-type").value, $("la-dec-lines")));
      this.save();
      $("la-dec-dlg").close();
      this.refresh();
    });

    for (const b of document.querySelectorAll("[data-la-zoom]")) {
      b.addEventListener("click", () => (b.dataset.laZoom === "fit" ? this.viewer.fit()
                                                                    : this.viewer.zoom(b.dataset.laZoom === "in" ? 0.5 : 2)));
    }
    $("la-clear").addEventListener("click", () => this.viewer.clearCursors());
    $("la-full").addEventListener("click", () => (document.fullscreenElement ? document.exitFullscreen()
                                                                             : $("la-view").requestFullscreen()));
    document.addEventListener("fullscreenchange", () => {
      const full = !!document.fullscreenElement;
      $("la-full").textContent = full ? "Leave full screen" : "Full screen";
      /* The window less the tools, the table and their margins */
      this.viewer.height = full ? innerHeight * 0.74 - 170 : null;
      this.viewer.draw();
      this.#drawTable();
    });
    $("la-search").addEventListener("input", () => {
      $("la-tscroll").scrollTop = 0;
      this.#renderTable();
    });
    $("la-tscroll").addEventListener("scroll", () => this.#drawTable());
    $("la-trows").addEventListener("click", (e) => {
      const row = e.target.closest("[data-i]");
      if (row) {
        this.#pick(Number(row.dataset.i));
      }
    });
    $("la-tscroll").addEventListener("keydown", (e) => {
      const step = { ArrowDown: 1, ArrowUp: -1 }[e.key];
      if (step) {
        e.preventDefault();
        const at = this.found.indexOf(this.picked);
        this.#pick(at < 0 ? 0 : Math.min(this.found.length - 1, Math.max(0, at + step)));
      }
    });
    $("la-vcd").addEventListener("click", () => {
      const cap = this.cap;
      const url = URL.createObjectURL(new Blob([toVcd(cap, cap.channels.map((_, k) => this.laneName(k)))],
                                               { type: "text/plain" }));
      const a = Object.assign(document.createElement("a"), {
        href: url, download: `${this.fileStem()}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.vcd`,
      });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
}
