import * as conversationsApi from "../api/conversations.js";
import * as modelsApi from "../api/models.js";
import { showError, showNotice } from "../store/ui.js";
import { sessionStore, saveLastConversationId, resetSession } from "../store/session.js";
import { settingsStore } from "../store/settings.js";
import { historyStore } from "../store/history.js";
import { imagesStore, persistImagesPrefs } from "../store/images.js";
import { updateLayout, setChatPanelVisible, isGalleryPanelVisible } from "../store/layout.js";
import { persistImagesPanel, applyImagesSnapshot, imagesSnapshotForConversation } from "./imagesPanel.js";
import { applyConversationTree, visibleMessages, latestLeafInSubtree } from "../lib/tree.js";
import { initialViewStartIndex, clampViewStartIndex } from "../lib/messageWindow.js";
import { getDefaultConversationTitle } from "../lib/dates.js";
import { buildModelParams } from "../lib/params.js";
import {
  illustrationNeedleInContent as contentHasIllustration,
  contentHasExactFilename,
} from "../lib/illustrationLocate.js";
import {
  applyConsultaChrome,
  refreshLeftHistory,
  refreshMessageTreePreservingExpansion,
  syncMessageHistoryActiveItem,
} from "./historyActions.js";
import { serializeRuleItems, hydrateChatRulesFromLibrary } from "./rulesActions.js";
import { loadModelContract, loadModels, loadParamsForProvider, applyConversationParams } from "./settingsActions.js";
import { loadOlderMessageInView } from "./messageWindowActions.js";

export { loadOlderMessageInView };

export { resetSession };

const collapsedMessageKeys = new Set();
const el = {
  conversationTitle: null,
};

export function scheduleScrollMessagesToBottom() {
  if (sessionStore.get().pendingReveal) return;
  requestAnimationFrame(() => {
    if (sessionStore.get().pendingReveal) return;
    const node = document.getElementById("messages-container");
    if (node) node.scrollTop = node.scrollHeight;
  });
}

export function scheduleScrollMessagesToTop() {
  requestAnimationFrame(() => {
    const node = document.getElementById("messages-container");
    if (node) node.scrollTop = 0;
  });
}

export function scrollMessagesToBottom() {
  const node = document.getElementById("messages-container");
  if (node) node.scrollTop = node.scrollHeight;
}

export function scrollMessagesToTop() {
  const node = document.getElementById("messages-container");
  if (node) node.scrollTop = 0;
}

async function persistPreviousConversation(previousId) {
  if (!previousId) return;
  const session = sessionStore.get();
  const payload = {};
  const instruction = (session.instructionOverride || "").trim() || null;
  payload.instruction_override = instruction;
  if (!session.autoTitle) {
    payload.title = (session.title || "").trim() || getDefaultConversationTitle();
  }
  if (Object.keys(payload).length > 0) {
    conversationsApi.patchConversation(previousId, payload).catch(() => {});
  }
}

function setFocusMessageId(messageId) {
  const id = messageId || null;
  sessionStore.set({ focusMessageId: id, consultaAssistantId: id });
  syncMessageHistoryActiveItem();
}

/**
 * Salir de la vista de mensaje aislado: al navegar el árbol, saltar desde la galería
 * o seguir conversando dejamos de limitar la transcripción a un único mensaje.
 */
export function clearIsolatedMessageView() {
  if (!sessionStore.get().messageViewOnly) return;
  sessionStore.set({
    messageViewOnly: false,
    messageViewOnlyMessageId: null,
    messageViewOnlyConversationId: null,
  });
}

