import { sessionStore } from "../../store/session.js";
import { layoutStore, updateLayout } from "../../store/layout.js";
import { useStore } from "../../hooks/useStore.js";
import { messagesForDisplay } from "../../lib/tree.js";
import { messagesForPane } from "../../lib/messageViewOnly.js";
import { canLoadOlderMessage } from "../../lib/messageWindow.js";
import { formatMessageHtml, buildCollapsibleMessageHtml, messageCollapseKey, splitFirstParagraph, escapeHtml, kickLazyIllustrations } from "../../lib/html.js";
import { forkConversationFromMessage, deleteMessageFromHistory, findMessageWithIllustration, loadOlderMessageInView } from "../../app/sessionActions.js";
import {
  maybeIllustrateAssistantMessage,
  generateRemainingImages,
  clearMessagePhotos,
  pruneOrphanAnchors,
  illustrateAtParagraph,
} from "../../app/illustrate.js";
import { scheduleConversationImageFilter, highlightIllustrationInConversation } from "../../app/galleryActions.js";
import { findChatIllustration } from "../../lib/illustrationLocate.js";
import { showNotice, showError } from "../../store/ui.js";
import { useEffect, useLayoutEffect, useRef } from "react";

function splitTxt2imgPrompt(content) {
  const re = /```txt2img-prompt\n([\s\S]*?)\n```/;
  const raw = content || "";
  const m = raw.match(re);
  if (!m) return { text: raw, prompt: null };
  return { text: raw.replace(re, "").trim(), prompt: m[1].trim() };
}

async function copyMessageToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showNotice("Copiado.");
  } catch (err) {
    showError("No se pudo copiar: " + (err && err.message ? err.message : err));
  }
}

let scheduledScrollToBottom = null;

export function cancelScheduledScrollToBottom() {
  if (scheduledScrollToBottom) {
    cancelAnimationFrame(scheduledScrollToBottom);
    scheduledScrollToBottom = null;
  }
}

export function collapseAllMessages() {
  const { messages } = sessionStore.get();
  const collapsedMessageKeys = new Set(sessionStore.get().collapsedMessageKeys);
  messages.forEach((m, idx) => {
    if (m.role === "user" || m.ephemeral_debug) return;
    if (!(m.content && String(m.content).trim())) return;
    if (!splitFirstParagraph(m.content).collapsible) return;
    collapsedMessageKeys.add(messageCollapseKey(m, idx));
  });
  sessionStore.set({ collapsedMessageKeys: Array.from(collapsedMessageKeys) });
}

const illustrationInfoIconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"></svg>`;
const msgDeleteIconSvgStr = `<svg xmlns="http://www.w3.org/2000/svg" width=\"11\" height=\"11\" viewBox="0 0 24 24"></svg>`;
const msgCopyIconSvgStr = `<svg xmlns="http://www.w3.org/2000/svg" width=\"11\" height=\"11\" viewBox="0 0 24 24"></svg>`;
const msgToInputIconSvgStr = `<svg xmlns="http://www.w3.org/2000/svg" width=\"11\" height=\"11\" viewBox="0 0 24 24"></svg>`;
const msgIllustrateIconSvgStr = `<svg xmlns="http://www.w3.org/2000/svg" width=\"11\" height=\"11\" viewBox="0 0 24 24"></svg>`;
const msgReadIconSvgStr = `<svg xmlns="http://www.w3.org/2000/svg" width=\"11\" height=\"11\" viewBox="0 0 24 24"></svg>`;
void illustrationInfoIconSvg;
void msgDeleteIconSvgStr;
void msgCopyIconSvgStr;
void msgToInputIconSvgStr;
void msgIllustrateIconSvgStr;
void msgReadIconSvgStr;

const msgDeleteIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
);
const msgCopyIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1"/></svg>
);
const msgToInputIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 10L4 15 9 20"/><path d="M20 4v11a4 4 0 01-4 4H4"/></svg>
);
const msgIllustrateIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
);
const msgReadIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
);
const msgMoreIconSvg = (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="5" r="1.75"/><circle cx="12" cy="12" r="1.75"/><circle cx="12" cy="19" r="1.75"/></svg>
);

