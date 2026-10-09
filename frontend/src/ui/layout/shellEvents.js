import { updateLayout, layoutStore, LAYOUT_KEYS } from "../../store/layout.js";
import { setLeftCollapsed, setComposerCollapsed, toggleDarkMode, toggleChatFullscreen, nudgeFont, applySideResize, beginSideResize } from "./LayoutEffects.jsx";
import { newConversation, newPromptGeneratorConversation, saveConversationMeta, resetSession } from "../../app/sessionActions.js";
import * as conversationsApi from "../../api/conversations.js";
import { sessionStore } from "../../store/session.js";
import { showError, showNotice } from "../../store/ui.js";
import { collapseAllMessages } from "../messages/MessagesPane.jsx";
import { enterGalleryView } from "../../app/galleryActions.js";
import { setGalleryPanelVisible } from "../../store/layout.js";
import { loadImageQueuePage, startImageQueuePoll } from "../../app/queueActions.js";
import { onComposerPrimaryClick, sendPromptGeneratorTurn } from "../../app/sendMessage.js";
import { changeProvider, changeModel, refreshModels, applyModelRecipe } from "../../app/settingsActions.js";
import { settingsStore } from "../../store/settings.js";
import { imagesStore } from "../../store/images.js";
import { updateImagesPref, loadImagesPromptModels, loadPlannerContract, renderPlannerRecipes } from "../../app/imagesPanel.js";
import { abortAllIllustrations } from "../../app/illustrate.js";
import {
  applyWorkspaceProfile,
  saveWorkspaceProfile,
  deleteWorkspaceProfile,
  getWorkspaceProfiles,
  applyPlannerRulePreset,
  savePlannerRulePreset,
  deletePlannerRulePreset,
} from "../../app/profilesActions.js";
import { debugStore, setStoredDebugLogSize, DEBUG_LOG_SIZE_STEP, DEBUG_LOG_SIZE_MIN, DEBUG_LOG_SIZE_MAX, setDebugPanelOpen, setDebugLogSize, toggleDebugJsonPath, toggleDebugEntryExpanded } from "../../store/debug.js";
import { decodeJsonPath } from "../../lib/debugJsonTree.js";

let drag = null;

/** Share del panel de chat a partir del arrastre vertical del splitter central. */
export function computeCenterPanelShare({
  startShare,
  startY,
  clientY,
  stackHeight,
  shareMin = LAYOUT_KEYS.SHARE_MIN,
  shareMax = LAYOUT_KEYS.SHARE_MAX,
}) {
  if (!(stackHeight > 0) || !Number.isFinite(clientY) || !Number.isFinite(startY)) {
    return startShare;
  }
  const next = startShare + (clientY - startY) / stackHeight;
  return Math.max(shareMin, Math.min(shareMax, next));
}

function measureCenterSplitStackHeight() {
  const chat = document.querySelector(".column-center > .chat-column");
  const gallery = document.getElementById("image-gallery-panel");
  const queue = document.getElementById("image-queue-panel");
  const bottom =
    gallery && !gallery.hidden
      ? gallery
      : queue && !queue.hidden
        ? queue
        : null;
  if (!chat || !bottom) return 0;
  const top = chat.getBoundingClientRect().top;
  const bottomEdge = bottom.getBoundingClientRect().bottom;
  return Math.max(0, bottomEdge - top);
}

export function onAppPointerDown(e) {
  const handle = e.target.closest("#sidebar-left-splitter, #sidebar-right-splitter, #center-panels-splitter");
  if (!handle) return;
  if (e.button != null && e.button !== 0) return;
  e.preventDefault();
  const layout = layoutStore.get();
  if (handle.id === "sidebar-left-splitter") {
    drag = beginSideResize("left", e.clientX, layout.leftWidthPx);
    document.body.classList.add("side-panels-resizing");
  } else if (handle.id === "sidebar-right-splitter") {
    drag = beginSideResize("right", e.clientX, layout.rightWidthPx);
    document.body.classList.add("side-panels-resizing");
  } else {
    drag = {
      side: "center",
      startY: e.clientY,
      startShare: layout.centerChatGalleryShare,
      stackHeight: measureCenterSplitStackHeight(),
    };
    document.body.classList.add("center-panels-resizing");
  }
  if (typeof handle.setPointerCapture === "function" && e.pointerId != null) {
    try {
      handle.setPointerCapture(e.pointerId);
    } catch (_) {}
  }
}

