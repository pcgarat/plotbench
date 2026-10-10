import * as conversationsApi from "../api/conversations.js";
import * as messageTreeApi from "../api/messageTree.js";
import { showError, showNotice } from "../store/ui.js";
import {
  historyStore,
  isMessagesHistoryMode,
  persistConversationSort,
  persistLeftHistoryMode,
  persistMessageSort,
  persistMessageSortDirection,
  persistMessageSearchIn,
  persistMessageShowDeleted,
  MESSAGE_HISTORY_SEARCH_DEBOUNCE_MS,
  MESSAGE_TREE_ROOT_PAGE_SIZE,
  CONV_SORT_OPTIONS,
  MESSAGE_SORT_OPTIONS,
  MESSAGE_SORT_DIRECTION_ASC,
  MESSAGE_SORT_DIRECTION_DESC,
  defaultMessageSortDirection,
  LEFT_HISTORY_MODE_CONVERSATIONS,
  LEFT_HISTORY_MODE_MESSAGES,
  readStoredConversationSort,
  readStoredMessageSort,
  readStoredMessageSortDirection,
  readStoredMessageSearchIn,
  readStoredMessagePageSize,
  persistMessagePageSize,
} from "../store/history.js";
import { sessionStore, resetSession } from "../store/session.js";
import {
  isAdditiveHistoryClick,
  isRangeHistoryClick,
  nextHistorySelection,
  selectionForContextMenu,
} from "../lib/historySelection.js";
import { visibleHistoryNodeIds } from "../lib/historyVisibleNodes.js";
import {
  clampPage,
  normalizePageSize,
  pageOffset,
  totalPages,
} from "../lib/messagePagination.js";

let messageListLoadSeq = 0;
let treeLoadSeq = 0;
let searchTimer = null;

export async function loadConversations() {
  const sort = readStoredConversationSort();
  try {
    const list = await conversationsApi.listConversations(sort);
    historyStore.set({ conversations: Array.isArray(list) ? list : [], loading: false });
    await loadDeletedConversations();
  } catch (e) {
    showError("Error al cargar conversaciones: " + e.message);
  }
}

export async function loadDeletedConversations() {
  try {
    const deleted = await conversationsApi.listDeletedConversations();
    historyStore.set({ deletedConversations: Array.isArray(deleted) ? deleted : [] });
  } catch (_) {
    historyStore.set({ deletedConversations: [] });
  }
}

/** Carga una página del listado de mensajes del panel izquierdo (vista por defecto). */
export async function loadMessageList(options = {}) {
  const state = historyStore.get();
  const pageSize = normalizePageSize(options.pageSize ?? state.messagePageSize);
  const sort = state.messageSort || readStoredMessageSort();
  const direction =
    state.messageSortDirection ||
    readStoredMessageSortDirection() ||
    defaultMessageSortDirection(sort);
  const q = (state.messageListQuery || "").trim();
  // El filtro, el orden y el tamaño de página reinician a la primera página; solo la
  // navegación explícita (options.resetPage === false) respeta la página pedida.
  const requestedPage = options.resetPage === false ? state.messagePage ?? 1 : options.page ?? 1;
  const page = clampPage(requestedPage, totalPages(state.messageListTotal, pageSize));
  const seq = ++messageListLoadSeq;
  const params = new URLSearchParams();
  params.set("sort", sort);
  params.set("direction", direction);
  params.set("limit", String(pageSize));
  params.set("offset", String(pageOffset(page, pageSize)));
  if (q) {
    params.set("q", q);
    params.set("search_in", state.messageSearchIn || readStoredMessageSearchIn());
  }
  if (state.messageModelFilter) params.set("model_id", state.messageModelFilter);
  if (state.messageShowDeleted) params.set("include_deleted", "true");
  try {
    const data = await conversationsApi.listMessagesList(params);
    if (seq !== messageListLoadSeq) return;
    const incoming = (data && data.items) || [];
    const total = data && typeof data.total === "number" ? data.total : incoming.length;
    historyStore.set({
      messageListItems: incoming,
      messageListTotal: total,
      messageModels: (data && data.models) || [],
      hasMissingModels: !!(data && data.has_missing_model),
      messagePageSize: pageSize,
      messagePage: clampPage(page, totalPages(total, pageSize)),
      loading: false,
    });
  } catch (e) {
    if (seq !== messageListLoadSeq) return;
    showError("Error al cargar mensajes: " + e.message);
  }
}