export function renderMessages() {
  const collapsedMessageKeys = new Set(sessionStore.get().collapsedMessageKeys);
  const wrap = document.getElementById("messages-container");
  const prevScrollTop = wrap ? wrap.scrollTop : 0;
  document.querySelectorAll(".msg-collapse-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const collapseKey = btn.closest("[data-collapse-key]") && btn.closest("[data-collapse-key]").getAttribute("data-collapse-key");
      if (!collapseKey) return;
      const key = collapseKey;
      const willExpand = collapsedMessageKeys.has(collapseKey);
      if (willExpand) collapsedMessageKeys.delete(key);
      else collapsedMessageKeys.add(key);
      kickLazyIllustrations(wrap);
      sessionStore.set({ collapsedMessageKeys: Array.from(collapsedMessageKeys) });
    });
  });
  scheduleConversationImageFilter();
  if (wrap && sessionStore.get().pendingReveal) return;
  if (wrap) wrap.scrollTop = prevScrollTop;
}

export function closeAllMessageContextMenus() {
  const menu = document.getElementById("msg-text-context-menu");
  if (menu) menu.hidden = true;
  document.querySelectorAll(".msg-more-wrap details[open]").forEach((details) => {
    details.removeAttribute("open");
  });
}

function selectedTextExcerpt() {
  const selection = typeof window.getSelection === "function" ? window.getSelection() : null;
  if (!selection || selection.isCollapsed) return "";
  return String(selection.toString() || "").trim();
}

function placeFixedMenu(menu, clientX, clientY) {
  menu.style.left = Math.max(8, clientX) + "px";
  menu.style.top = Math.max(8, clientY) + "px";
  menu.hidden = false;
  const rect = menu.getBoundingClientRect();
  if (rect.right > window.innerWidth - 8) {
    menu.style.left = Math.max(8, window.innerWidth - rect.width - 8) + "px";
  }
  if (rect.bottom > window.innerHeight - 8) {
    menu.style.top = Math.max(8, window.innerHeight - rect.height - 8) + "px";
  }
}

function openMessageTextContextMenu(clientX, clientY, ctx) {
  const menu = document.getElementById("msg-text-context-menu");
  if (!menu) return;
  menu.dataset.messageId = ctx.messageId || "";
  menu.dataset.paragraphIndex = String(ctx.paragraphIndex ?? 0);
  menu.dataset.excerpt = ctx.excerpt || "";
  const copyBtn = document.getElementById("msg-text-copy");
  if (copyBtn) copyBtn.hidden = !ctx.excerpt;
  placeFixedMenu(menu, clientX, clientY);
}

export function scrollMessagesToBottom() {
  const el = document.getElementById("messages-container");
  if (el) el.scrollTop = el.scrollHeight;
}

export function scheduleScrollMessagesToBottom() {
  cancelScheduledScrollToBottom();
  scheduledScrollToBottom = requestAnimationFrame(scrollMessagesToBottom);
}

export function scrollMessagesToTop() {
  const el = document.getElementById("messages-container");
  if (el) el.scrollTop = 0;
}

export function scheduleScrollMessagesToTop() {
  requestAnimationFrame(scrollMessagesToTop);
}

export function scrollAndHighlightMessage(id) {
  cancelScheduledScrollToBottom();
  const container = document.getElementById("messages-container");
  const node = container && id ? container.querySelector(`[data-msg-id="${CSS.escape(String(id))}"]`) : null;
  if (node) scrollElementInMessages(container, node, "start");
}

export function scrollElementInMessages(container, el, block) {
  if (!container || !el) return false;
  const top = messageOffsetInContainer(container, el);
  if (block === "center") {
    const height = el.getBoundingClientRect().height;
    container.scrollTop = Math.max(0, top - Math.max(0, (container.clientHeight - height) / 2));
  } else {
    container.scrollTop = Math.max(0, top);
  }
  return true;
}

function expandCollapsedMessageRow(row) {
  const collapsible = row && row.querySelector(".message-body-collapsible.is-collapsed");
  if (!collapsible) return false;
  const key = collapsible.getAttribute("data-collapse-key");
  if (!key) return false;
  sessionStore.set((s) => ({
    collapsedMessageKeys: (s.collapsedMessageKeys || []).filter((k) => k !== key),
  }));
  return true;
}

