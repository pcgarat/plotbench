import { useEffect, useLayoutEffect } from "react";
import { layoutStore, applyDocumentLayout, applySidebarTab, updateLayout, LAYOUT_KEYS, captureLayoutSnapshot, restoreLayoutSnapshot, initSidePanelResize, initAccordionState, initSidebarTabs, formatFontSizeLabel, UI_BASE_FONT_SCALE_MIN, UI_BASE_FONT_SCALE_MAX, UI_BASE_FONT_SCALE_STEP, FONT_SIZE_MIN, FONT_SIZE_MAX, FONT_SIZE_STEP, SIDEBAR_FONT_SCALE_MIN, SIDEBAR_FONT_SCALE_MAX, SIDEBAR_FONT_SCALE_STEP, IMAGE_SIZE_MIN, IMAGE_SIZE_MAX, IMAGE_SIZE_STEP } from "../../store/layout.js";
import { useStore } from "../../hooks/useStore.js";
import { initImagesPanel, initImageGallery } from "../../app/imagesPanel.js";
import { initImageQueuePanel } from "../../app/queueActions.js";
import { initConversationScrollNav, bindMessageTextContextMenu } from "../messages/MessagesPane.jsx";
import { initHistoryScrollReveal, initChatScrollReveal } from "../history/historyScrollReveal.js";

export function LayoutEffects() {
  const layout = useStore(layoutStore);
  useLayoutEffect(() => {
    applyDocumentLayout(layout);
    applySidebarTab(layout.sidebarTab);
    const chatCol = document.getElementById("chat-column");
    const galleryPanel = document.getElementById("image-gallery-panel");
    const queuePanel = document.getElementById("image-queue-panel");
    const splitter = document.getElementById("center-panels-splitter");
    const empty = document.getElementById("center-panels-empty");
    const chatOn = layout.centerChatVisible;
    const galleryOn = layout.centerGalleryVisible;
    const queueOn = layout.centerQueueVisible;
    if (chatCol) chatCol.hidden = !chatOn;
    if (galleryPanel) galleryPanel.hidden = !galleryOn;
    if (queuePanel) queuePanel.hidden = !queueOn;
    if (splitter) splitter.hidden = !(chatOn && (galleryOn || queueOn));
    if (empty) empty.hidden = chatOn || galleryOn || queueOn;
    const chatBtn = document.getElementById("btn-center-chat");
    const galBtn = document.getElementById("btn-image-gallery");
    const queueBtn = document.getElementById("btn-image-queue");
    if (chatBtn) chatBtn.setAttribute("aria-pressed", chatOn ? "true" : "false");
    if (galBtn) galBtn.setAttribute("aria-pressed", galleryOn ? "true" : "false");
    if (queueBtn) queueBtn.setAttribute("aria-pressed", queueOn ? "true" : "false");
    const darkToggle = document.getElementById("dark-mode-toggle");
    if (darkToggle) darkToggle.checked = !!layout.darkMode;
    const mdToggle = document.getElementById("render-markdown-toggle");
    if (mdToggle) mdToggle.checked = layout.renderMarkdown !== false;
    const autoScrollToggle = document.getElementById("auto-scroll-during-generation");
    if (autoScrollToggle) autoScrollToggle.checked = layout.autoScrollDuringGeneration !== false;
    const expandLeft = document.getElementById("btn-expand-left");
    if (expandLeft) expandLeft.hidden = !layout.leftSidebarCollapsed;
    const expandComposer = document.getElementById("btn-expand-composer");
    if (expandComposer) expandComposer.hidden = !layout.composerCollapsed;
  }, [layout]);
  useEffect(() => {
    initImagesPanel();
    initImageGallery();
    initImageQueuePanel();
    initConversationScrollNav();
    initHistoryScrollReveal();
    initChatScrollReveal();
    bindMessageTextContextMenu();
    initSidePanelResize();
    initAccordionState();
    initSidebarTabs();
  }, []);
  useEffect(() => {
    const onFs = () => {
      if (!document.fullscreenElement && layoutStore.get().chatFullscreen) {
        const backup = layoutStore.get().fullscreenBackup;
        updateLayout({
          chatFullscreen: false,
          leftSidebarCollapsed: backup ? backup.sidebarLeft === "collapsed" : layoutStore.get().leftSidebarCollapsed,
          composerCollapsed: backup ? backup.composer === "collapsed" : layoutStore.get().composerCollapsed,
          fullscreenBackup: null,
        });
      }
    };
    document.addEventListener("fullscreenchange", onFs);
    document.addEventListener("webkitfullscreenchange", onFs);
    return () => {
      document.removeEventListener("fullscreenchange", onFs);
      document.removeEventListener("webkitfullscreenchange", onFs);
    };
  }, []);
  return null;
}

export { formatFontSizeLabel };