export async function setCurrentConversation(conv, options = {}) {
  const previousId = sessionStore.get().conversationId;
  if (!(options.keepFocus || options.keepConsulta)) {
    setFocusMessageId(null);
  }
  applyConsultaChrome();
  if (previousId && (!conv || conv.id !== previousId)) {
    await persistPreviousConversation(previousId);
  }
  if (!conv) {
    resetSession();
    return;
  }
  const sameId = conv.id === previousId;
  if (!options.preserveView) {
    sessionStore.set({ collapsedMessageKeys: [] });
    collapsedMessageKeys.clear();
  }
  const tree = applyConversationTree(conv);
  const focusId = options.focusMessageId || null;
  let viewStartIndex;
  if (options.preserveView && !focusId) {
    viewStartIndex = clampViewStartIndex(tree.messages, sessionStore.get().viewStartIndex);
  } else {
    viewStartIndex = initialViewStartIndex(tree.messages, focusId);
  }
  if (focusId) setFocusMessageId(focusId);
  sessionStore.set({
    conversationId: conv.id,
    conversationKind: conv.kind || "chat",
    title: conv.title || "",
    autoTitle: Boolean(conv.auto_title),
    instructionOverride: conv.instruction_override || "",
    messageViewOnly: false,
    messageViewOnlyMessageId: null,
    messageViewOnlyConversationId: null,
    rules: Array.isArray(conv.system_instructions)
      ? conv.system_instructions
      : Array.isArray(conv.rules)
        ? conv.rules
        : [],
    ...tree,
    viewStartIndex,
    streamingText: "",
    streamingStatus: null,
    collapsedMessageKeys: options.preserveView ? sessionStore.get().collapsedMessageKeys : [],
  });
  hydrateChatRulesFromLibrary();
  saveLastConversationId(conv.id);
  // La selección de proveedor/modelo es global (sticky): una vez el usuario la elige,
  // abrir otra conversación no debe pisarla. Hasta entonces se adopta la de la conversación.
  const settings = settingsStore.get();
  if (!settings.modelSelectionLocal) {
    const provider = conv.provider || settings.currentProvider || "ollama";
    const model = conv.model_id || settings.currentModel || "";
    if (provider !== settings.currentProvider || model !== settings.currentModel) {
      settingsStore.set({ currentProvider: provider, currentModel: model });
    }
  }
  if (conv.provider) await loadParamsForProvider(settingsStore.get().currentProvider);
  await loadModels(true);
  await loadModelContract({ applyParamDefaults: !conv.model_params });
  if (conv.model_params) applyConversationParams(conv.model_params);
  if (conv.images && typeof conv.images === "object") {
    applyImagesSnapshot(conv.images);
  }
  if (conv.save_to_chromadb) settingsStore.set({ saveToChromadb: conv.save_to_chromadb });
  if (conv.history_turns != null) settingsStore.set({ historyTurns: conv.history_turns });
  applyAutoTitleUi(sessionStore.get().autoTitle);
  if (!options.skipScroll) {
    if (focusId || options.keepConsulta) scheduleScrollMessagesToTop();
    else scheduleScrollMessagesToBottom();
  }
  void sameId;
}

let saveRulesDebounceTimer;

export async function openConversation(id, options = {}) {
  if (!(options.keepFocus || options.focusMessageId)) setFocusMessageId(null);
  applyConsultaChrome();
  setChatPanelVisible(true);
  isGalleryPanelVisible();
  try {
    const conv = await conversationsApi.getConversation(id);
    await setCurrentConversation(conv, options);
  } catch (e) {
    showError("Error al abrir conversación: " + e.message);
  }
}

/** @deprecated Usar goToConversationTarget / openConversationAtMessage (misma ventana unificada). */
export async function openConsultaTurn(conversationId, assistantId) {
  if (!conversationId || !assistantId) return;
  updateLayout({ centerChatVisible: true });
  return openConversationAtMessage(conversationId, assistantId);
}

export async function newConversation() {
  setFocusMessageId(null);
  applyConsultaChrome();
  setChatPanelVisible(true);
  const settings = settingsStore.get();
  try {
    const conv = await conversationsApi.createConversation({
      title: getDefaultConversationTitle(),
      provider: settings.currentProvider || "ollama",
      model_id: settings.currentModel || (settings.models[0] || ""),
      kind: "chat",
      images: imagesSnapshotForConversation(),
      system_instructions: serializeRuleItems(sessionStore.get().rules),
    });
    await setCurrentConversation(conv);
    await refreshMessageTreePreservingExpansion();
    return conv;
  } catch (e) {
    showError("Error al crear conversación: " + e.message);
    return null;
  }
}

export async function newPromptGeneratorConversation() {
  setFocusMessageId(null);
  applyConsultaChrome();
  updateLayout({ centerChatVisible: true });
  const settings = settingsStore.get();
  try {
    const conv = await conversationsApi.createConversation({
      title: getDefaultConversationTitle(),
      provider: settings.currentProvider || "ollama",
      model_id: settings.currentModel || (settings.models[0] || ""),
      kind: "prompt_generator",
    });
    await setCurrentConversation(conv);
    await refreshMessageTreePreservingExpansion();
    return conv;
  } catch (e) {
    showError("Error al crear txt2img: " + e.message);
    return null;
  }
}

