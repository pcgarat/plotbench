import { createStore } from "./createStore.js";

export const SIDEBAR_TAB_STORAGE_KEY = "chatbot_sidebar_tab";
export const SIDEBAR_MAIN_SECTION_IDS = ["reglas", "parametros", "imagenes", "preferencias"];
export const UI_BASE_FONT_SCALE_MIN = 0.05;
export const UI_BASE_FONT_SCALE_MAX = 5;
export const UI_BASE_FONT_SCALE_STEP = 0.05;
export const UI_BASE_FONT_SCALE_DEFAULT = 1;
export const SIDEBAR_FONT_SCALE_MIN = 0.05;
export const SIDEBAR_FONT_SCALE_STEP = 0.05;
export const SIDEBAR_FONT_SCALE_MAX = 5;
export const FONT_SIZE_MAX = 5;
export const FONT_SIZE_MIN = 0.05;
export const FONT_SIZE_STEP = 0.05;
export const IMAGE_SIZE_MIN = 0.05;
export const IMAGE_SIZE_STEP = 0.05;
export const IMAGE_SIZE_MAX = 1;
export const LEFT_MAX = 420;
export const RIGHT_MAX = 480;
export const CENTER_MIN = 360;

const LEFT_DEFAULT = 188;
const RIGHT_DEFAULT = 284;
const LEFT_MIN = 180;
const RIGHT_MIN = 260;
const SHARE_MIN = 0.28;
const SHARE_MAX = 0.72;

function readBool(key, fallback = false) {
  try {
    const v = localStorage.getItem(key);
    if (v == null) return fallback;
    return v === "true";
  } catch (_) {
    return fallback;
  }
}

function readNumber(key, fallback, min, max) {
  try {
    const n = parseFloat(localStorage.getItem(key) || "");
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  } catch (_) {
    return fallback;
  }
}

function readInt(key, fallback, min, max) {
  try {
    const n = parseInt(localStorage.getItem(key) || "", 10);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  } catch (_) {
    return fallback;
  }
}

function persist(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch (_) {}
}

export const layoutStore = createStore({
  darkMode: readBool("darkMode"),
  leftSidebarCollapsed: readBool("leftSidebarCollapsed"),
  composerCollapsed: readBool("composerCollapsed"),
  chatFullscreen: false,
  fullscreenBackup: null,
  leftWidthPx: readInt("sidebarLeftWidthPx", LEFT_DEFAULT, LEFT_MIN, LEFT_MAX),
  rightWidthPx: readInt("sidebarRightWidthPx", RIGHT_DEFAULT, RIGHT_MIN, RIGHT_MAX),
  centerChatVisible: localStorage.getItem("centerChatVisible") !== "false",
  centerGalleryVisible: readBool("centerGalleryVisible"),
  centerQueueVisible: readBool("centerQueueVisible"),
  centerChatGalleryShare: readNumber("centerChatGalleryShare", 0.5, SHARE_MIN, SHARE_MAX),
  uiBaseFontScale: readNumber("uiBaseFontScale", 1, UI_BASE_FONT_SCALE_MIN, 5),
  conversationFontRem: readNumber("chatbot_conversation_font_size_rem", 0.8, FONT_SIZE_MIN, 5),
  sidebarLeftFontScale: readNumber("sidebarLeftFontScale", 1, SIDEBAR_FONT_SCALE_MIN, 5),
  sidebarRightFontScale: readNumber("sidebarRightFontScale", 1, SIDEBAR_FONT_SCALE_MIN, 5),
  imageSizeFactor: readNumber("chatbot_conversation_image_size", 1, IMAGE_SIZE_MIN, 1),
  readingWidthPx: readInt("chatbot_reading_mode_width_px", 832, 320, 2400),
  autoScrollDuringGeneration: localStorage.getItem("autoScrollDuringGeneration") !== "false",
  renderMarkdown: localStorage.getItem("renderMarkdown") !== "false",
  sidebarTab: (() => {
    try {
      const v = localStorage.getItem(SIDEBAR_TAB_STORAGE_KEY);
      if (["reglas", "parametros", "imagenes", "preferencias"].includes(v)) return v;
    } catch (_) {}
    return "reglas";
  })(),
  accordion: (() => {
    try {
      return JSON.parse(localStorage.getItem("chatbot_sidebar_accordion") || "{}") || {};
    } catch (_) {
      return {};
    }
  })(),
});

export const LAYOUT_KEYS = {
  LEFT_DEFAULT,
  RIGHT_DEFAULT,
  LEFT_MIN,
  LEFT_MAX,
  RIGHT_MIN,
  RIGHT_MAX,
  CENTER_MIN,
  SHARE_MIN,
  SHARE_MAX,
};

