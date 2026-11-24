// Small behaviours of the BitBunk documentation.  No dependency, nothing sent anywhere.

document.addEventListener("DOMContentLoaded", () => {
  // Click a drawing or a screenshot to see it at full size; click again, or press Escape, to close.
  document.querySelectorAll(".yue .bb-step-fig img.bb-step-drawing, .yue figure img, .yue img.bb-zoomable")
    .forEach((img) => {
      if (img.closest("a")) return;
      img.dataset.zoom = "1";
      img.addEventListener("click", () => {
        const layer = document.createElement("div");
        layer.className = "bb-zoom";
        const big = img.cloneNode();
        ["data-zoom", "style", "width", "height"].forEach((a) => big.removeAttribute(a));
        layer.appendChild(big);
        const onKey = (e) => { if (e.key === "Escape") close(); };
        const close = () => { layer.remove(); document.removeEventListener("keydown", onKey); };
        layer.addEventListener("click", close);
        document.addEventListener("keydown", onKey);
        document.body.appendChild(layer);
      });
    });

  // Checklists (the bring-up pages) keep their ticks in this browser, per page.
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