export async function saveConversationMeta() {
  const s = sessionStore.get();
  if (!s.conversationId) return;
  const payload = {
    title: (s.title || "").trim() || getDefaultConversationTitle(),
    auto_title: !!s.autoTitle,
    instruction_override: (s.instructionOverride || "").trim() || null,
    provider: settingsStore.get().currentProvider,
    model_id: settingsStore.get().currentModel,
    model_params: buildModelParams(),
  };
  try {
    await conversationsApi.patchConversation(s.conversationId, payload);
    await refreshLeftHistory();
  } catch (e) {
    showError("Error al guardar: " + e.message);
  }
}

export async function forkConversationFromMessage(messageId) {
  const { conversationId } = sessionStore.get();
  if (!messageId || !conversationId) return;
  try {
    const conv = await conversationsApi.forkConversation(conversationId, { message_id: messageId });
    await setCurrentConversation(conv);
    updateLayout({ composerCollapsed: false });
    await refreshMessageTreePreservingExpansion();
    showNotice("Conversación nueva. El historial se toma del mensaje original.");
  } catch (e) {
    showError("No se pudo crear la conversación: " + e.message);
  }
}

export function applyAutoTitleUi(enabled) {
  sessionStore.set({ autoTitle: Boolean(enabled) });
}

export async function commitConversationTitle() {
  el.conversationTitle = document.getElementById("conversation-title");
  if (!el.conversationTitle) return;
  const title = el.conversationTitle.value.trim() || getDefaultConversationTitle();
  if (el.conversationTitle.value !== title) el.conversationTitle.value = title;
  const currentConversationId = sessionStore.get().conversationId;
  if (!currentConversationId) return;
  try {
    await conversationsApi.patchConversation(
      currentConversationId,
      JSON.parse(JSON.stringify({ title, auto_title: false })),
    );
    sessionStore.set({ title, autoTitle: false });
    refreshLeftHistory();
  } catch (e) {
    showError("Error al guardar el título: " + e.message);
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("change", (e) => {
    if (e.target && e.target.id === "conversation-title") commitConversationTitle();
  });
}
el.conversationTitle && el.conversationTitle.addEventListener("change", commitConversationTitle);

export async function persistWorkspaceToConversation() {
  persistImagesPanel();
  const payload = { images: imagesSnapshotForConversation() };
  await saveConversationMeta();
  void payload;
}

export async function saveConversation() {
  await saveConversationMeta();
  await setCurrentConversation(
    await conversationsApi.getConversation(sessionStore.get().conversationId),
    { preserveView: true }
  );
}

function waitForMessagesPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(resolve);
    });
  });
}

function ensureMessageExpanded(messageId) {
  if (!messageId) return false;
  const keys = sessionStore.get().collapsedMessageKeys || [];
  const id = String(messageId);
  const next = keys.filter((k) => k !== id);
  if (next.length === keys.length) return false;
  sessionStore.set({ collapsedMessageKeys: next });
  return true;
}

export function illustrationNeedleInContent(content, filename, sceneId) {
  return contentHasIllustration(content, filename, sceneId);
}

export function findMessageWithIllustration(messages, filename, sceneId, preferredMessageId) {
  if (!Array.isArray(messages)) return null;
  const preferred = preferredMessageId
    ? messages.find((m) => m && String(m.id) === String(preferredMessageId)) || null
    : null;
  if (preferred) {
    if (contentHasExactFilename(preferred.content, filename)) return preferred;
    if (sceneId && illustrationNeedleInContent(preferred.content, null, sceneId)) return preferred;
  }
  if (filename) {
    for (let i = 0; i < messages.length; i++) {
      if (contentHasExactFilename(messages[i] && messages[i].content, filename)) {
        return messages[i];
      }
    }
  }
  if (preferred) return preferred;
  // Con messageId explícito no "robamos" la misma escena de otro mensaje.
  if (preferredMessageId) return null;
  if (!sceneId) return null;
  for (let i = 0; i < messages.length; i++) {
    if (illustrationNeedleInContent(messages[i] && messages[i].content, null, sceneId)) {
      return messages[i];
    }
  }
  return null;
}

function applyFocusMessageWindow(focusMessageId) {
  const state = sessionStore.get();
  const focusId = focusMessageId || null;
  const open = state.messages || [];
  let all = state.allMessages || [];
  if (focusId && open.some((m) => m.id === focusId) && !all.some((m) => m.id === focusId)) {
    all = open;
  } else if (!all.length) {
    all = open;
  }
  const messages = focusId ? visibleMessages(all, focusId) : open;
  sessionStore.set({
    activeLeafId: focusId || state.activeLeafId,
    allMessages: all,
    messages,
    viewStartIndex: initialViewStartIndex(messages, focusId),
    focusMessageId: focusId,
    consultaAssistantId: focusId,
  });
  syncMessageHistoryActiveItem();
}