/** Navega a una página concreta del listado de mensajes (1-based). */
export function goToMessagePage(page) {
  const state = historyStore.get();
  const pageSize = normalizePageSize(state.messagePageSize);
  const target = clampPage(page, totalPages(state.messageListTotal, pageSize));
  if (target === state.messagePage && (state.messageListItems || []).length) return;
  historyStore.set({ messagePage: target });
  loadMessageList({ resetPage: false });
}

export function goToFirstMessagePage() {
  goToMessagePage(1);
}

export function goToLastMessagePage() {
  const state = historyStore.get();
  goToMessagePage(totalPages(state.messageListTotal, normalizePageSize(state.messagePageSize)));
}

export function goToPrevMessagePage() {
  goToMessagePage((historyStore.get().messagePage ?? 1) - 1);
}

export function goToNextMessagePage() {
  goToMessagePage((historyStore.get().messagePage ?? 1) + 1);
}

/** Cambia cuántos elementos se muestran por página y vuelve a la primera. */
export function setMessagePageSize(size) {
  const pageSize = normalizePageSize(size);
  persistMessagePageSize(pageSize);
  historyStore.set({ messagePageSize: pageSize });
  if (isMessagesHistoryMode()) loadMessageList();
}

/** Raíces del árbol de conversaciones (paginación incremental). */
export async function loadMessageTreeRoots(options = {}) {
  const append = !!options.append;
  const seq = ++treeLoadSeq;
  const state = historyStore.get();
  const offset = append ? (state.treeRoots || []).length : 0;
  try {
    const data = await messageTreeApi.listMessageTreeRoots({
      limit: MESSAGE_TREE_ROOT_PAGE_SIZE,
      offset,
    });
    if (seq !== treeLoadSeq) return;
    const incoming = (data && data.items) || [];
    const nextRoots = append ? (state.treeRoots || []).concat(incoming) : incoming;
    historyStore.set({
      treeRoots: nextRoots,
      treeRootsTotal: data && typeof data.total === "number" ? data.total : nextRoots.length,
      treeChildrenByParent: append ? state.treeChildrenByParent : {},
      treeExpandedIds: append ? state.treeExpandedIds : {},
      loading: false,
    });
    await loadDeletedConversations();
  } catch (e) {
    if (seq !== treeLoadSeq) return;
    showError("Error al cargar el árbol de mensajes: " + e.message);
  }
}

export async function loadMessageTreeChildren(messageId) {
  if (!messageId) return;
  try {
    const kids = await messageTreeApi.listMessageTreeChildren(messageId);
    const map = { ...(historyStore.get().treeChildrenByParent || {}) };
    map[messageId] = Array.isArray(kids) ? kids : [];
    historyStore.set({ treeChildrenByParent: map });
  } catch (e) {
    showError("Error al expandir el árbol: " + e.message);
  }
}

export async function toggleMessageTreeNode(messageId) {
  if (!messageId) return;
  const state = historyStore.get();
  const expanded = { ...(state.treeExpandedIds || {}) };
  if (expanded[messageId]) {
    delete expanded[messageId];
    historyStore.set({ treeExpandedIds: expanded });
    return;
  }
  expanded[messageId] = true;
  historyStore.set({ treeExpandedIds: expanded });
  if (!(state.treeChildrenByParent || {})[messageId]) {
    await loadMessageTreeChildren(messageId);
  }
}

export async function refreshMessageTreePreservingExpansion() {
  const prevExpanded = { ...(historyStore.get().treeExpandedIds || {}) };
  await loadMessageTreeRoots();
  const ids = Object.keys(prevExpanded);
  if (!ids.length) return;
  historyStore.set({ treeExpandedIds: prevExpanded });
  await Promise.all(ids.map((id) => loadMessageTreeChildren(id)));
}

/** Refresca la vista activa del panel izquierdo (mensajes o conversaciones). */
export async function refreshLeftHistory() {
  if (isMessagesHistoryMode()) return loadMessageList();
  return refreshMessageTreePreservingExpansion();
}

