import { createStore } from "./createStore.js";

export const LEFT_HISTORY_MODE_KEY = "leftHistoryMode";
export const LEFT_HISTORY_SORT_CONVERSATIONS_KEY = "leftHistorySortConversations";
export const LEFT_HISTORY_SORT_MESSAGES_KEY = "leftHistorySortMessages";

export const CONV_SORT_OPTIONS = [
  { value: "activity", label: "Actividad" },
  { value: "created_at", label: "Creación" },
];

export const MSG_SORT_OPTIONS = [
  { value: "message", label: "Mensaje" },
  { value: "image", label: "Imagen" },
];

export const CONV_GROUP_LABELS = { hoy: "Hoy", ayer: "Ayer", semana: "Semana", anteriores: "Antes" };

export const MESSAGE_HISTORY_PAGE_SIZE = 50;
export const MESSAGE_TREE_ROOT_PAGE_SIZE = 50;
export const MESSAGE_HISTORY_SEARCH_DEBOUNCE_MS = 280;

function normalizeMode(raw) {
  if (raw === "tree" || raw === "messages" || raw === "conversations") return "tree";
  return "tree";
}

function readMode() {
  try {
    const stored = localStorage.getItem(LEFT_HISTORY_MODE_KEY);
    const mode = normalizeMode(stored);
    if (stored !== "tree") {
      try {
        localStorage.setItem(LEFT_HISTORY_MODE_KEY, "tree");
      } catch (_) {}
    }
    return mode;
  } catch (_) {
    return "tree";
  }
}

function readConversationSort() {
  try {
    return localStorage.getItem(LEFT_HISTORY_SORT_CONVERSATIONS_KEY) === "created_at"
      ? "created_at"
      : "activity";
  } catch (_) {
    return "activity";
  }
}

function readMessageSort() {
  try {
    return localStorage.getItem(LEFT_HISTORY_SORT_MESSAGES_KEY) === "image" ? "image" : "message";
  } catch (_) {
    return "message";
  }
}

export function readStoredConversationSort() {
  return readConversationSort();
}

export function persistConversationSort(sort) {
  try {
    localStorage.setItem(
      LEFT_HISTORY_SORT_CONVERSATIONS_KEY,
      sort === "created_at" ? "created_at" : "activity"
    );
  } catch (_) {}
}

export function readStoredMessageSort() {
  return readMessageSort();
}

export function persistMessageSort(sort) {
  try {
    localStorage.setItem(LEFT_HISTORY_SORT_MESSAGES_KEY, sort === "image" ? "image" : "message");
  } catch (_) {}
}

export function persistLeftHistoryMode(mode) {
  try {
    localStorage.setItem(LEFT_HISTORY_MODE_KEY, normalizeMode(mode));
  } catch (_) {}
}

export const historyStore = createStore({
  mode: readMode(),
  conversationSort: readConversationSort(),
  messageSort: readMessageSort(),
  conversations: [],
  deletedConversations: [],
  messageHistoryItems: [],
  messageHistoryTotal: 0,
  messageHistoryQuery: "",
  messageHistorySearchIn: null,
  treeRoots: [],
  treeRootsTotal: 0,
  treeChildrenByParent: {},
  treeExpandedIds: {},
  treeSelectedMessageId: null,
  treeMultiSelectedIds: [],
  treeSelectionAnchorId: null,
  loading: false,
});

export function isMessagesHistoryMode(state = historyStore.get()) {
  return state.mode === "messages";
}

export function isTreeHistoryMode(state = historyStore.get()) {
  return state.mode === "tree" || state.mode !== "messages";
}

export function currentLeftHistorySort(state = historyStore.get()) {
  return isMessagesHistoryMode(state) ? state.messageSort : state.conversationSort;
}