async function revealMessageInConversation(conversationId, messageId, options = {}) {
  setChatPanelVisible(true);
  clearIsolatedMessageView();
  const current = sessionStore.get();

  const lookingForPhoto = !!(options.filename || options.sceneId);
  // Solo por filename: no pasar messageId (puede ser stale y “ganar” sin tener la foto).
  const photoInCurrent = lookingForPhoto
    ? findMessageWithIllustration(current.messages, options.filename, null, null)
    : null;
  const messageInCurrent =
    !!messageId && (current.messages || []).some((m) => m.id === messageId);

  // Si la foto ya está en el hilo abierto (p. ej. fork), no saltar al dueño.
  // Con búsqueda de foto, la mera presencia del messageId no basta (puede ser stale).
  let targetConv = conversationId || current.conversationId;
  if (photoInCurrent) {
    targetConv = current.conversationId;
  } else if (!lookingForPhoto && messageInCurrent && current.conversationId) {
    targetConv = current.conversationId;
  }
  if (!targetConv) return photoInCurrent || null;

  const sameConv = targetConv === current.conversationId;
  if (!sameConv) {
    await openConversation(targetConv, { skipScroll: true });
  }

  let resolved =
    findMessageWithIllustration(
      sessionStore.get().messages,
      options.filename,
      options.sceneId,
      messageId
    ) || photoInCurrent;
  let resolvedMessageId = (resolved && resolved.id) || messageId || null;

  const all = sessionStore.get().allMessages || [];
  const openMsgs = sessionStore.get().messages || [];
  const known =
    !!resolvedMessageId &&
    (openMsgs.some((m) => m && m.id === resolvedMessageId) ||
      all.some((m) => m && m.id === resolvedMessageId && !m.ephemeral_debug));

  if (resolvedMessageId && !known) {
    const ownOnly = (sessionStore.get().allMessages || []).filter((m) => m && !m.inherited && !m.ephemeral_debug);
    const leaf = latestLeafInSubtree(ownOnly.length ? ownOnly : sessionStore.get().allMessages, resolvedMessageId);
    const leafId = (leaf && leaf.id) || resolvedMessageId;
    await conversationsApi.patchConversation(targetConv, {
      active_leaf_message_id: leafId,
    });
    await openConversation(targetConv, {
      skipScroll: true,
      focusMessageId: resolvedMessageId,
    });
    resolved = findMessageWithIllustration(
      sessionStore.get().messages,
      options.filename,
      options.sceneId,
      resolvedMessageId
    );
    resolvedMessageId = (resolved && resolved.id) || resolvedMessageId;
  }

  if (resolvedMessageId) {
    const ownOnly = (sessionStore.get().allMessages || []).filter((m) => m && !m.inherited && !m.ephemeral_debug);
    const leaf = latestLeafInSubtree(ownOnly.length ? ownOnly : sessionStore.get().allMessages, resolvedMessageId);
    const leafId = (leaf && leaf.id) || resolvedMessageId;
    const prevLeaf = sessionStore.get().activeLeafId;
    applyFocusMessageWindow(resolvedMessageId);
    if (prevLeaf !== leafId) {
      conversationsApi
        .patchConversation(targetConv, { active_leaf_message_id: leafId })
        .catch(() => {});
      if (leafId !== resolvedMessageId) {
        await openConversation(targetConv, {
          skipScroll: true,
          focusMessageId: resolvedMessageId,
        });
        applyFocusMessageWindow(resolvedMessageId);
      }
    }
  } else {
    const msgs = sessionStore.get().messages || [];
    sessionStore.set({ viewStartIndex: initialViewStartIndex(msgs, null) });
  }

  const expandId = (resolved && resolved.id) || resolvedMessageId;
  if (ensureMessageExpanded(expandId)) await waitForMessagesPaint();
  return resolved;
}

function queueRevealInMessages(conversationId, messageId, options = {}) {
  const found = findMessageWithIllustration(
    sessionStore.get().messages,
    options.filename,
    options.sceneId,
    messageId
  );
  sessionStore.set({
    pendingReveal: {
      conversationId: sessionStore.get().conversationId || conversationId || null,
      messageId: (found && found.id) || messageId || null,
      filename: options.filename || null,
      sceneId: options.sceneId || null,
    },
  });
}