export async function setLeftHistoryMode(mode) {
  const next = mode === LEFT_HISTORY_MODE_CONVERSATIONS
    ? LEFT_HISTORY_MODE_CONVERSATIONS
    : LEFT_HISTORY_MODE_MESSAGES;
  persistLeftHistoryMode(next);
  historyStore.set({ mode: next });
  document.documentElement.removeAttribute("data-history-consulta");
  await refreshLeftHistory();
}

export function onLeftHistorySortChange(value) {
  if (isMessagesHistoryMode()) {
    const direction = defaultMessageSortDirection(value);
    persistMessageSort(value);
    persistMessageSortDirection(direction);
    historyStore.set({ messageSort: value, messageSortDirection: direction });
    loadMessageList();
  } else {
    const sort = value === "created_at" ? "created_at" : "activity";
    persistConversationSort(sort);
    historyStore.set({ conversationSort: sort });
    loadMessageTreeRoots();
  }
}

export function onMessageSortDirectionToggle() {
  const state = historyStore.get();
  const current =
    state.messageSortDirection || defaultMessageSortDirection(state.messageSort || "date");
  const next = current === MESSAGE_SORT_DIRECTION_ASC
    ? MESSAGE_SORT_DIRECTION_DESC
    : MESSAGE_SORT_DIRECTION_ASC;
  persistMessageSortDirection(next);
  historyStore.set({ messageSortDirection: next });
  if (isMessagesHistoryMode()) loadMessageList();
}

export function onMessageHistorySearchInput(value) {
  historyStore.set({ messageListQuery: value });
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchTimer = null;
    if (!isMessagesHistoryMode()) return;
    loadMessageList();
  }, MESSAGE_HISTORY_SEARCH_DEBOUNCE_MS);
}

export function onMessageSearchInChange(value) {
  persistMessageSearchIn(value);
  historyStore.set({ messageSearchIn: value });
  if (isMessagesHistoryMode()) loadMessageList();
}

export function onMessageModelFilterChange(value) {
  historyStore.set({ messageModelFilter: value || "" });
  if (isMessagesHistoryMode()) loadMessageList();
}

/** Muestra u oculta en el listado los mensajes de conversaciones en la papelera. */
export function onMessageShowDeletedToggle(value) {
  const next = !!value;
  persistMessageShowDeleted(next);
  historyStore.set({ messageShowDeleted: next });
  if (isMessagesHistoryMode()) loadMessageList();
}

export async function deleteConversationFromHistory(id) {
  try {
    await conversationsApi.deleteConversation(id);
    if (sessionStore.get().conversationId === id) resetSession();
    await refreshLeftHistory();
    showNotice("Conversación movida a la papelera.");
  } catch (e) {
    showError("Error al borrar: " + e.message);
  }
}

export async function restoreConversationFromTrash(id) {
  try {
    await conversationsApi.restoreConversation(id);
    await refreshLeftHistory();
    showNotice("Conversación restaurada.");
  } catch (e) {
    showError("Error al restaurar: " + e.message);
  }
}

export async function permanentlyDeleteFromTrash(id) {
  if (!window.confirm("¿Eliminar definitivamente esta conversación? No se podrá recuperar.")) {
    return;
  }
  try {
    await conversationsApi.permanentlyDeleteConversation(id);
    if (sessionStore.get().conversationId === id) resetSession();
    await refreshLeftHistory();
    showNotice("Conversación eliminada definitivamente.");
  } catch (e) {
    showError("Error al eliminar: " + e.message);
  }
}

export async function emptyTrash() {
  const n = (historyStore.get().deletedConversations || []).length;
  if (!n) return;
  if (!window.confirm(`¿Vaciar la papelera (${n})? No se podrá recuperar.`)) {
    return;
  }
  try {
    const result = await conversationsApi.purgeDeletedConversations();
    const currentId = sessionStore.get().conversationId;
    const purgedIds = (result && result.ids) || [];
    if (currentId && purgedIds.includes(currentId)) resetSession();
    await refreshLeftHistory();
    showNotice(
      "Papelera vaciada (" + ((result && result.deleted) || purgedIds.length || n) + ")."
    );
  } catch (e) {
    showError("Error al vaciar papelera: " + e.message);
  }
}

export async function clearConversationHistory(id) {
  try {
    await conversationsApi.clearConversationMessages(id);
    if (sessionStore.get().conversationId === id) {
      sessionStore.set({ messages: [], allMessages: [], activeLeafId: null, viewStartIndex: 0 });
    }
    await refreshLeftHistory();
    showNotice("Historial de mensajes limpiado.");
  } catch (e) {
    showError("Error al limpiar: " + e.message);
  }
}

