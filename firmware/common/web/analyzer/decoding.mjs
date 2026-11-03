/*
 * What the viewer shows for a capture: a lane per channel and, under the
 * last lane each decoder reads, the decoder's rows; and the form that adds a
 * decoder.  Shared by the analyzer page (app.mjs) and the bay page's card
 * (bay-node/web/analyzer-card.mjs).  Channel names are the user's: escaped.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { BAUDS, DECODERS } from "./decoders.mjs";

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
      rows.push(...d.rows);
    }
  });
  return rows;
}

/* A decoder in a few words, as HTML: "<b>UART</b> RX TX line · 115,200 Bd" (chName(c): a channel's name) */
export function decoderLabel(d, chName) {
  const lines = Object.entries(d.lines).filter(([, c]) => c !== null && c !== undefined)
    .map(([role, c]) => `${role.toUpperCase()} ${esc(chName(c))}`).join(", ");
  return `<b>${DECODERS[d.type].name}</b> ${lines}` +
    (d.baud ? ` · ${d.baud >= 1e6 ? `${d.baud / 1e6} M` : `${d.baud} `}Bd` : "") +
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
    + (type === "spi" ? `<label>Mode <select data-mode>${[0, 1, 2, 3].map((m) =>
    `<option value="${m}">${m}</option>`).join("")}</select></label>` : "");
}

/* The decoder those fields (in root) describe */
export function decoderFrom(type, root) {
  const d = { type, lines: {} };
  for (const sel of root.querySelectorAll("select[data-line]")) {
    d.lines[sel.dataset.line] = sel.value === "" ? null : Number(sel.value);
  }
  if (type === "uart") {
    d.baud = Number(root.querySelector("[data-baud]").value);
  }
  if (type === "spi") {
    d.mode = Number(root.querySelector("[data-mode]").value);
  }
  return d;
}