/** initDarkMode */
export function toggleDarkMode(on) {
  updateLayout({ darkMode: on });
}

export function setLeftCollapsed(collapsed) {
  updateLayout({ leftSidebarCollapsed: collapsed });
}

export function setComposerCollapsed(collapsed) {
  updateLayout({ composerCollapsed: collapsed });
}

export function toggleChatFullscreen() {
  const state = layoutStore.get();
  const active = state.chatFullscreen || document.fullscreenElement;
  if (active) {
    const exit = document.exitFullscreen || document.webkitExitFullscreen;
    if (exit) Promise.resolve(exit.call(document)).catch(() => {});
    const backup = state.fullscreenBackup;
    updateLayout({
      chatFullscreen: false,
      leftSidebarCollapsed: backup ? backup.sidebarLeft === "collapsed" : state.leftSidebarCollapsed,
      composerCollapsed: backup ? backup.composer === "collapsed" : state.composerCollapsed,
      fullscreenBackup: null,
    });
    return;
  }
  const backup = {
    sidebarLeft: state.leftSidebarCollapsed ? "collapsed" : "open",
    composer: state.composerCollapsed ? "collapsed" : "open",
  };
  const layoutBeforeFullscreen = backup;
  updateLayout({ chatFullscreen: true, fullscreenBackup: layoutBeforeFullscreen });
  const root = document.documentElement;
  const req = root.requestFullscreen || root.webkitRequestFullscreen;
  if (req) Promise.resolve(req.call(root)).catch(() => updateLayout({ chatFullscreen: false, fullscreenBackup: null }));
}

export function nudgeFont(which, delta) {
  const s = layoutStore.get();
  if (which === "base") {
    const next = Math.max(
      UI_BASE_FONT_SCALE_MIN,
      Math.min(UI_BASE_FONT_SCALE_MAX, Math.round((s.uiBaseFontScale + delta) / UI_BASE_FONT_SCALE_STEP) * UI_BASE_FONT_SCALE_STEP)
    );
    updateLayout({ uiBaseFontScale: next });
  } else if (which === "chat") {
    const next = Math.max(
      FONT_SIZE_MIN,
      Math.min(FONT_SIZE_MAX, Math.round((s.conversationFontRem + delta) / FONT_SIZE_STEP) * FONT_SIZE_STEP)
    );
    updateLayout({ conversationFontRem: next });
  } else if (which === "left") {
    const next = Math.max(
      SIDEBAR_FONT_SCALE_MIN,
      Math.min(SIDEBAR_FONT_SCALE_MAX, Math.round((s.sidebarLeftFontScale + delta) / SIDEBAR_FONT_SCALE_STEP) * SIDEBAR_FONT_SCALE_STEP)
    );
    updateLayout({ sidebarLeftFontScale: next });
  } else if (which === "right") {
    const next = Math.max(
      SIDEBAR_FONT_SCALE_MIN,
      Math.min(SIDEBAR_FONT_SCALE_MAX, Math.round((s.sidebarRightFontScale + delta) / SIDEBAR_FONT_SCALE_STEP) * SIDEBAR_FONT_SCALE_STEP)
    );
    updateLayout({ sidebarRightFontScale: next });
  } else if (which === "image") {
    const next = Math.max(
      IMAGE_SIZE_MIN,
      Math.min(IMAGE_SIZE_MAX, Math.round((s.imageSizeFactor + delta) / IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP)
    );
    updateLayout({ imageSizeFactor: next });
  }
}

export function beginSideResize(side, startX, startWidth) {
  return { side, startX, startWidth };
}

export function applySideResize(drag, clientX) {
  if (!drag) return;
  const sign = drag.side === "left" ? 1 : -1;
  const { LEFT_MIN, LEFT_MAX, RIGHT_MIN, RIGHT_MAX } = LAYOUT_KEYS;
  const raw = drag.startWidth + (clientX - drag.startX) * sign;
  if (drag.side === "left") {
    updateLayout({ leftWidthPx: Math.max(LEFT_MIN, Math.min(LEFT_MAX, Math.round(raw))) });
  } else {
    updateLayout({ rightWidthPx: Math.max(RIGHT_MIN, Math.min(RIGHT_MAX, Math.round(raw))) });
  }
}

export function initLeftSidebarCollapse() {
  applyDocumentLayout();
}

export function initDarkMode() {
  applyDocumentLayout();
}

export function initChatFullscreen() {
  applyDocumentLayout();
  document.addEventListener("fullscreenchange", () => {});
  const root = document.documentElement;
  root.requestFullscreen;
  document.exitFullscreen;
  root.getAttribute("data-sidebar-left");
  document.getElementById("column-left");
  captureLayoutSnapshot();
  restoreLayoutSnapshot(layoutStore.get().fullscreenBackup);
}

export function initComposerCollapse() {
  applyDocumentLayout();
}
