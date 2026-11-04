/*
 * What the analyzer page (app.mjs) and the bay page's card
 * (bay-node/web/analyzer-card.mjs) share: the settings kept in this browser,
 * the state line, the channels' events, the sample rate and the share before
 * the trigger, the settings folding away after a capture, a capture's
 * progress, the viewer and its tools, the decoders, the .vcd.  Both pages hold the same element ids (la-*), and a #la-view it fills.
 * What stays theirs: how they reach the analyzer, their channels' chips, names
 * and colours, their trigger.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { Capture } from "./capture.mjs";
import { captureRows, decoderFields, decoderFrom, decoderLabel, decoderTypes } from "./decoding.mjs";
import { toVcd } from "./vcd.mjs";
import { Viewer, fmtTime } from "./viewer.mjs";

const $ = (id) => document.getElementById(id);
const RATES = [1e6, 2e6, 5e6, 10e6, 20e6, 25e6, 50e6, 100e6];

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
  <p class="hint">Drag to pan, Ctrl + wheel or pinch to zoom; click for cursor 1, again for cursor 2 and the time
    between them.  A box's value shows on hover.  Once clicked: + and − zoom, ← and → pan, 0 fits, Esc clears the
    cursors.</p>`;

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
@media (max-width: 560px) {
  #la-view output { margin-left: 0; flex-basis: 100%; }
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
      /* The window less the tools and their margins */
      this.viewer.height = full ? innerHeight - 90 : null;
      this.viewer.draw();
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