export function onAppPointerMove(e) {
  if (!drag) return;
  if (drag.side === "center") {
    const share = computeCenterPanelShare({
      startShare: drag.startShare,
      startY: drag.startY,
      clientY: e.clientY,
      stackHeight: drag.stackHeight,
    });
    updateLayout({ centerChatGalleryShare: share });
    return;
  }
  applySideResize(drag, e.clientX);
}

export function onAppPointerUp() {
  if (!drag) return;
  drag = null;
  document.body.classList.remove("side-panels-resizing");
  document.body.classList.remove("center-panels-resizing");
}

export async function onAppClick(e) {
  const imageLink = e.target.closest(".debug-image-link");
  if (imageLink) {
    e.preventDefault();
    const { goToConversationTarget } = await import("../../app/sessionActions.js");
    goToConversationTarget({
      conversationId: imageLink.getAttribute("data-conversation-id") || "",
      messageId: imageLink.getAttribute("data-message-id") || "",
      filename: imageLink.getAttribute("data-filename") || "",
      sceneId: imageLink.getAttribute("data-scene-id") || "",
    });
    return;
  }
  const jsonToggle = e.target.closest(".json-toggle");
  if (jsonToggle) {
    e.preventDefault();
    e.stopPropagation();
    const entry = jsonToggle.closest(".debug-entry");
    const entryId = entry && entry.getAttribute("data-debug-id");
    const encoded = jsonToggle.getAttribute("data-json-path") || "";
    if (entryId && encoded) toggleDebugJsonPath(entryId, decodeJsonPath(encoded));
    return;
  }
  const entryToggle = e.target.closest(".debug-entry-toggle");
  if (entryToggle) {
    e.preventDefault();
    e.stopPropagation();
    const entry = entryToggle.closest(".debug-entry");
    const entryId = entry && entry.getAttribute("data-debug-id");
    if (entryId) toggleDebugEntryExpanded(entryId);
    return;
  }
  const btn = e.target.closest("button, [role='tab']");
  if (!btn) return;
  const { id } = btn;
  switch (id) {
    case "btn-collapse-left":
      setLeftCollapsed(true);
      break;
    case "btn-expand-left":
      setLeftCollapsed(false);
      break;
    case "btn-collapse-composer":
      setComposerCollapsed(true);
      break;
    case "btn-expand-composer":
      setComposerCollapsed(false);
      break;
    case "btn-chat-fullscreen":
      toggleChatFullscreen();
      break;
    case "btn-new-chat":
      newConversation();
      break;
    case "btn-prompt-generator":
      newPromptGeneratorConversation();
      break;
    case "btn-center-chat":
      updateLayout({ centerChatVisible: !layoutStore.get().centerChatVisible });
      break;
    case "btn-image-gallery": {
      const on = !layoutStore.get().centerGalleryVisible;
      updateLayout({ centerGalleryVisible: on, centerQueueVisible: on ? false : layoutStore.get().centerQueueVisible });
      if (on) enterGalleryView();
      break;
    }
    case "btn-image-queue": {
      const on = !layoutStore.get().centerQueueVisible;
      updateLayout({ centerQueueVisible: on, centerGalleryVisible: on ? false : layoutStore.get().centerGalleryVisible });
      if (on) {
        loadImageQueuePage();
        startImageQueuePoll();
      }
      break;
    }
    case "btn-send":
      onComposerPrimaryClick();
      break;
    case "btn-generate-prompt":
      sendPromptGeneratorTurn({ force: true });
      break;
    case "btn-save":
      saveConversationMeta();
      break;
    case "btn-clear-memory": {
      const id = sessionStore.get().conversationId;
      if (!id) return;
      if (!window.confirm("¿Borrar esta conversación?")) return;
      try {
        await conversationsApi.deleteConversation(id);
        resetSession();
        showNotice("Conversación movida a la papelera.");
      } catch (err) {
        showError(err.message);
      }
      break;
    }
    case "btn-font-size-decrease":
    case "pref-font-decrease":
    case "reading-font-decrease":
      nudgeFont("chat", -0.05);
      break;
    case "btn-font-size-increase":
    case "pref-font-increase":
    case "reading-font-increase":
      nudgeFont("chat", 0.05);
      break;
    case "pref-font-base-decrease":
      nudgeFont("base", -0.05);
      break;
    case "pref-font-base-increase":
      nudgeFont("base", 0.05);
      break;
    case "pref-font-left-decrease":
      nudgeFont("left", -0.05);
      break;
    case "pref-font-left-increase":
      nudgeFont("left", 0.05);
      break;
    case "pref-font-right-decrease":
      nudgeFont("right", -0.05);
      break;
    case "pref-font-right-increase":
      nudgeFont("right", 0.05);
      break;
    case "pref-image-decrease":
    case "reading-image-decrease":
      nudgeFont("image", -0.05);
      break;
    case "pref-image-increase":
    case "reading-image-increase":
      nudgeFont("image", 0.05);
      break;
    case "btn-collapse-all-messages":
    case "pref-collapse-all-messages":
      collapseAllMessages();
      break;
    case "btn-refresh-models":
      refreshModels();
      break;
    case "images-debug-stop":
      abortAllIllustrations();
      break;
    case "debug-chat-toggle":
      setDebugPanelOpen("chat", !debugStore.get().chatOpen);
      break;
    case "debug-images-toggle":
      setDebugPanelOpen("images", !debugStore.get().imagesOpen);
      break;
    case "pref-debug-log-decrease":
      setDebugLogSize(-DEBUG_LOG_SIZE_STEP);
      break;
    case "pref-debug-log-increase":
      setDebugLogSize(DEBUG_LOG_SIZE_STEP);
      break;
    case "btn-workspace-profile-apply": {
      const sel = document.getElementById("workspace-profile-select");
      if (sel && sel.value) applyWorkspaceProfile(sel.value);
      break;
    }
    case "btn-workspace-profile-save": {
      const sel = document.getElementById("workspace-profile-select");
      const name = window.prompt("Nombre del perfil");
      if (name) saveWorkspaceProfile({ name, profileId: sel && sel.value, asNew: false });
      break;
    }
    case "btn-workspace-profile-save-as": {
      const name = window.prompt("Nombre del perfil");
      if (name) saveWorkspaceProfile({ name, asNew: true });
      break;
    }
    case "btn-workspace-profile-delete": {
      const sel = document.getElementById("workspace-profile-select");
      if (sel && sel.value) deleteWorkspaceProfile(sel.value);
      break;
    }
    case "btn-planner-rule-preset-apply": {
      const sel = document.getElementById("planner-rule-preset-select");
      if (sel && sel.value) applyPlannerRulePreset(sel.value);
      break;
    }
    case "btn-planner-rule-preset-save": {
      const sel = document.getElementById("planner-rule-preset-select");
      const name = window.prompt("Nombre del preset de reglas");
      if (name) savePlannerRulePreset({ name, presetId: sel && sel.value, asNew: false });
      break;
    }
    case "btn-planner-rule-preset-save-as": {
      const name = window.prompt("Nombre del preset de reglas");
      if (name) savePlannerRulePreset({ name, asNew: true });
      break;
    }
    case "btn-planner-rule-preset-delete": {
      const sel = document.getElementById("planner-rule-preset-select");
      if (sel && sel.value) deletePlannerRulePreset(sel.value);
      break;
    }
    case "btn-add-rule": {
      const title = document.getElementById("rule-new-title");
      const content = document.getElementById("rule-new-input");
      const { createAndAddRule } = await import("../../app/rulesActions.js");
      createAndAddRule({ title: title?.value || "", content: content?.value || "", scope: "chat" });
      if (title) title.value = "";
      if (content) content.value = "";
      break;
    }
    case "btn-add-library-rule": {
      const sel = document.getElementById("rule-library-select");
      const { addLibraryRule } = await import("../../app/rulesActions.js");
      if (sel && sel.value) addLibraryRule(sel.value, "chat");
      break;
    }
    case "btn-add-planner-rule": {
      const title = document.getElementById("planner-rule-new-title");
      const content = document.getElementById("planner-rule-new-input");
      const { createAndAddRule } = await import("../../app/rulesActions.js");
      createAndAddRule({ title: title?.value || "", content: content?.value || "", scope: "planner" });
      break;
    }
    case "btn-add-planner-library-rule": {
      const sel = document.getElementById("planner-rule-library-select");
      const { addLibraryRule } = await import("../../app/rulesActions.js");
      if (sel && sel.value) addLibraryRule(sel.value, "planner");
      break;
    }
    case "conversation-image-filter-notice-dismiss": {
      const { clearGalleryToolbarFilters } = await import("../../app/galleryActions.js");
      clearGalleryToolbarFilters();
      break;
    }
    default:
      break;
  }
  if (btn.classList && btn.classList.contains("chat-image-filter-notice-open")) {
    setGalleryPanelVisible(true);
  }
  if (btn.dataset.sidebarTab) {
    updateLayout({ sidebarTab: btn.dataset.sidebarTab });
  }
  const acc = btn.closest(".accordion-header");
  if (acc) {
  const section = btn.closest(".accordion-section");
    if (section && section.dataset.accordionSection) {
      const id = section.dataset.accordionSection;
      const open = !section.classList.contains("is-open");
      const parent = section.parentElement;
      const next = { ...layoutStore.get().accordion, [id]: open };
      if (parent) {
        Array.from(parent.children).forEach((el) => {
          if (el.classList.contains("accordion-section") && el !== section) {
            const oid = el.dataset.accordionSection;
            if (oid) next[oid] = false;
          }
        });
      }
      updateLayout({ accordion: next });
      section.classList.toggle("is-open", open);
      acc.setAttribute("aria-expanded", open ? "true" : "false");
      if (parent) {
        Array.from(parent.children).forEach((el) => {
          if (el.classList.contains("accordion-section") && el !== section) {
            el.classList.toggle("is-open", false);
            const b = el.querySelector(":scope > .accordion-header");
            if (b) b.setAttribute("aria-expanded", "false");
          }
        });
      }
    }
  }
}