export function applyRevealInMessages(pending, options = {}) {
  if (!pending) return true;
  cancelScheduledScrollToBottom();
  const container = document.getElementById("messages-container");
  if (!container || container.clientHeight < 8) return false;
  const currentConv = sessionStore.get().conversationId;
  if (pending.conversationId && currentConv && pending.conversationId !== currentConv) {
    return false;
  }
  const resolved = findMessageWithIllustration(
    sessionStore.get().messages,
    pending.filename,
    pending.sceneId,
    pending.messageId
  );
  const messageId = (resolved && resolved.id) || pending.messageId || null;
  const row = messageId
    ? container.querySelector(`.message-row[data-msg-id="${CSS.escape(String(messageId))}"]`)
    : null;
  if (messageId && !row) {
    // Esperar a que cargue el hilo / se pinte el mensaje; no cerrar el pending.
    return false;
  }
  if (row && expandCollapsedMessageRow(row)) return false;
  kickLazyIllustrations(container);
  if (pending.filename || pending.sceneId) {
    if (
      highlightIllustrationInConversation(pending.filename, pending.sceneId, {
        silent: true,
        messageId,
      })
    ) {
      return illustrationRevealIsStable(pending.filename, pending.sceneId, messageId);
    }
    if (options.finalAttempt && row) {
      scrollElementInMessages(container, row, "start");
      return true;
    }
    return false;
  }
  if (!row) return false;
  scrollElementInMessages(container, row, "start");
  const cRect = container.getBoundingClientRect();
  const r = row.getBoundingClientRect();
  return Math.abs(r.top - cRect.top) < 96;
}

let revealLoopToken = 0;

export function schedulePendingRevealLoop() {
  const token = ++revealLoopToken;
  let attempts = 0;
  const run = () => {
    if (token !== revealLoopToken) return;
    const pending = sessionStore.get().pendingReveal;
    if (!pending) return;
    attempts += 1;
    if (applyRevealInMessages(pending, { finalAttempt: attempts >= 45 }) || attempts >= 45) {
      if (token !== revealLoopToken) return;
      sessionStore.set({ pendingReveal: null });
      return;
    }
    requestAnimationFrame(run);
  };
  run();
}

function illustrationRevealIsStable(filename, sceneId, messageId) {
  const root = document.getElementById("messages-container");
  if (!root) return false;
  const found = findChatIllustration(root, { filename, sceneId, messageId });
  const img = found && found.img;
  const frame = found && found.frame;
  if (!img || !frame) return false;
  if (!img.complete) return false;
  return frame.getBoundingClientRect().height > 1;
}

export async function openConversationAtMessage(conversationId, messageId) {
  const { openConversationAtMessage: open } = await import("../../app/sessionActions.js");
  return open(conversationId, messageId);
}

export function scrollReadingBodyToStart() {
  const el = document.getElementById("reading-mode-body");
  if (!el) return;
  el.scrollTop = 0;
  requestAnimationFrame(function () {
    el.scrollTop = 0;
    requestAnimationFrame(function () {
      el.scrollTop = 0;
    });
  });
}

export function openReadingMode(index) {
  sessionStore.set({ readingModeIndex: index });
  scrollReadingBodyToStart();
}

export function closeReadingMode() {
  sessionStore.set({ readingModeIndex: null });
}

export function syncReadingModeContentPreservingScroll() {
  applyIllustrationContentToOpenView();
}

export function applyIllustrationContentToOpenView() {
  return true;
}

export function paragraphIndexFromEventTarget(target, messageRoot) {
  if (!target || !messageRoot) return 0;
  const para = target.closest("[data-paragraph-index]");
  if (para && messageRoot.contains(para)) {
    const n = parseInt(para.getAttribute("data-paragraph-index"), 10);
    if (!Number.isNaN(n) && n >= 0) return n;
  }
  const unit = target.closest(".illustration-unit");
  if (unit && messageRoot.contains(unit)) {
    const owner = parseInt(unit.getAttribute("data-owner-paragraph-index"), 10);
    if (!Number.isNaN(owner) && owner >= 0) return owner;
  }
  return 0;
}

let messageTextContextMenuBound = false;

