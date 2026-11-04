/*
 * What the viewer shows for a capture: a lane per channel and, under the
 * last lane each decoder reads, the decoder's rows; and the form that adds a
 * decoder.  Shared by the analyzer page (app.mjs) and the bay page's card
 * (bay-node/web/analyzer-card.mjs).  Channel names are the user's: escaped.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { BAUDS, CAN_RATES, DECODERS } from "./decoders.mjs";

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

/* A decoder's rows, under the last lane it reads; a decoder that cannot run says why */
export function decode(cap, d) {
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

/* The viewer's rows: lane k named name(k), coloured color(channel); each decoder's rows under its lane */
export function captureRows(cap, decoders, name, color = (c) => `--lane-${c % 8}`) {
  const decoded = decoders.map((d) => decode(cap, d));
  const rows = [];
  cap.channels.forEach((c, k) => {
    rows.push({ k, name: name(k), color: color(c) });
    for (const d of decoded.filter((x) => x.anchor === k)) {
      rows.push(...d.rows.map((r) => ({ ...r, lane: name(k) })));
    }
  });
  return rows;
}

/* Samples a bit: what reads a known speed well; a UART's decoder stops under 4 */
const GOOD_UART = 10;
const WS2812_RATE = 10e6;
const ONEWIRE_RATE = 1e6;
/* Samples a bit for CAN, whose decoder stops under 4 */
const GOOD_CAN = 10;
/* A clock pulse this many samples wide or less is hardly seen */
const THIN_PULSE = 2;

/* What these decoders ask of a rate, known before the capture: [{text, need}], need in samples per second */
export function rateNeeds(decoders, rate) {
  const out = [];
  for (const d of decoders) {
    const need = d.type === "uart" ? (d.baud ?? 115200) * GOOD_UART : d.type === "ws2812" ? WS2812_RATE
               : d.type === "onewire" ? ONEWIRE_RATE : d.type === "can" ? (d.baud ?? 500000) * GOOD_CAN : 0;
    if (rate < need) {
      const what = d.type === "uart" ? `UART at ${(d.baud ?? 115200).toLocaleString("en-US")} Bd` : DECODERS[d.type].name;
      out.push({ text: `${what} reads well from ${need / 1e6} MS/s up, ${rate / 1e6} MS/s is low.`, need });
    }
  }
  return out;
}

/* What a capture says of its rate, for the clocks whose speed nobody asked: [{text, need}] */
export function captureNotes(cap, decoders, chName) {
  const out = [];
  for (const d of decoders) {
    const c = d.type === "i2c" ? d.lines.scl : d.type === "spi" ? d.lines.sck : d.type === "pwm" ? d.lines.in : undefined;
    const k = c === undefined || c === null ? -1 : cap.channels.indexOf(c);
    const e = k < 0 ? [] : cap.edges(k);
    let thin = Infinity;
    for (let i = 2; i < e.length; i++) {
      thin = Math.min(thin, e[i] - e[i - 1]);
    }
    if (thin <= THIN_PULSE) {
      out.push({ text: `${chName(c)}'s shortest pulse is ${thin} sample${thin === 1 ? "" : "s"} wide: ` +
                       `${DECODERS[d.type].name} may read wrong at ${cap.rate / 1e6} MS/s.`,
                 need: cap.rate * (THIN_PULSE + 2) / thin });
    }
  }
  return out;
}

/* A decoded value in hex */
export const hexOf = (v) => (v === undefined ? "" : `0x${v.toString(16).toUpperCase().padStart(2, "0")}`);

/*
 * The viewer's rows as the table's list, in time order: {it, items, label, lane, hex, hay}.  it: what the row says, a
 * row's frame or its box; items: the boxes it marks in the viewer; hay: what a search looks in, both hex spellings.
 */
export function entriesOf(rows) {
  return rows.filter((r) => r.items).flatMap((r) => (r.frames ?? r.items).map((it) => {
    const hex = it.hex ?? hexOf(it.value);
    return { it, items: it.items ?? [it], label: r.label, lane: r.lane ?? "", hex,
             hay: `${it.text} ${hex} ${hex.replace(/\b(?=[0-9A-F]{2}\b)/g, "0x")} ${r.label} ${r.lane ?? ""}`.toLowerCase() };
  })).sort((a, b) => a.it.t0 - b.it.t0);
}

/* The entries a search keeps: every word found, in any case */
export function matching(entries, query) {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return words.length ? entries.filter((e) => words.every((w) => e.hay.includes(w))) : entries;
}

/* A decoder in a few words, as HTML: "<b>UART</b> RX TX line · 115,200 Bd" (chName(c): a channel's name) */
export function decoderLabel(d, chName) {
  const lines = Object.entries(d.lines).filter(([, c]) => c !== null && c !== undefined)
    .map(([role, c]) => `${role.toUpperCase()} ${esc(chName(c))}`).join(", ");
  return `<b>${DECODERS[d.type].name}</b> ${lines}` +
    (d.type === "can" ? ` · ${(d.baud ?? 500000) / 1e3} kbit/s`
                      : d.baud ? ` · ${d.baud >= 1e6 ? `${d.baud / 1e6} M` : `${d.baud} `}Bd` : "") +
    (d.type === "spi" ? ` · mode ${d.mode ?? 0}` : "");
}

export const decoderTypes = () =>
  Object.entries(DECODERS).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("");

/* The form's fields for a decoder of this type over these channels */
export function decoderFields(type, chans, chName) {
  const spec = DECODERS[type];
  return spec.lines.map((line, i) => {
    const role = line.replace("?", ""), optional = line.endsWith("?");
    return `<label>${role.toUpperCase()}${optional ? " (optional)" : ""}
      <select data-line="${role}">${optional ? '<option value="">none</option>' : ""}${chans.map((c) =>
        `<option value="${c}" ${!optional && chans[i] === c ? "selected" : ""}>${esc(chName(c))}</option>`).join("")}</select></label>`;
  }).join("") + (type === "uart" ? `<label>Baud rate <select data-baud>${BAUDS.map((b) =>
    `<option value="${b}" ${b === 115200 ? "selected" : ""}>${b.toLocaleString("en-US")}</option>`).join("")}</select></label>` : "")
    + (type === "can" ? `<label>Bit rate <select data-baud>${CAN_RATES.map((b) =>
    `<option value="${b}" ${b === 500000 ? "selected" : ""}>${b / 1e3} kbit/s</option>`).join("")}</select></label>` : "")
    + (type === "spi" ? `<label>Mode <select data-mode>${[0, 1, 2, 3].map((m) =>
    `<option value="${m}">${m}</option>`).join("")}</select></label>` : "");
}

/* The decoder those fields (in root) describe */
export function decoderFrom(type, root) {
  const d = { type, lines: {} };
  for (const sel of root.querySelectorAll("select[data-line]")) {
    d.lines[sel.dataset.line] = sel.value === "" ? null : Number(sel.value);
  }
  if (type === "uart" || type === "can") {
    d.baud = Number(root.querySelector("[data-baud]").value);
  }
  if (type === "spi") {
    d.mode = Number(root.querySelector("[data-mode]").value);
  }
  return d;
}