/** Punto único para ir a un mensaje/foto desde historial, galería, cola, debug, etc. */
export async function goToConversationTarget(target = {}) {
  const conversationId = target.conversationId || "";
  const messageId = target.messageId || "";
  const filename = target.filename || "";
  const sceneId = target.sceneId || "";
  if (filename || sceneId) {
    return openConversationAtIllustration(conversationId, messageId, { filename, sceneId });
  }
  return openConversationAtMessage(conversationId, messageId);
}

export async function openConversationAtMessage(conversationId, messageId) {
  try {
    await revealMessageInConversation(conversationId, messageId);
    const msgs = sessionStore.get().messages || [];
    const focusId = messageId || null;
    sessionStore.set({
      viewStartIndex: initialViewStartIndex(msgs, focusId),
      focusMessageId: focusId,
      consultaAssistantId: focusId,
    });
    syncMessageHistoryActiveItem();
    queueRevealInMessages(conversationId, messageId);
    updateLayout({ composerCollapsed: false });
  } catch (err) {
    showError("No se pudo abrir el mensaje: " + err.message);
  }
}

/** Clic en nodo del árbol de historial: hilo editable + hoja del subárbol. */
export async function openMessageTreeNode(conversationId, messageId) {
  historyStore.set({ treeSelectedMessageId: messageId || null });
  setChatPanelVisible(true);
  updateLayout({ composerCollapsed: false });
  document.documentElement.removeAttribute("data-history-consulta");
  return openConversationAtMessage(conversationId, messageId);
}

/**
 * Clic en un mensaje del listado: abre la conversación mostrando SOLO ese mensaje
 * (ni el prompt que lo generó ni el resto del hilo). El composer sigue disponible
 * para continuar la conversación.
 */
export async function openIsolatedMessage(conversationId, messageId) {
  if (!conversationId || !messageId) return;
  historyStore.set({ treeSelectedMessageId: messageId });
  setChatPanelVisible(true);
  updateLayout({ composerCollapsed: false });
  document.documentElement.removeAttribute("data-history-consulta");
  try {
    const conv = await conversationsApi.getConversation(conversationId);
    setFocusMessageId(messageId);
    await setCurrentConversation(conv, {
      skipScroll: true,
      keepFocus: true,
      focusMessageId: messageId,
      preserveView: true,
    });
    // La hoja activa pasa a ser el mensaje abierto: el panel pinta su camino y el
    // composer continúa desde ahí; el filtro deja visible solo ese mensaje.
    const tree = applyConversationTree(conv);
    sessionStore.set({
      allMessages: tree.allMessages,
      activeLeafId: messageId,
      messages: visibleMessages(tree.allMessages, messageId),
      messageViewOnly: true,
      messageViewOnlyMessageId: messageId,
      messageViewOnlyConversationId: conversationId,
      focusMessageId: messageId,
      consultaAssistantId: messageId,
      viewStartIndex: 0,
      streamingText: "",
      streamingStatus: null,
    });
    applyConsultaChrome();
    syncMessageHistoryActiveItem();
  } catch (e) {
    showError("No se pudo abrir el mensaje: " + e.message);
  }
}

export async function openConversationAtIllustration(conversationId, messageId, filenameOrOptions, sceneId) {
  const options =
    filenameOrOptions && typeof filenameOrOptions === "object"
      ? filenameOrOptions
      : { filename: filenameOrOptions || "", sceneId: sceneId || "" };
  try {
    const resolved = await revealMessageInConversation(conversationId, messageId, options);
    const focusId = (resolved && resolved.id) || messageId || null;
    const msgs = sessionStore.get().messages || [];
    sessionStore.set({
      viewStartIndex: initialViewStartIndex(msgs, focusId),
      focusMessageId: focusId,
      consultaAssistantId: focusId,
    });
    syncMessageHistoryActiveItem();
    queueRevealInMessages(conversationId, messageId, options);
  } catch (err) {
    showError("No se pudo abrir el mensaje: " + err.message);
  }
}

export async function deleteMessageFromHistory(conversationId, messageId) {
  try {
    await conversationsApi.deleteMessage(conversationId, messageId);
    const conv = await conversationsApi.getConversation(conversationId);
    await setCurrentConversation(conv, { preserveView: true, keepFocus: true });
  } catch (e) {
    showError("Error al eliminar mensaje: " + e.message);
  }
}