export function bindMessageTextContextMenu() {
  if (messageTextContextMenuBound) return;
  messageTextContextMenuBound = true;
  document.addEventListener("contextmenu", function (e) {
    const bubble = e.target.closest(".message-bubble.assistant");
    if (!bubble) {
      if (!e.target.closest("#msg-text-context-menu")) closeAllMessageContextMenus();
      return;
    }
    if (e.target.closest("button, a, textarea, input")) return;
    e.preventDefault();
    e.stopPropagation();
    const row = bubble.closest("[data-msg-id]");
    openMessageTextContextMenu(e.clientX, e.clientY, {
      messageId: row ? row.getAttribute("data-msg-id") : "",
      paragraphIndex: paragraphIndexFromEventTarget(e.target, bubble),
      excerpt: selectedTextExcerpt(),
    });
  });
  document.addEventListener("click", function (e) {
    const moreItem = e.target.closest(".msg-more-wrap .msg-context-item");
    if (moreItem) {
      moreItem.closest("details")?.removeAttribute("open");
    } else if (!e.target.closest(".msg-more-wrap details")) {
      document.querySelectorAll(".msg-more-wrap details[open]").forEach((details) => {
        details.removeAttribute("open");
      });
    }

    const menu = document.getElementById("msg-text-context-menu");
    if (!menu || menu.hidden) return;
    const item = e.target.closest("#msg-text-context-menu [data-action]");
    if (item && menu.contains(item)) {
      const action = item.getAttribute("data-action");
      const messageId = menu.dataset.messageId;
      const paragraphIndex = menu.dataset.paragraphIndex;
      const excerpt = menu.dataset.excerpt || "";
      closeAllMessageContextMenus();
      if (action === "illustrate-at") {
        illustrateAtParagraph(messageId, paragraphIndex, excerpt);
      } else if (action === "copy-selection") {
        copyMessageToClipboard(excerpt);
      }
      return;
    }
    if (e.target.closest("#msg-text-context-menu")) return;
    closeAllMessageContextMenus();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAllMessageContextMenus();
  });
}

export function getPartiallyVisibleMessageRows(container) {
  if (!container) return [];
  const rows = Array.from(container.querySelectorAll(".message-row"));
  const cRect = container.getBoundingClientRect();
  return rows.filter((row) => {
    const r = row.getBoundingClientRect();
    return r.bottom > cRect.top + 0.5 && r.top < cRect.bottom - 0.5;
  });
}

export function messageOffsetInContainer(container, messageEl) {
  const cRect = container.getBoundingClientRect();
  const r = messageEl.getBoundingClientRect();
  return r.top - cRect.top + container.scrollTop;
}

export function scrollMessageStartIntoView(container, messageEl) {
  scrollElementInMessages(container, messageEl, "start");
}

export function scrollMessageEndIntoView(container, messageEl) {
  if (!container || !messageEl) return;
  const top = messageOffsetInContainer(container, messageEl);
  const height = messageEl.getBoundingClientRect().height;
  container.scrollTop = Math.max(0, top + height - container.clientHeight);
  requestAnimationFrame(function () {
    const residual =
      messageEl.getBoundingClientRect().bottom - container.getBoundingClientRect().bottom;
    if (Math.abs(residual) > 0.5) container.scrollTop += residual;
  });
}

export function scrollToFirstVisibleMessageStart() {
  const container = document.getElementById("messages-container");
  const rows = getPartiallyVisibleMessageRows(container);
  if (rows[0]) scrollMessageStartIntoView(container, rows[0]);
}

export function scrollToLastVisibleMessageEnd() {
  const container = document.getElementById("messages-container");
  const rows = getPartiallyVisibleMessageRows(container);
  if (rows.length) scrollMessageEndIntoView(container, rows[rows.length - 1]);
}