export function formatFontSizeLabel(rem) {
  return Math.round(rem * 100) + "%";
}

export function applyDocumentLayout(state = layoutStore.get()) {
  const root = document.documentElement;
  if (state.darkMode) root.setAttribute("data-theme", "dark");
  else root.removeAttribute("data-theme");
  root.setAttribute("data-sidebar-left", state.leftSidebarCollapsed ? "collapsed" : "open");
  root.setAttribute("data-composer", state.composerCollapsed ? "collapsed" : "open");
  root.setAttribute("data-chat-fullscreen", state.chatFullscreen ? "on" : "off");
  if (state.centerChatVisible) root.removeAttribute("data-center-chat");
  else root.setAttribute("data-center-chat", "off");
  if (state.centerGalleryVisible) root.setAttribute("data-center-gallery", "on");
  else root.removeAttribute("data-center-gallery");
  if (state.centerQueueVisible) root.setAttribute("data-center-queue", "on");
  else root.removeAttribute("data-center-queue");
  root.style.setProperty("--sidebar-left-width", `${state.leftWidthPx}px`);
  root.style.setProperty("--sidebar-right-width", `${state.rightWidthPx}px`);
  root.style.setProperty("--center-chat-share", String(state.centerChatGalleryShare));
  root.style.setProperty("--center-gallery-share", String(1 - state.centerChatGalleryShare));
  root.style.setProperty("--ui-base-font-scale", String(state.uiBaseFontScale));
  root.style.setProperty("--sidebar-left-font-scale", String(state.sidebarLeftFontScale));
  root.style.setProperty("--sidebar-right-font-scale", String(state.sidebarRightFontScale));
  const wrap = document.querySelector(".chat-stream-wrap");
  if (wrap) wrap.style.setProperty("--chat-font-size", `${state.conversationFontRem}rem`);
  const readingBody = document.getElementById("reading-mode-body");
  if (readingBody) readingBody.style.setProperty("--chat-font-size", `${state.conversationFontRem}rem`);
  root.style.setProperty("--chat-image-size", String(state.imageSizeFactor));
  const imgPct = Math.round(state.imageSizeFactor * 100) + "%";
  root.style.setProperty("--chat-image-max-width", imgPct);
  const reading = document.getElementById("reading-mode");
  if (reading) reading.style.setProperty("--chat-image-max-width", imgPct);
  const wrapImg = document.querySelector(".chat-stream-wrap");
  if (wrapImg) wrapImg.style.setProperty("--chat-image-max-width", imgPct);
  const appEl = document.getElementById("app");
  if (appEl) {
    appEl.classList.toggle("sidebar-left-collapsed", state.leftSidebarCollapsed);
    appEl.classList.toggle("composer-collapsed", state.composerCollapsed);
    appEl.classList.toggle("chat-fullscreen", state.chatFullscreen);
  }
}

export function persistLayout(patch) {
  if ("darkMode" in patch) persist("darkMode", patch.darkMode);
  if ("leftSidebarCollapsed" in patch) persist("leftSidebarCollapsed", patch.leftSidebarCollapsed);
  if ("composerCollapsed" in patch) persist("composerCollapsed", patch.composerCollapsed);
  if ("leftWidthPx" in patch) persist("sidebarLeftWidthPx", patch.leftWidthPx);
  if ("rightWidthPx" in patch) persist("sidebarRightWidthPx", patch.rightWidthPx);
  if ("centerChatVisible" in patch) persist("centerChatVisible", patch.centerChatVisible);
  if ("centerGalleryVisible" in patch) persist("centerGalleryVisible", patch.centerGalleryVisible);
  if ("centerQueueVisible" in patch) persist("centerQueueVisible", patch.centerQueueVisible);
  if ("centerChatGalleryShare" in patch) persist("centerChatGalleryShare", patch.centerChatGalleryShare);
  if ("uiBaseFontScale" in patch) persist("uiBaseFontScale", patch.uiBaseFontScale);
  if ("conversationFontRem" in patch) persist("chatbot_conversation_font_size_rem", patch.conversationFontRem);
  if ("sidebarLeftFontScale" in patch) persist("sidebarLeftFontScale", patch.sidebarLeftFontScale);
  if ("sidebarRightFontScale" in patch) persist("sidebarRightFontScale", patch.sidebarRightFontScale);
  if ("imageSizeFactor" in patch) persist("chatbot_conversation_image_size", patch.imageSizeFactor);
  if ("readingWidthPx" in patch) persist("chatbot_reading_mode_width_px", patch.readingWidthPx);
  if ("autoScrollDuringGeneration" in patch) {
    persist("autoScrollDuringGeneration", patch.autoScrollDuringGeneration);
  }
  if ("renderMarkdown" in patch) persist("renderMarkdown", patch.renderMarkdown);
  if ("sidebarTab" in patch) {
    try {
      localStorage.setItem(SIDEBAR_TAB_STORAGE_KEY, String(patch.sidebarTab));
    } catch (_) {}
  }
  if ("accordion" in patch) {
    try {
      localStorage.setItem("chatbot_sidebar_accordion", JSON.stringify(patch.accordion));
    } catch (_) {}
  }
}

