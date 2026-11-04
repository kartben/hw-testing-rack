/*
 * The capture on a canvas: one lane per channel, decoded rows under them (a
 * row's items: {t0, t1, text, kind, value}), time from the trigger.  Drag to
 * pan, Ctrl + wheel or pinch to zoom, click for cursor 1, click again for
 * cursor 2; a box's value shows on hover.  With the canvas focused: + and -
 * zoom, the arrows pan (Shift: further), 0 fits, Esc clears the cursors.
 * Colours are CSS custom properties, resolved by
 * the browser (light-dark() included): a lane's own (--lane-0 to --lane-7,
 * the resistor colour code, CH1 brown), --text, --muted, --grid, --card,
 * --trigger, --cursor, --dec-data, --dec-addr, --dec-ctl, --dec-text.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

const RH = 26;     /* row height */
const TOP = 22;    /* the time axis */

/* The first index whose value is past v (a in ascending order) */
function upperBound(a, v) {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (a[mid] <= v) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

export function fmtTime(s) {
  const a = Math.abs(s);
  return a >= 1 ? `${s.toFixed(3)} s` : a >= 1e-3 ? `${(s * 1e3).toFixed(3)} ms`
       : a >= 1e-6 ? `${(s * 1e6).toFixed(2)} µs` : `${(s * 1e9).toFixed(0)} ns`;
}

/* The item at t, items in time order; slack (seconds) makes a thin box easier to hit */
export function itemAt(items, t, slack = 0) {
  let lo = 0, hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (items[mid].t1 + slack < t) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  const it = items[lo];
  return it && it.t0 - slack <= t ? it : null;
}

/* A decoded value as hex and decimal, and in binary while it is short */
export function valueText(v) {
  const hex = `0x${v.toString(16).toUpperCase().padStart(2, "0")}`;
  return v < 256 ? `${hex} · ${v} · 0b${v.toString(2).padStart(8, "0")}` : `${hex} · ${v}`;
}

/* What the tooltip says about an item, line by line */
export function itemLines(it) {
  return [it.text, ...(it.value === undefined ? [] : [valueText(it.value)]),
          `${fmtTime(it.t0)}, lasts ${fmtTime(it.t1 - it.t0)}`];
}

export class Viewer {
  constructor(canvas, { onReadout } = {}) {
    this.cv = canvas;
    this.onReadout = onReadout ?? (() => {});
    this.cap = null;
    this.rows = [];
    this.view = { t0: 0, t1: 1 };
    this.cursors = [];
    this.hover = null;
    this.touches = new Map();
    this.drag = null;
    /* A canvas cannot read light-dark(): an element computes the colours */
    this.probe = document.createElement("span");
    this.probe.hidden = true;
    canvas.after(this.probe);
    this.tip = document.createElement("div");
    this.tip.hidden = true;
    this.tip.style.cssText = "position: fixed; z-index: 10; pointer-events: none; white-space: pre; padding: 5px 8px; " +
      "border-radius: 8px; border: 1px solid var(--line); background: var(--card); color: var(--text); " +
      "font: 11.5px/1.45 var(--mono); box-shadow: 0 4px 16px #0003;";
    canvas.after(this.tip);
    canvas.tabIndex = 0;
    this.#listen();
    new ResizeObserver(() => this.draw()).observe(canvas);
    globalThis.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", () => this.draw());
    new MutationObserver(() => this.draw()).observe(document.documentElement,
                                                    { attributes: true, attributeFilter: ["data-theme"] });
  }

  /* rows: {k, name, color} for channel lanes (k: index in cap.channels, color a custom property such as
   * "--lane-0"), {label, items} for decoded rows */
  show(cap, rows) {
    const keep = this.cap && cap && this.cap.rate === cap.rate && this.cap.count === cap.count;
    this.cap = cap;
    this.rows = rows;
    if (!keep) {
      this.cursors = [];
      this.fit();
    } else {
      this.draw();
    }
  }

  get span() {
    return this.cap ? [this.cap.time(0), this.cap.time(this.cap.count - 1)] : [0, 1];
  }

  fit() {
    const [a, b] = this.span;
    this.view = { t0: a, t1: b > a ? b : a + 1e-6 };
    this.draw();
  }

  /* Show [t0, t1] (seconds from the trigger), within the capture */
  setRange(t0, t1) {
    this.view = { t0, t1 };
    this.#clamp();
    this.draw();
  }

  zoom(k, at) {
    const v = this.view, t = at ?? (v.t0 + v.t1) / 2;
    const [a, b] = this.span;
    const minSpan = this.cap ? 8 / this.cap.rate : 1e-9;
    const w = Math.min(b - a, Math.max(minSpan, (v.t1 - v.t0) * k));
    const t0 = t - (t - v.t0) * w / (v.t1 - v.t0);
    this.view = { t0, t1: t0 + w };
    this.#clamp();
    this.draw();
  }

  /* Move the view by this share of its width */
  pan(share) {
    const v = this.view, dt = (v.t1 - v.t0) * share;
    this.setRange(v.t0 + dt, v.t1 + dt);
  }

  clearCursors() {
    this.cursors = [];
    this.draw();
  }

  #clamp() {
    const [a, b] = this.span, w = Math.min(this.view.t1 - this.view.t0, b - a);
    const t0 = Math.min(Math.max(a, this.view.t0), b - w);
    this.view = { t0, t1: t0 + w };
  }

  #labelW() {
    return Math.min(150, this.cv.clientWidth * 0.3);
  }

  #tAt(px) {
    const L = this.#labelW(), W = this.cv.clientWidth - L - 8;
    return this.view.t0 + (px - L) / W * (this.view.t1 - this.view.t0);
  }

  /* The box under the pointer, in its tooltip */
  #showTip(e, r) {
    const px = e.clientX - r.left, row = this.rows[Math.floor((e.clientY - r.top - TOP) / RH)];
    const L = this.#labelW(), W = this.cv.clientWidth - L - 8;
    const it = !this.drag?.moved && this.cap && px > L && row?.items
      ? itemAt(row.items, this.#tAt(px), 3 / W * (this.view.t1 - this.view.t0)) : null;
    this.tip.hidden = !it;
    if (it) {
      this.tip.textContent = itemLines(it).join("\n");
      const room = (a, size, max) => (a + 14 + size > max ? Math.max(0, a - 14 - size) : a + 14);
      this.tip.style.left = `${room(e.clientX, this.tip.offsetWidth, innerWidth)}px`;
      this.tip.style.top = `${room(e.clientY, this.tip.offsetHeight, innerHeight)}px`;
    }
  }

  #key(e) {
    const act = { "+": () => this.zoom(0.5), "=": () => this.zoom(0.5), "-": () => this.zoom(2), "_": () => this.zoom(2),
                  ArrowLeft: () => this.pan(e.shiftKey ? -1 : -0.25), ArrowRight: () => this.pan(e.shiftKey ? 1 : 0.25),
                  0: () => this.fit(), Escape: () => this.clearCursors() }[e.key];
    if (act && this.cap && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      act();
    }
  }

  #listen() {
    const cv = this.cv;
    cv.addEventListener("keydown", (e) => this.#key(e));
    cv.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) {
        return;
      }
      e.preventDefault();
      const r = cv.getBoundingClientRect();
      this.zoom(e.deltaY > 0 ? 1.25 : 0.8, this.#tAt(e.clientX - r.left));
    }, { passive: false });
    cv.addEventListener("pointerdown", (e) => {
      this.touches.set(e.pointerId, e.clientX);
      cv.setPointerCapture(e.pointerId);
      this.drag = this.touches.size === 1 ? { x: e.clientX, v: { ...this.view }, moved: false } : null;
    });
    cv.addEventListener("pointermove", (e) => {
      const r = cv.getBoundingClientRect();
      if (this.touches.size === 2 && this.touches.has(e.pointerId)) {
        const [a, b] = [...this.touches.values()], d0 = Math.abs(a - b);
        this.touches.set(e.pointerId, e.clientX);
        const [c, d] = [...this.touches.values()], d1 = Math.abs(c - d);
        if (d0 > 10 && d1 > 10) {
          this.zoom(d0 / d1, this.#tAt((c + d) / 2 - r.left));
        }
        return;
      }
      if (this.drag && Math.abs(e.clientX - this.drag.x) > 3) {
        this.drag.moved = true;
        const dt = this.#tAt(this.drag.x - r.left) - this.#tAt(e.clientX - r.left);
        this.view = { t0: this.drag.v.t0 + dt, t1: this.drag.v.t1 + dt };
        this.#clamp();
      }
      this.hover = this.#tAt(e.clientX - r.left);
      this.#showTip(e, r);
      this.draw();
    });
    cv.addEventListener("pointerup", (e) => {
      const r = cv.getBoundingClientRect();
      if (this.drag && !this.drag.moved && this.cap && e.clientX - r.left > this.#labelW()) {
        const t = this.#tAt(e.clientX - r.left);
        this.cursors = this.cursors.length >= 2 ? [t] : [...this.cursors, t];
        this.draw();
      }
      this.touches.delete(e.pointerId);
      this.drag = null;
    });
    cv.addEventListener("pointercancel", (e) => {
      this.touches.delete(e.pointerId);
      this.drag = null;
    });
    cv.addEventListener("pointerleave", () => {
      this.tip.hidden = true;
      if (!this.drag) {
        this.hover = null;
        this.draw();
      }
    });
  }

  draw() {
    const cv = this.cv;
    if (!cv.clientWidth) {
      return;
    }
    const colors = new Map();
    const css = (name) => {
      if (!colors.has(name)) {
        this.probe.style.color = `var(${name})`;
        colors.set(name, getComputedStyle(this.probe).color);
      }
      return colors.get(name);
    };
    const style = getComputedStyle(cv);
    const mono = style.getPropertyValue("--mono").trim() || "ui-monospace, monospace";
    const sans = style.getPropertyValue("--sans").trim() || "system-ui, sans-serif";
    const dpr = globalThis.devicePixelRatio || 1, Wd = cv.clientWidth, L = this.#labelW();
    const H = TOP + Math.max(1, this.rows.length) * RH + 8, W = Wd - L - 8;
    cv.style.height = `${H}px`;
    cv.width = Math.round(Wd * dpr);
    cv.height = Math.round(H * dpr);
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = css("--card");
    g.fillRect(0, 0, Wd, H);
    const { t0, t1 } = this.view;
    const x = (t) => L + (t - t0) / (t1 - t0) * W;

    /* Time grid */
    const span = t1 - t0, step = 10 ** Math.floor(Math.log10(span / 6));
    const nice = [1, 2, 5, 10].map((m) => m * step).find((s) => span / s <= Math.max(3, W / 95)) || step * 10;
    g.font = `10.5px ${mono}`;
    g.lineWidth = 1;
    for (let t = Math.ceil(t0 / nice) * nice; t <= t1; t += nice) {
      const X = x(t);
      g.strokeStyle = css("--grid");
      g.beginPath();
      g.moveTo(X, TOP - 4);
      g.lineTo(X, H - 4);
      g.stroke();
      g.fillStyle = css("--muted");
      const label = fmtTime(Math.abs(t) < nice / 1e6 ? 0 : t);
      if (X + 3 + g.measureText(label).width <= Wd) {
        g.fillText(label, X + 3, 12);
      }
    }
    if (!this.cap) {
      g.fillStyle = css("--muted");
      g.font = `13px ${sans}`;
      g.fillText("No capture yet.", L, TOP + 24);
    }

    this.rows.forEach((r, i) => {
      const y = TOP + i * RH, hi = y + 5, lo = y + RH - 7;
      g.save();
      g.beginPath();
      g.rect(0, y, L - 8, RH);
      g.clip();
      if (r.items) {
        g.fillStyle = css("--muted");
        g.font = `11px ${sans}`;
        g.fillText(r.label, 26, y + RH / 2 + 4);
      } else {
        g.fillStyle = css(r.color);
        g.beginPath();
        g.arc(12, y + RH / 2, 4.5, 0, 7);
        g.fill();
        g.fillStyle = css("--text");
        g.font = `12px ${sans}`;
        g.fillText(r.name, 24, y + RH / 2 + 4);
      }
      g.restore();
      if (!this.cap) {
        return;
      }
      g.save();
      g.beginPath();
      g.rect(L, y, W, RH);
      g.clip();
      if (r.items) {
        this.#drawItems(g, r.items, x, y, css, mono);
      } else {
        this.#drawLane(g, r, css(r.color), x, hi, lo);
      }
      g.restore();
    });

    if (this.cap && t0 <= 0 && t1 >= 0) {
      const X = x(0);
      g.strokeStyle = css("--trigger");
      g.setLineDash([3, 3]);
      g.beginPath();
      g.moveTo(X, TOP - 6);
      g.lineTo(X, H);
      g.stroke();
      g.setLineDash([]);
      g.fillStyle = css("--trigger");
      g.beginPath();
      g.moveTo(X - 5, TOP - 8);
      g.lineTo(X + 5, TOP - 8);
      g.lineTo(X, TOP - 2);
      g.fill();
    }
    this.cursors.forEach((c, i) => {
      if (c < t0 || c > t1) {
        return;
      }
      const X = x(c);
      g.strokeStyle = css("--cursor");
      g.beginPath();
      g.moveTo(X, TOP - 6);
      g.lineTo(X, H);
      g.stroke();
      g.fillStyle = css("--cursor");
      g.font = `600 10px ${sans}`;
      g.fillText(String(i + 1), X + 3, TOP + 2);
    });

    let ro = `${fmtTime(t0)} … ${fmtTime(t1)}`;
    if (this.cursors.length === 2) {
      const d = Math.abs(this.cursors[1] - this.cursors[0]);
      ro += ` · Δt ${fmtTime(d)} (${d > 0 ? (1 / d >= 1e6 ? `${(1 / d / 1e6).toFixed(3)} MHz`
                                                          : `${(1 / d / 1e3).toFixed(3)} kHz`) : "–"})`;
    } else if (this.hover !== null && this.cap) {
      ro += ` · ${fmtTime(this.hover)}`;
    }
    this.onReadout(ro);
  }

  /* A channel's level changes; several in one pixel column draw a bar */
  #drawLane(g, r, color, x, hi, lo) {
    const cap = this.cap, e = cap.edges(r.k), { t0, t1 } = this.view;
    const i0 = Math.max(0, Math.floor(cap.index(t0))), i1 = Math.min(cap.count - 1, Math.ceil(cap.index(t1)));
    const L = x(t0), R = x(t1);
    let m = upperBound(e, i0);
    let lv = cap.firstLevel(r.k) ^ ((m - 1) & 1);
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    g.beginPath();
    g.moveTo(L, lv ? hi : lo);
    while (m < e.length && e[m] <= i1) {
      const px = Math.floor(x(cap.time(e[m])));
      /* The changes in this pixel column: up to the first sample of the next one */
      const tNext = t0 + (px + 1 - L) / (R - L) * (t1 - t0);
      const m2 = Math.max(m + 1, upperBound(e, Math.ceil(tNext * cap.rate + cap.pre) - 1));
      const n = m2 - m;
      g.lineTo(px, lv ? hi : lo);
      if (n === 1) {
        lv ^= 1;
        g.lineTo(px, lv ? hi : lo);
      } else {
        g.lineTo(px, hi);
        g.lineTo(px, lo);
        lv ^= n & 1;
        g.lineTo(px, lv ? hi : lo);
      }
      m = m2;
    }
    g.lineTo(R, lv ? hi : lo);
    g.stroke();
  }

  #drawItems(g, items, x, y, css, mono) {
    const { t0, t1 } = this.view;
    for (const it of items) {
      if (it.t1 < t0 || it.t0 > t1) {
        continue;
      }
      const X0 = Math.max(x(t0), x(it.t0)), X1 = Math.min(x(t1), x(it.t1));
      g.fillStyle = it.color ?? css(`--dec-${it.kind ?? "data"}`);
      g.beginPath();
      g.roundRect(X0, y + 4, Math.max(1, X1 - X0 - 1), RH - 8, 4);
      g.fill();
      if (it.text && X1 - X0 > 14) {
        g.fillStyle = it.color ? (it.light ? "#111" : "#fff") : css("--dec-text");
        g.font = `10.5px ${mono}`;
        g.save();
        g.beginPath();
        g.rect(X0 + 2, y, X1 - X0 - 4, RH);
        g.clip();
        g.fillText(it.text, X0 + 5, y + RH / 2 + 3.5);
        g.restore();
      }
    }
  }
}