export function initConversationScrollNav() {
  const wrap = document.querySelector(".chat-stream-wrap");
  const nav = document.getElementById("chat-scroll-nav");
  const btnUp = document.getElementById("btn-scroll-msg-up");
  const btnDown = document.getElementById("btn-scroll-msg-down");
  if (!wrap || !nav || !btnUp || !btnDown) return;
  if (nav.dataset.scrollNavBound === "1") return;
  nav.dataset.scrollNavBound = "1";
  const IDLE_HIDE_MS = 1200;
  let hideTimer = null;
  let pointerOverNav = false;
  function setVisible(visible) {
    nav.classList.toggle("is-visible", visible);
  }
  function clearHide() {
    if (hideTimer === null) return;
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  function scheduleHide() {
    clearHide();
    hideTimer = setTimeout(function () {
      hideTimer = null;
      if (!pointerOverNav) setVisible(false);
    }, IDLE_HIDE_MS);
  }
  wrap.addEventListener("mousemove", () => {
    setVisible(true);
    if (!pointerOverNav) scheduleHide();
  });
  nav.addEventListener("mouseenter", () => {
    pointerOverNav = true;
    clearHide();
    setVisible(true);
  });
  nav.addEventListener("mouseleave", () => {
    pointerOverNav = false;
    scheduleHide();
  });
  wrap.addEventListener("mouseleave", () => {
    pointerOverNav = false;
    scheduleHide();
  });
  btnUp.addEventListener("click", (e) => { e.preventDefault(); scrollToFirstVisibleMessageStart(); });
  btnDown.addEventListener("click", (e) => { e.preventDefault(); scrollToLastVisibleMessageEnd(); });
}

export function initReadingMode() {}

export function MessagesPane() {
  const messages = useStore(sessionStore, (s) => s.messages);
  const viewStartIndex = useStore(sessionStore, (s) => s.viewStartIndex);
  const streamingText = useStore(sessionStore, (s) => s.streamingText);
  const streamingStatus = useStore(sessionStore, (s) => s.streamingStatus);
  const collapsed = useStore(sessionStore, (s) => s.collapsedMessageKeys);
  const illustrating = useStore(sessionStore, (s) => s.illustratingIds);
  const conversationId = useStore(sessionStore, (s) => s.conversationId);
  const autoScroll = useStore(layoutStore, (s) => s.autoScrollDuringGeneration);
  const renderMarkdown = useStore(layoutStore, (s) => s.renderMarkdown);
  const pendingReveal = useStore(sessionStore, (s) => s.pendingReveal);
  const messageViewOnly = useStore(sessionStore, (s) => s.messageViewOnly);
  const messageViewOnlyMessageId = useStore(sessionStore, (s) => s.messageViewOnlyMessageId);
  const ref = useRef(null);
  const pendingScrollRestore = useRef(null);
  const loadingOlderRef = useRef(false);
  // `messagesForPane` depende de la vista aislada; las suscripciones de arriba disparan el re-render.
  const display = messagesForPane(
    { messageViewOnly, messageViewOnlyMessageId, conversationId },
    messagesForDisplay(messages, viewStartIndex)
  );
  // El composer sigue disponible en todas las vistas (incluso mensaje aislado).
  const hideComposerActions = false;

  useLayoutEffect(() => {
    if (!pendingReveal) return;
    schedulePendingRevealLoop();
  }, [pendingReveal, messages, collapsed, viewStartIndex]);

  useLayoutEffect(() => {
    const el = ref.current;
    const restore = pendingScrollRestore.current;
    if (!el || !restore) return;
    const delta = el.scrollHeight - restore.prevScrollHeight;
    el.scrollTop = restore.prevScrollTop + delta;
    pendingScrollRestore.current = null;
    loadingOlderRef.current = false;
  }, [viewStartIndex, display.length]);

  useEffect(() => {
    const el = ref.current;
    if (el) kickLazyIllustrations(el);
  }, [messages, streamingText, display.length, viewStartIndex]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!autoScroll) return;
    if (pendingReveal) return;
    if (!streamingText && !streamingStatus) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streamingText, streamingStatus, autoScroll, pendingReveal, viewStartIndex]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function tryLoadOlder() {
      if (loadingOlderRef.current) return;
      if (sessionStore.get().pendingReveal) return;
      if (!canLoadOlderMessage(sessionStore.get().viewStartIndex)) return;
      if (el.scrollTop > 24) return;
      loadingOlderRef.current = true;
      pendingScrollRestore.current = {
        prevScrollHeight: el.scrollHeight,
        prevScrollTop: el.scrollTop,
      };
      if (!loadOlderMessageInView()) {
        pendingScrollRestore.current = null;
        loadingOlderRef.current = false;
      }
    }

    function onScroll() {
      tryLoadOlder();
    }

    function onWheel(e) {
      if (e.deltaY >= 0) return;
      if (el.scrollTop > 24) return;
      tryLoadOlder();
    }

    el.addEventListener("scroll", onScroll, { passive: true });
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      el.removeEventListener("wheel", onWheel);
    };
  }, [conversationId, messages.length]);

  function toggleCollapse(key) {
    sessionStore.set((s) => {
      const set = new Set(s.collapsedMessageKeys);
      if (set.has(key)) set.delete(key);
      else set.add(key);
      return { ...s, collapsedMessageKeys: Array.from(set) };
    });
  }

  if (!display.length && !streamingStatus) {
    return (
      <div className="chat-stream scroll-y-reveal" id="messages-container" ref={ref}>
        <div className="empty-state chat-empty-state">
          <div className="empty-state-inner">
            <img src="/static/img/logo_256.png" alt="" className="empty-state-logo" />
            <p className="empty-state-text">Empieza escribiendo una orden. El agente mantendrá el contexto técnico y el tono estable.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-stream scroll-y-reveal" id="messages-container" ref={ref}>
      {display.map((m, displayIdx) => {
        const idx = messages.findIndex((x) => x === m || (m.id && x.id === m.id));
        const hasContent = m.content && m.content.trim();
        const isEphemeralDebug = !!m.ephemeral_debug;
        const isInherited = !!m.inherited;
        const isUser = m.role === "user";
        const collapseKey = messageCollapseKey(m, idx >= 0 ? idx : displayIdx);
        const isCollapsed = collapsed.includes(collapseKey);
        const splitPg = !isUser && hasContent ? splitTxt2imgPrompt(m.content || "") : null;
        const mdOpts = { markdown: !!renderMarkdown };
        let bodyHtml;
        if (splitPg && splitPg.prompt) {
          const prose = splitPg.text ? `<div class="message-content">${formatMessageHtml(splitPg.text, 0, mdOpts)}</div>` : "";
          bodyHtml = `${prose}<div class="txt2img-prompt-block"><div class="txt2img-prompt-toolbar"><span class="txt2img-prompt-label">Prompt</span><button type="button" class="txt2img-prompt-copy">Copiar</button></div><pre class="txt2img-prompt-text">${escapeHtml(splitPg.prompt)}</pre></div>`;
        } else if (!isUser && !isEphemeralDebug && hasContent) {
          bodyHtml = buildCollapsibleMessageHtml(m.content || "", collapseKey, isCollapsed, mdOpts);
        } else {
          bodyHtml = `<div class="message-content">${formatMessageHtml(m.content || "", 0, mdOpts)}</div>`;
        }
        const inheritedSplit =
          isInherited && (!display[displayIdx + 1] || display[displayIdx + 1].inherited !== true);
        const illustratingBusy = m.id && illustrating.includes(m.id);
        return (
          <div key={m.id || displayIdx}>
            <div className={`${isUser ? "message-row user-row" : "message-row"}${isInherited ? " message-row-inherited" : ""}`} data-msg-id={m.id || ""}>
              <div style={{ maxWidth: isUser ? "70%" : "100%", flex: 1, minWidth: 0 }}>
                <div
                  className={isUser ? "message-bubble user" : "message-bubble assistant"}
                  dangerouslySetInnerHTML={{ __html: bodyHtml }}
                  onClick={(e) => {
                    const tog = e.target.closest(".msg-collapse-toggle");
                    if (tog) {
                      e.preventDefault();
                      toggleCollapse(collapseKey);
                    }
                    const copy = e.target.closest(".txt2img-prompt-copy");
                    if (copy) {
                      e.preventDefault();
                      const pre = copy.closest(".txt2img-prompt-block")?.querySelector("pre");
                      if (pre) copyMessageToClipboard(pre.textContent || "");
                    }
                  }}
                />
                {!isEphemeralDebug && (hasContent || m.id) ? (
                  <div className="message-footer">
                    <div className="message-footer-actions">
                      {hasContent && !hideComposerActions ? (
                        <button type="button" className="msg-action-btn msg-to-input-btn" title="Enviar texto al cuadro de mensaje" onClick={() => {
                          sessionStore.set({ composerDraft: m.content || "" });
                          updateLayout({ composerCollapsed: false });
                          showNotice("Texto del mensaje copiado al cuadro de mensaje.");
                        }}>{msgToInputIconSvg}</button>
                      ) : null}
                      {m.id && (isInherited ? "" : (
                        <button type="button" className="msg-action-btn msg-delete-btn" title="Eliminar del historial" onClick={() => conversationId && deleteMessageFromHistory(conversationId, m.id)}>{msgDeleteIconSvg}</button>
                      ))}
                      {m.id ? (
                        <button type="button" className="msg-action-btn msg-copy-btn" title="Copiar" onClick={() => copyMessageToClipboard(m.content || "")}>{msgCopyIconSvg}</button>
                      ) : null}
                      {m.role === "assistant" && m.id && hasContent ? (
                        <button type="button" className={`msg-action-btn msg-illustrate-btn${illustratingBusy ? " is-busy" : ""}`} title="Generar imágenes para esta respuesta" aria-label="Generar imágenes" disabled={illustratingBusy} onClick={() => maybeIllustrateAssistantMessage(m.id, { force: true })}>{msgIllustrateIconSvg}</button>
                      ) : null}
                      {m.role === "assistant" && hasContent ? (
                        <button type="button" className="msg-action-btn msg-read-btn" title="Modo lectura a pantalla completa" aria-label="Modo lectura" onClick={() => sessionStore.set({ readingModeIndex: idx >= 0 ? idx : displayIdx })}>{msgReadIconSvg}</button>
                      ) : null}
                      {m.id ? (
                        <div className="msg-more-wrap">
                          <details>
                            <summary className="msg-action-btn msg-more-btn" title="Más acciones" aria-label="Más acciones">{msgMoreIconSvg}</summary>
                            <div className="msg-context-menu" role="menu">
                              <button type="button" className="msg-context-item" data-action="fork-conversation" role="menuitem" onClick={() => forkConversationFromMessage(m.id)}>Nueva conversación desde aquí</button>
                              {m.role === "assistant" && hasContent ? (
                                <>
                                  <button type="button" className="msg-context-item" data-action="clear-photos" role="menuitem" onClick={() => clearMessagePhotos(m.id)}>Borrar todas las imágenes</button>
                                  <button type="button" className="msg-context-item" data-action="prune-orphans" role="menuitem" onClick={() => pruneOrphanAnchors(m.id)}>Borrar anclas huérfanas</button>
                                  <button type="button" className="msg-context-item" data-action="generate-remaining" role="menuitem" onClick={() => generateRemainingImages(m.id)}>Generar imágenes restantes</button>
                                </>
                              ) : null}
                            </div>
                          </details>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
            {inheritedSplit ? <div className="message-inherited-split">Historial de la conversación original</div> : null}
          </div>
        );
      })}
      {streamingStatus ? (
        <div className="message-row" data-streaming="1">
          <div style={{ maxWidth: "100%", flex: 1, minWidth: 0 }}>
            <div className="message-bubble assistant">
              <span className="content" dangerouslySetInnerHTML={{ __html: escapeHtml(streamingText || "Analizando").replace(/\n/g, "<br>") }} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ReadingModeOverlay() {
  const readingIndex = useStore(sessionStore, (s) => s.readingModeIndex);
  const messages = useStore(sessionStore, (s) => s.messages);
  const renderMarkdown = useStore(layoutStore, (s) => s.renderMarkdown);
  const open = readingIndex != null && readingIndex >= 0;
  const msg = open ? messages[readingIndex] : null;
  const html = msg ? formatMessageHtml(msg.content || "", 0, { markdown: !!renderMarkdown }) : "";
  useEffect(() => {
    if (!open) return;
    kickLazyIllustrations(document.getElementById("reading-mode-body"));
  }, [html, open]);
  return (
    <div id="reading-mode" className="reading-mode" hidden={!open} role="dialog" aria-modal="true" aria-label="Modo lectura">
      <div className="reading-mode-toolbar font-size-controls" role="toolbar" aria-label="Controles de lectura">
        <button type="button" id="reading-font-decrease" className="icon-btn font-size-btn" title="Reducir tamaño del texto" aria-label="Reducir tamaño del texto">−</button>
        <button type="button" id="reading-font-increase" className="icon-btn font-size-btn" title="Aumentar tamaño del texto" aria-label="Aumentar tamaño del texto">+</button>
        <span className="reading-mode-toolbar-sep" aria-hidden="true"></span>
        <button type="button" id="reading-mode-close" className="icon-btn font-size-btn reading-mode-close-btn" title="Cerrar modo lectura" aria-label="Cerrar modo lectura" onClick={() => sessionStore.set({ readingModeIndex: null })}>×</button>
      </div>
      <div className="reading-mode-stage">
        <div id="reading-mode-panel" className="reading-mode-panel">
          <div id="reading-mode-body" className="reading-mode-body" dangerouslySetInnerHTML={{ __html: html }} />
        </div>
      </div>
    </div>
  );
}