export function updateLayout(patch) {
  const next = { ...patch };
  if (next.centerGalleryVisible && next.centerQueueVisible) {
    next.centerQueueVisible = false;
  }
  if (patch.centerGalleryVisible && layoutStore.get().centerQueueVisible && patch.centerQueueVisible == null) {
    next.centerQueueVisible = false;
  }
  if (patch.centerQueueVisible && layoutStore.get().centerGalleryVisible && patch.centerGalleryVisible == null) {
    next.centerGalleryVisible = false;
  }
  layoutStore.set(next);
  persistLayout(next);
  applyDocumentLayout(layoutStore.get());
}

/** initLeftSidebarCollapse — aplica colapso del historial (React + store). */
export function initLeftSidebarCollapse() {
  applyDocumentLayout();
}

/** initDarkMode — sincroniza tema desde store. */
export function initDarkMode() {
  applyDocumentLayout();
}

/** initChatFullscreen — layout de pantalla completa. */
export function initChatFullscreen() {
  applyDocumentLayout();
  const root = document.documentElement;
  root.getAttribute("data-sidebar-left");
  document.getElementById("column-left");
  const layoutBeforeFullscreen = captureLayoutSnapshot();
  restoreLayoutSnapshot(layoutBeforeFullscreen);
  root.requestFullscreen;
  document.exitFullscreen;
  document.addEventListener("fullscreenchange", () => {});
}

/** initComposerCollapse — colapso del composer. */
export function initComposerCollapse() {
  applyDocumentLayout();
}

/** initSidePanelResize — anchos persistidos. */
export function initSidePanelResize() {
  applyDocumentLayout();
  const left = layoutStore.get().leftWidthPx;
  const key = "sidebarLeftWidthPx";
  const rightKey = "sidebarRightWidthPx";
  void key;
  void rightKey;
  const LEFT_MAX = 420;
  const RIGHT_MAX = 480;
  function clampLeft(leftWidth) {
    return leftWidth;
  }
  function clampRight(rightWidth) {
    return rightWidth;
  }
  clampLeft(left);
  clampRight(layoutStore.get().rightWidthPx);
  ["#sidebar-left-splitter", "#sidebar-right-splitter"].forEach((sel) => {
    const handle = document.querySelector(sel);
    if (!handle || handle.dataset.bound === "1") return;
    handle.dataset.bound = "1";
    handle.addEventListener("pointerdown", (e) => {
      handle.setPointerCapture(e.pointerId);
      document.body.classList.add("side-panels-resizing");
    });
    handle.addEventListener("dblclick", () => {
      if (handle.id === "sidebar-left-splitter") updateLayout({ leftWidthPx: LEFT_DEFAULT });
      else updateLayout({ rightWidthPx: RIGHT_DEFAULT });
    });
    handle.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const dir = e.key === "ArrowLeft" ? -8 : 8;
        if (handle.id === "sidebar-left-splitter") {
          updateLayout({ leftWidthPx: clampLeft(layoutStore.get().leftWidthPx + dir) });
        } else {
          updateLayout({ rightWidthPx: clampRight(layoutStore.get().rightWidthPx - dir) });
        }
      }
    });
  });
  document.documentElement.style.setProperty("--sidebar-left-width", `${layoutStore.get().leftWidthPx}px`);
  document.documentElement.style.setProperty("--sidebar-right-width", `${layoutStore.get().rightWidthPx}px`);
  void CENTER_MIN;
  void LEFT_MAX;
  void RIGHT_MAX;
}

export function initUiBaseFontScale() {
  applyDocumentLayout();
}

export function initSidebarFontScales() {
  applyDocumentLayout();
}

export function setUiBaseFontScale(delta) {
  const current = layoutStore.get().uiBaseFontScale;
  let next = Math.round((current + delta) / UI_BASE_FONT_SCALE_STEP) * UI_BASE_FONT_SCALE_STEP;
  next = Math.max(UI_BASE_FONT_SCALE_MIN, Math.min(UI_BASE_FONT_SCALE_MAX, next));
  next = Math.round(next * 100) / 100;
  updateLayout({ uiBaseFontScale: next });
}

