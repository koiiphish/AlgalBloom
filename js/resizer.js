// A draggable divider between the map and the sidebar, so readers can widen the info panel
// (and shrink the map) or the other way round. Works with a mouse, a finger, or the keyboard
// (focus the divider, then use the Left/Right arrow keys; Home/End jump to the limits).
// The chosen width is remembered in this browser for the next visit.

const STORAGE_KEY = "hab-sidebar-width";
const MIN_WIDTH = 320; // px: narrower than this and the panel text gets cramped
const MAX_SHARE = 0.65; // the sidebar may take at most 65% of the window
const KEY_STEP = 30; // px moved per arrow-key press

// Keep a width within the allowed range for the current window size.
function clamp(width) {
  return Math.round(Math.min(Math.max(width, MIN_WIDTH), window.innerWidth * MAX_SHARE));
}

// Connect the divider. `layoutEl` is the grid holding map + divider + sidebar; `onResize`
// is called after every change (the map needs to be told its new size).
export function enableResizer(handle, layoutEl, onResize) {
  // Apply a width: store it as a CSS variable the grid layout uses, and update the
  // divider's accessibility values so screen readers can announce the size.
  function apply(width) {
    const w = clamp(width);
    layoutEl.style.setProperty("--sidebar", `${w}px`);
    handle.setAttribute("aria-valuenow", String(w));
    handle.setAttribute("aria-valuemin", String(MIN_WIDTH));
    handle.setAttribute("aria-valuemax", String(Math.round(window.innerWidth * MAX_SHARE)));
    onResize();
    return w;
  }

  // Remember the width for next time (ignored if the browser blocks storage).
  function save(width) {
    try { localStorage.setItem(STORAGE_KEY, String(width)); } catch { /* storage unavailable */ }
  }

  // Current sidebar width in pixels.
  function current() {
    return layoutEl.querySelector(".sidebar").getBoundingClientRect().width;
  }

  // Start from the saved width, if there is one.
  const saved = Number(localStorage.getItem(STORAGE_KEY));
  if (saved) apply(saved);

  // Dragging: the sidebar's width is the distance from the pointer to the window's right edge.
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add("resizing");
    const move = (ev) => apply(window.innerWidth - ev.clientX);
    const stop = () => {
      handle.removeEventListener("pointermove", move);
      document.body.classList.remove("resizing");
      save(current());
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop, { once: true });
    handle.addEventListener("pointercancel", stop, { once: true });
  });

  // Keyboard: Left widens the sidebar, Right narrows it (the divider moves with the arrow).
  handle.addEventListener("keydown", (e) => {
    const steps = { ArrowLeft: KEY_STEP, ArrowRight: -KEY_STEP };
    let target = null;
    if (e.key in steps) target = current() + steps[e.key];
    if (e.key === "Home") target = MIN_WIDTH;
    if (e.key === "End") target = window.innerWidth * MAX_SHARE;
    if (target == null) return;
    e.preventDefault();
    save(apply(target));
  });

  // Double-click puts the divider back to the default width.
  handle.addEventListener("dblclick", () => {
    layoutEl.style.removeProperty("--sidebar");
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* storage unavailable */ }
    onResize();
  });

  // If the window shrinks, keep the sidebar within the limits.
  window.addEventListener("resize", () => {
    if (layoutEl.style.getPropertyValue("--sidebar")) apply(current());
  });
}
