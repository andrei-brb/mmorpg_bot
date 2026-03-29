/**
 * Visual layout editor: drag & resize regions marked with [data-layout-id].
 * Persists to localStorage (per browser). Call refresh() after tab content is re-rendered.
 */

const STORAGE_KEY = "wod-activity-ui-layout-v1";

export type LayoutRect = {
  /** Position & size as % of offset parent (0–100) */
  x: number;
  y: number;
  w: number;
  h: number;
};

function loadAll(): Record<string, LayoutRect> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const o = JSON.parse(raw) as Record<string, LayoutRect>;
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

function saveAll(data: Record<string, LayoutRect>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* ignore quota */
  }
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function clearInlineLayout(el: HTMLElement): void {
  el.style.position = "";
  el.style.left = "";
  el.style.top = "";
  el.style.width = "";
  el.style.height = "";
  el.style.zIndex = "";
  el.classList.remove("ui-layout--positioned");
}

function applyRect(el: HTMLElement, r: LayoutRect): void {
  el.classList.add("ui-layout--positioned");
  el.style.position = "absolute";
  el.style.left = `${clamp(r.x, 0, 100)}%`;
  el.style.top = `${clamp(r.y, 0, 100)}%`;
  el.style.width = `${clamp(r.w, 4, 100)}%`;
  el.style.height = `${clamp(r.h, 4, 100)}%`;
  el.style.boxSizing = "border-box";
  if (!el.style.zIndex) el.style.zIndex = "2";
}

/** Convert element box to % of parent content box. */
function toPercent(el: HTMLElement, parent: HTMLElement): LayoutRect {
  const er = el.getBoundingClientRect();
  const pr = parent.getBoundingClientRect();
  const pw = pr.width || 1;
  const ph = pr.height || 1;
  return {
    x: ((er.left - pr.left) / pw) * 100,
    y: ((er.top - pr.top) / ph) * 100,
    w: (er.width / pw) * 100,
    h: (er.height / ph) * 100,
  };
}

let editMode = false;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
let rootRef: HTMLElement | null = null;
let toolbarEl: HTMLElement | null = null;
let observer: MutationObserver | null = null;

function ensureToolbar(root: HTMLElement): HTMLElement {
  if (toolbarEl && toolbarEl.isConnected) return toolbarEl;
  const bar = document.createElement("div");
  bar.className = "ui-layout-toolbar";
  bar.innerHTML = `
    <button type="button" class="ui-layout-toolbar__main" data-layout-toggle>Edit UI</button>
    <span class="ui-layout-toolbar__hint">Drag headers · corner to resize</span>
    <button type="button" class="ui-layout-toolbar__btn" data-layout-reset hidden>Reset layout</button>
    <button type="button" class="ui-layout-toolbar__btn" data-layout-done hidden>Done</button>
  `;
  root.appendChild(bar);
  toolbarEl = bar;

  bar.querySelector("[data-layout-toggle]")?.addEventListener("click", () => {
    setEditMode(!editMode, root);
  });
  bar.querySelector("[data-layout-done]")?.addEventListener("click", () => {
    setEditMode(false, root);
  });
  bar.querySelector("[data-layout-reset]")?.addEventListener("click", () => {
    saveAll({});
    applyLayout(root);
    setEditMode(false, root);
  });

  return bar;
}

function setEditMode(on: boolean, root: HTMLElement): void {
  editMode = on;
  document.body.classList.toggle("ui-layout-edit", on);
  const bar = ensureToolbar(root);
  const toggle = bar.querySelector<HTMLButtonElement>("[data-layout-toggle]");
  const done = bar.querySelector<HTMLButtonElement>("[data-layout-done]");
  const reset = bar.querySelector<HTMLButtonElement>("[data-layout-reset]");
  const hint = bar.querySelector(".ui-layout-toolbar__hint");
  if (toggle) {
    toggle.textContent = on ? "Editing…" : "Edit UI";
    toggle.setAttribute("aria-pressed", on ? "true" : "false");
  }
  done?.toggleAttribute("hidden", !on);
  reset?.toggleAttribute("hidden", !on);
  if (hint) hint.classList.toggle("ui-layout-toolbar__hint--hidden", !on);
  refresh(root);
}