export function onAppKeyDown(e) {
  const t = e.target;
  if (!t || t.id !== "message-input") return;
  if (e.key !== "Enter" || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey || e.isComposing) return;
  e.preventDefault();
  onComposerPrimaryClick();
}

export function onAppChange(e) {
  const t = e.target;
  if (!t) return;
  if (t.id === "dark-mode-toggle") toggleDarkMode(t.checked);
  if (t.id === "render-markdown-toggle") updateLayout({ renderMarkdown: t.checked });
  if (t.id === "auto-scroll-during-generation") updateLayout({ autoScrollDuringGeneration: t.checked });
  if (t.id === "conversation-title") {
    sessionStore.set({ title: t.value });
  }
  if (t.id === "instruction-override") sessionStore.set({ instructionOverride: t.value });
  if (t.id === "message-input") sessionStore.set({ composerDraft: t.value });
  if (t.id === "provider-select") changeProvider(t.value);
  if (t.id === "model-select") changeModel(t.value);
  if (t.id === "save-to-chromadb-select") settingsStore.set({ saveToChromadb: t.value });
  if (t.id === "history-turns-input") settingsStore.set({ historyTurns: Number(t.value) || 20 });
  if (t.id === "images-enabled") updateImagesPref({ enabled: t.checked });
  if (t.id === "images-use-chat-config") {
    updateImagesPref({ use_chat_config: t.checked });
    renderPlannerRecipes();
  }
  if (t.id === "images-visual-consistency") updateImagesPref({ visual_consistency: t.checked });
  if (t.id === "images-scene-selection-strategy") {
    updateImagesPref({ scene_selection_strategy: t.value });
  }
  if (t.id === "images-per-response") updateImagesPref({ images_per_response: Number(t.value) || 2 });
  if (t.id === "images-batch-size") updateImagesPref({ batch_size: Number(t.value) || 10 });
  if (t.id === "images-retries") updateImagesPref({ retries: Number(t.value) || 0 });
  if (t.id === "images-prompt") updateImagesPref({ prompt: t.value });
  if (t.id === "images-prompt-provider") {
    updateImagesPref({ prompt_provider: t.value, prompt_model_params: {} });
    loadImagesPromptModels().then(() => loadPlannerContract());
  }
  if (t.id === "images-prompt-model") {
    updateImagesPref({ prompt_model: t.value, prompt_model_params: {} });
    loadPlannerContract();
  }
  if (t.id === "settings-think") {
    const canonical = document.getElementById("param-think");
    if (canonical) {
      canonical.value = t.value;
      canonical.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  if (t.id === "planner-think") {
    const raw = t.value;
    const think = raw === "true" ? true : raw === "false" ? false : raw;
    const current = imagesStore.get().prefs.prompt_model_params || {};
    updateImagesPref({ prompt_model_params: { ...current, think } });
    renderPlannerRecipes();
  }
  if (t.dataset.controlId) {
    const id = t.dataset.controlId;
    let value = t.value;
    if (t.type === "number") value = t.value === "" ? null : Number(t.value);
    settingsStore.set((s) => ({
      ...s,
      paramsValues: { ...s.paramsValues, [id]: value },
      paramsSource: "user",
    }));
  }
  if (t.classList.contains("sidebar-tab") || t.dataset.sidebarTab) {
    /* handled in click */
  }
}
