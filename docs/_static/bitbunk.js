// Small behaviours of the BitBunk documentation.  No dependency, nothing sent anywhere.

document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;

  // The left-hand menu opens on the page you are on, when the section is longer than the window.
  const here = document.querySelector(".bb-nav li.bb-here > a");
  const column = here && here.closest(".sy-scrollbar");
  if (column && here.getBoundingClientRect().bottom > column.getBoundingClientRect().bottom - 48) {
    column.scrollTop = here.offsetTop - column.clientHeight / 3;
  }

  // A still of the 3D model is taken on the paper colour.  In the dark theme its twin on the dark ground is
  // shown, when one exists (_static/viewer-dark/<name>.jpg); the style sheet dims the others.
  const stills = [...document.querySelectorAll(".yue img.bb-still")];
  const base = (root.dataset.content_root || "./") + "_static/viewer-dark/";
  const paint = () => {
    const dark = root.classList.contains("dark");
    stills.forEach((img) => {
      if (!img.dataset.light) img.dataset.light = img.getAttribute("src");
      if (!dark) { img.src = img.dataset.light; img.classList.remove("bb-still-dark"); return; }
      const twin = base + img.dataset.light.split("/").pop().split("?")[0];
      if (img.dataset.twin === "none") return;
      const probe = new Image();
      probe.onload = () => {
        img.dataset.twin = twin;
        if (root.classList.contains("dark")) { img.src = twin; img.classList.add("bb-still-dark"); }
      };
      probe.onerror = () => { img.dataset.twin = "none"; };
      probe.src = twin;
    });
  };
  if (stills.length) {
    paint();
    new MutationObserver(paint).observe(root, { attributes: true, attributeFilter: ["class"] });
  }

  // "Every action, four ways": on a phone each row becomes a short list, each line named by its column.
  document.querySelectorAll(".yue table.bb-ways-table").forEach((table) => {
    if (!table.tHead) return;
    const heads = [...table.tHead.rows[0].cells].map((c) => c.innerText.trim());
    [...table.tBodies].forEach((body) => [...body.rows].forEach((row) =>
      [...row.cells].forEach((cell, i) => { cell.dataset.label = heads[i] || ""; })));
  });

  // Click a drawing or a screenshot (or press Enter on it) to see it at full size; click again, or press
  // Escape, to close.
  document.querySelectorAll(".yue .bb-step-fig img.bb-step-drawing, .yue figure img, .yue img.bb-zoomable")
    .forEach((img) => {
      if (img.closest("a")) return;
      img.dataset.zoom = "1";
      img.tabIndex = 0;
      img.setAttribute("role", "button");
      img.setAttribute("aria-label", (img.alt || "Picture") + ": show at full size");
      const open = () => {
        const layer = document.createElement("div");
        layer.className = "bb-zoom";
        layer.setAttribute("role", "dialog");
        layer.setAttribute("aria-label", img.alt || "Picture");
        layer.tabIndex = -1;
        const big = img.cloneNode();
        ["data-zoom", "style", "width", "height", "tabindex", "role", "aria-label"].forEach((a) => big.removeAttribute(a));
        layer.appendChild(big);
        const onKey = (e) => { if (e.key === "Escape" || e.key === "Enter" || e.key === " ") { e.preventDefault(); close(); } };
        const close = () => { layer.remove(); document.removeEventListener("keydown", onKey); img.focus(); };
        layer.addEventListener("click", close);
        document.addEventListener("keydown", onKey);
        document.body.appendChild(layer);
        layer.focus();
      };
      img.addEventListener("click", open);
      img.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); open(); }
      });
    });

  // Checklists (the bench checks) keep their ticks in this browser, per page.
  const boxes = [...document.querySelectorAll(".yue input.task-list-item-checkbox")];
  if (!boxes.length) return;
  const key = "bitbunk-ticks:" + location.pathname;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) { /* private mode */ }
  const store = () => {
    const state = {};
    boxes.forEach((b, i) => { if (b.checked) state[i] = 1; });
    try { localStorage.setItem(key, JSON.stringify(state)); } catch (e) { /* private mode */ }
  };
  boxes.forEach((b, i) => {
    b.disabled = false;
    if (Object.keys(saved).length) b.checked = Boolean(saved[i]);
    b.addEventListener("change", store);
  });
  const lists = [...document.querySelectorAll(".yue ul.contains-task-list")];
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "bb-ticks-reset";
  reset.textContent = "Clear the ticks on this page";
  reset.addEventListener("click", () => { boxes.forEach((b) => { b.checked = false; }); store(); });
  lists[lists.length - 1].after(reset);
});