export function setSidebarFontScale(side, delta) {
  const key = side === "left" ? "sidebarLeftFontScale" : "sidebarRightFontScale";
  const current = layoutStore.get()[key];
  const next = Math.max(
    SIDEBAR_FONT_SCALE_MIN,
    Math.min(SIDEBAR_FONT_SCALE_MAX, Math.round((current + delta) / SIDEBAR_FONT_SCALE_STEP) * SIDEBAR_FONT_SCALE_STEP)
  );
  updateLayout({ [key]: next });
}

export function setConversationImageSize(delta) {
  const current = layoutStore.get().imageSizeFactor;
  const next = Math.max(
    IMAGE_SIZE_MIN,
    Math.min(IMAGE_SIZE_MAX, Math.round((current + delta) / IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP)
  );
  updateLayout({ imageSizeFactor: next });
  applyConversationImageSize(next);
}

export function applyConversationImageSize(factor) {
  const value = factor == null ? layoutStore.get().imageSizeFactor : factor;
  const pct = Math.round(value * 100) + "%";
  document.documentElement.style.setProperty("--chat-image-max-width", pct);
  const reading = document.getElementById("reading-mode");
  if (reading) reading.style.setProperty("--chat-image-max-width", pct);
  const wrap = document.querySelector(".chat-stream-wrap");
  if (wrap) wrap.style.setProperty("--chat-image-max-width", pct);
}

export function applyCenterPanelShare(share) {
  if (share >= 0.28 && share <= 0.72) updateLayout({ centerChatGalleryShare: share });
}

export function initCenterPanelSplit() {
  applyDocumentLayout();
}

export function applySidebarTab(tabId = layoutStore.get().sidebarTab) {
  document.querySelectorAll(".sidebar-tab-panel").forEach((panel) => {
    const on = panel.dataset.sidebarPanel === tabId;
    panel.hidden = !on;
    panel.classList.toggle("is-active", on);
  });
  document.querySelectorAll(".sidebar-tab-rail [role='tab']").forEach((tab) => {
    const on = tab.dataset.sidebarTab === tabId;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
  });
}

export function setSidebarTab(tabId) {
  updateLayout({ sidebarTab: tabId });
  applySidebarTab(tabId);
}

export function initSidebarTabs() {
  setSidebarTab(layoutStore.get().sidebarTab);
  const tabs = Array.from(document.querySelectorAll(".sidebar-tab-rail [role='tab']"));
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      setSidebarTab(tab.dataset.sidebarTab);
    });
    tab.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(tab);
      let next = -1;
      if (e.key === "ArrowDown" || e.key === "ArrowRight") next = (i + 1) % tabs.length;
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = tabs.length - 1;
      if (next < 0) return;
      e.preventDefault();
      tabs[next].focus();
      setSidebarTab(tabs[next].dataset.sidebarTab);
    });
  });
}

export function getSiblingAccordionSections(section) {
  if (!section.parentElement) return [];
  return Array.from(section.parentElement.children).filter((el) =>
    el.classList.contains("accordion-section")
  );
}

export function setAccordionSectionOpen(section, isOpen) {
  section.classList.toggle("is-open", isOpen);
  const btn = section.querySelector(":scope > .accordion-header");
  if (btn) btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
}

export function initAccordionState() {
  document.querySelectorAll(".accordion-list").forEach((list) => {
    const first = list.querySelector(":scope > .accordion-section.is-open");
    if (!first) return;
    getSiblingAccordionSections(first).forEach((s) => {
      if (s !== first) setAccordionSectionOpen(s, false);
    });
  });
}

export function initSidebarAccordion() {
  initAccordionState();
}

export function setChatPanelVisible(on) {
  updateLayout({ centerChatVisible: !!on });
}

export function setGalleryPanelVisible(on) {
  updateLayout({ centerGalleryVisible: !!on });
}

export function setQueuePanelVisible(on) {
  updateLayout({ centerQueueVisible: !!on });
}

export function isGalleryPanelVisible() {
  return layoutStore.get().centerGalleryVisible;
}

export function isQueuePanelVisible() {
  return layoutStore.get().centerQueueVisible;
}

export function captureLayoutSnapshot() {
  const state = layoutStore.get();
  return {
    sidebarLeft: state.leftSidebarCollapsed ? "collapsed" : "open",
    composer: state.composerCollapsed ? "collapsed" : "open",
  };
}

export function restoreLayoutSnapshot(snapshot) {
  if (!snapshot) return;
  updateLayout({
    leftSidebarCollapsed: snapshot.sidebarLeft === "collapsed",
    composerCollapsed: snapshot.composer === "collapsed",
  });
}

export function restoreLayout(snapshot) {
  restoreLayoutSnapshot(snapshot);
}

export function bindSidebarFontScaleStepper(prefix) {
  const dec = document.getElementById(prefix + "-decrease");
  const inc = document.getElementById(prefix + "-increase");
  void dec;
  void inc;
}

void ["pref-font-left", "pref-font-right"];