function removeHandles(root: HTMLElement): void {
  root.querySelectorAll(".ui-layout-handle").forEach((n) => n.remove());
}

function attachHandles(root: HTMLElement): void {
  if (!editMode) return;
  const data = loadAll();
  root.querySelectorAll<HTMLElement>("[data-layout-id]").forEach((el) => {
    const id = el.dataset.layoutId;
    if (!id || el.querySelector(":scope > .ui-layout-handle")) return;

    const drag = document.createElement("div");
    drag.className = "ui-layout-handle ui-layout-handle--drag";
    drag.textContent = id;
    drag.title = "Drag to move";

    const resize = document.createElement("div");
    resize.className = "ui-layout-handle ui-layout-handle--resize";
    resize.title = "Drag to resize";

    el.appendChild(drag);
    el.appendChild(resize);

    const parent = el.closest(".tab-pane") as HTMLElement | null;
    if (!parent) return;

    const ensureInStore = (): LayoutRect => {
      let r = data[id];
      if (!r) {
        r = toPercent(el, parent);
        data[id] = r;
        saveAll(data);
        applyLayout(root);
      }
      return r;
    };

    drag.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      ev.preventDefault();
      ev.stopPropagation();
      const r = ensureInStore();
      applyRect(el, r);
      drag.setPointerCapture(ev.pointerId);
      const startX = ev.clientX;
      const startY = ev.clientY;
      const pw = parent.clientWidth || 1;
      const ph = parent.clientHeight || 1;
      const rx0 = r.x;
      const ry0 = r.y;

      const move = (e: PointerEvent) => {
        const dx = ((e.clientX - startX) / pw) * 100;
        const dy = ((e.clientY - startY) / ph) * 100;
        r.x = clamp(rx0 + dx, 0, Math.max(0, 100 - r.w));
        r.y = clamp(ry0 + dy, 0, Math.max(0, 100 - r.h));
        data[id] = { ...r };
        saveAll(data);
        applyRect(el, r);
      };
      const up = (e: PointerEvent) => {
        drag.releasePointerCapture(e.pointerId);
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });

    resize.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      ev.preventDefault();
      ev.stopPropagation();
      const r = ensureInStore();
      applyRect(el, r);
      resize.setPointerCapture(ev.pointerId);
      const startX = ev.clientX;
      const startY = ev.clientY;
      const pw = parent.clientWidth || 1;
      const ph = parent.clientHeight || 1;
      const w0 = r.w;
      const h0 = r.h;

      const move = (e: PointerEvent) => {
        const dx = ((e.clientX - startX) / pw) * 100;
        const dy = ((e.clientY - startY) / ph) * 100;
        r.w = clamp(w0 + dx, 8, 100 - r.x);
        r.h = clamp(h0 + dy, 8, 100 - r.y);
        data[id] = { ...r };
        saveAll(data);
        applyRect(el, r);
      };
      const up = (e: PointerEvent) => {
        resize.releasePointerCapture(e.pointerId);
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
  });
}

/** Apply saved layout rects to all marked regions under root. */
export function applyLayout(root: HTMLElement): void {
  const data = loadAll();
  root.querySelectorAll<HTMLElement>("[data-layout-id]").forEach((el) => {
    const id = el.dataset.layoutId;
    if (!id) return;
    const r = data[id];
    if (!r) {
      clearInlineLayout(el);
      return;
    }
    applyRect(el, r);
  });
}

export function refresh(root: HTMLElement): void {
  observer?.disconnect();
  try {
    applyLayout(root);
    removeHandles(root);
    attachHandles(root);
  } finally {
    if (rootRef) observer?.observe(rootRef, { childList: true, subtree: true });
  }
}

function scheduleRefresh(root: HTMLElement): void {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null;
    refresh(root);
  }, 80);
}

export function initLayoutEditor(root: HTMLElement): void {
  rootRef = root;
  ensureToolbar(root);
  applyLayout(root);

  observer?.disconnect();
  observer = new MutationObserver(() => {
    if (rootRef) scheduleRefresh(rootRef);
  });
  observer.observe(root, { childList: true, subtree: true });

  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    if (params.get("layoutEdit") === "1") {
      setEditMode(true, root);
    }
  }

  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && editMode && rootRef) {
      setEditMode(false, rootRef);
    }
  });

  scheduleRefresh(root);
}