export function syncLeftHistorySortControl() {
  return isMessagesHistoryMode() ? MESSAGE_SORT_OPTIONS : CONV_SORT_OPTIONS;
}

export function currentLeftHistorySort() {
  const s = historyStore.get();
  return isMessagesHistoryMode(s) ? s.messageSort : s.conversationSort;
}

export function applyConsultaChrome() {
  document.documentElement.removeAttribute("data-history-consulta");
}

export function syncMessageHistoryActiveItem() {
  const list = document.getElementById("conversations-list");
  const focusId = sessionStore.get().focusMessageId || sessionStore.get().consultaAssistantId;
  historyStore.set({ treeSelectedMessageId: focusId || null });
  if (!list) return;
  list.querySelectorAll(".message-history-item, .message-tree-item, .message-list-item").forEach((node) => {
    node.classList.toggle("active", node.dataset.id === focusId);
  });
}

export function messageHistoryWhenIso(item, sort) {
  return sort === "photos" && item.latest_image_at ? item.latest_image_at : item.created_at;
}

export function currentHistoryVisibleIds(state = historyStore.get()) {
  return visibleHistoryNodeIds(state.treeRoots, state.treeChildrenByParent, state.treeExpandedIds);
}

export function applyHistoryNodeClick(nodeId, event, visibleIds) {
  const additive = isAdditiveHistoryClick(event);
  const range = isRangeHistoryClick(event);
  const state = historyStore.get();
  const next = nextHistorySelection({
    visibleIds: visibleIds || currentHistoryVisibleIds(state),
    selectedIds: state.treeMultiSelectedIds || [],
    anchorId: state.treeSelectionAnchorId,
    clickedId: nodeId,
    additive,
    range,
  });
  historyStore.set({
    treeMultiSelectedIds: next.selectedIds,
    treeSelectionAnchorId: next.anchorId || null,
  });
  return { shouldOpen: !additive && !range };
}

export function applyHistoryNodeContextMenu(nodeId) {
  const next = selectionForContextMenu(historyStore.get().treeMultiSelectedIds || [], nodeId);
  historyStore.set({
    treeMultiSelectedIds: next.selectedIds,
    ...(next.anchorId ? { treeSelectionAnchorId: next.anchorId } : {}),
  });
}

export function clearHistorySelection() {
  historyStore.set({ treeMultiSelectedIds: [], treeSelectionAnchorId: null });
}

function historyDeleteNotice(result) {
  const trashed = (result && result.trashed_conversation_ids) || [];
  const deleted = (result && result.deleted_message_ids) || [];
  if (trashed.length && !deleted.length) {
    return trashed.length === 1
      ? "Conversación movida a la papelera."
      : `${trashed.length} conversaciones movidas a la papelera.`;
  }
  if (deleted.length && !trashed.length) {
    return "Rama del fork eliminada.";
  }
  return "Historial actualizado.";
}

export async function deleteSelectedHistoryNodes() {
  const ids = historyStore.get().treeMultiSelectedIds || [];
  if (!ids.length) return;
  const label = ids.length === 1 ? "este elemento" : `${ids.length} elementos`;
  if (!window.confirm(`¿Eliminar ${label} del historial?`)) {
    return;
  }
  try {
    const result = await messageTreeApi.deleteHistoryNodes(ids);
    const currentId = sessionStore.get().conversationId;
    const trashed = (result && result.trashed_conversation_ids) || [];
    const deleted = new Set((result && result.deleted_message_ids) || []);
    const sessionIds = (sessionStore.get().allMessages || sessionStore.get().messages || []).map(
      (m) => m && m.id
    );
    const hitOpenThread = sessionIds.some((id) => deleted.has(id));
    clearHistorySelection();
    if (currentId && trashed.includes(currentId)) {
      resetSession();
    } else if (hitOpenThread && currentId) {
      const { setCurrentConversation } = await import("./sessionActions.js");
      const conv = await conversationsApi.getConversation(currentId);
      await setCurrentConversation(conv, { preserveView: true });
    }
    await refreshMessageTreePreservingExpansion();
    showNotice(historyDeleteNotice(result));
  } catch (e) {
    showError("Error al borrar: " + e.message);
  }
}
