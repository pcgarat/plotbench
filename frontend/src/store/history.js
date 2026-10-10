import { createStore } from "./createStore.js";
import { MESSAGE_PAGE_SIZE_OPTIONS, normalizePageSize } from "../lib/messagePagination.js";

export const LEFT_HISTORY_MODE_KEY = "leftHistoryMode";
export const LEFT_HISTORY_SORT_CONVERSATIONS_KEY = "leftHistorySortConversations";
export const LEFT_HISTORY_SORT_MESSAGES_KEY = "leftHistorySortMessages";
export const LEFT_HISTORY_SORT_DIRECTION_KEY = "leftHistorySortDirection";
export const LEFT_HISTORY_SEARCH_IN_KEY = "leftHistorySearchIn";
export const LEFT_HISTORY_PAGE_SIZE_KEY = "leftHistoryPageSize";
export const LEFT_HISTORY_SHOW_DELETED_KEY = "leftHistoryShowDeleted";

/** Vistas del panel izquierdo: listado de mensajes (por defecto) o de conversaciones. */
export const LEFT_HISTORY_MODE_MESSAGES = "messages";
export const LEFT_HISTORY_MODE_CONVERSATIONS = "conversations";

export const CONV_SORT_OPTIONS = [
  { value: "activity", label: "Actividad" },
  { value: "created_at", label: "Creación" },
];

// Orden del listado de mensajes.
export const MESSAGE_SORT_OPTIONS = [
  { value: "date", label: "Fecha" },
  { value: "title", label: "Título" },
  { value: "length", label: "Extensión" },
  { value: "photos", label: "Nº de fotos" },
];

// Ámbito de la búsqueda de mensajes.
export const MESSAGE_SEARCH_IN_OPTIONS = [
  { value: "title", label: "Solo título" },
  { value: "both", label: "Título y cuerpo" },
];

// Dirección del orden del listado de mensajes.
export const MESSAGE_SORT_DIRECTION_ASC = "asc";
export const MESSAGE_SORT_DIRECTION_DESC = "desc";
export const MESSAGE_SORT_DIRECTION_VALUES = [
  MESSAGE_SORT_DIRECTION_ASC,
  MESSAGE_SORT_DIRECTION_DESC,
];

// Dirección por defecto de cada criterio (título A→Z; el resto, mayor/reciente primero).
export const MESSAGE_SORT_DEFAULT_DIRECTION = {
  date: MESSAGE_SORT_DIRECTION_DESC,
  title: MESSAGE_SORT_DIRECTION_ASC,
  length: MESSAGE_SORT_DIRECTION_DESC,
  photos: MESSAGE_SORT_DIRECTION_DESC,
};

export const CONV_GROUP_LABELS = { hoy: "Hoy", ayer: "Ayer", semana: "Semana", anteriores: "Antes" };

// Valor del filtro por modelo para los mensajes sin modelo conocido (conversación sin model_id).
export const MESSAGE_MODEL_NONE = "__none__";

export const MESSAGE_TREE_ROOT_PAGE_SIZE = 50;
export const MESSAGE_HISTORY_SEARCH_DEBOUNCE_MS = 280;

export { MESSAGE_PAGE_SIZE_OPTIONS };

const MESSAGE_SORT_VALUES = MESSAGE_SORT_OPTIONS.map((o) => o.value);
const MESSAGE_SEARCH_IN_VALUES = MESSAGE_SEARCH_IN_OPTIONS.map((o) => o.value);

/** Dirección por defecto del criterio (título A→Z; el resto, mayor/reciente primero). */
export function defaultMessageSortDirection(sort) {
  return MESSAGE_SORT_DEFAULT_DIRECTION[sort] || MESSAGE_SORT_DIRECTION_DESC;
}

function normalizeMode(raw) {
  return raw === LEFT_HISTORY_MODE_CONVERSATIONS
    ? LEFT_HISTORY_MODE_CONVERSATIONS
    : LEFT_HISTORY_MODE_MESSAGES;
}

function readMode() {
  try {
    return normalizeMode(localStorage.getItem(LEFT_HISTORY_MODE_KEY));
  } catch (_) {
    return LEFT_HISTORY_MODE_MESSAGES;
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
    const stored = localStorage.getItem(LEFT_HISTORY_SORT_MESSAGES_KEY);
    return MESSAGE_SORT_VALUES.includes(stored) ? stored : "date";
  } catch (_) {
    return "date";
  }
}

function readMessageSearchIn() {
  try {
    const stored = localStorage.getItem(LEFT_HISTORY_SEARCH_IN_KEY);
    return MESSAGE_SEARCH_IN_VALUES.includes(stored) ? stored : "title";
  } catch (_) {
    return "title";
  }
}

function readStoredMessageSortDirectionRaw() {
  try {
    const stored = localStorage.getItem(LEFT_HISTORY_SORT_DIRECTION_KEY);
    return MESSAGE_SORT_DIRECTION_VALUES.includes(stored) ? stored : null;
  } catch (_) {
    return null;
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

/** Dirección explícita guardada, o null si el usuario nunca la cambió (aún aplica el default del criterio). */
export function readStoredMessageSortDirection() {
  return readStoredMessageSortDirectionRaw();
}

export function persistMessageSort(sort) {
  try {
    localStorage.setItem(
      LEFT_HISTORY_SORT_MESSAGES_KEY,
      MESSAGE_SORT_VALUES.includes(sort) ? sort : "date"
    );
  } catch (_) {}
}

export function persistMessageSortDirection(direction) {
  try {
    const normalized =
      direction === MESSAGE_SORT_DIRECTION_ASC
        ? MESSAGE_SORT_DIRECTION_ASC
        : MESSAGE_SORT_DIRECTION_DESC;
    localStorage.setItem(LEFT_HISTORY_SORT_DIRECTION_KEY, normalized);
  } catch (_) {}
}

export function readStoredMessageSearchIn() {
  return readMessageSearchIn();
}

export function persistMessageSearchIn(scope) {
  try {
    localStorage.setItem(
      LEFT_HISTORY_SEARCH_IN_KEY,
      MESSAGE_SEARCH_IN_VALUES.includes(scope) ? scope : "title"
    );
  } catch (_) {}
}

function readMessagePageSize() {
  try {
    return normalizePageSize(localStorage.getItem(LEFT_HISTORY_PAGE_SIZE_KEY));
  } catch (_) {
    return normalizePageSize(null);
  }
}

function readMessageShowDeleted() {
  try {
    return localStorage.getItem(LEFT_HISTORY_SHOW_DELETED_KEY) === "true";
  } catch (_) {
    return false;
  }
}

export function readStoredMessageShowDeleted() {
  return readMessageShowDeleted();
}

export function persistMessageShowDeleted(value) {
  try {
    localStorage.setItem(LEFT_HISTORY_SHOW_DELETED_KEY, value ? "true" : "false");
  } catch (_) {}
}

export function readStoredMessagePageSize() {
  return readMessagePageSize();
}

export function persistMessagePageSize(size) {
  try {
    localStorage.setItem(LEFT_HISTORY_PAGE_SIZE_KEY, String(normalizePageSize(size)));
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
  // Listado de mensajes (vista por defecto).
  messageSort: readMessageSort(),
  messageSortDirection: readStoredMessageSortDirectionRaw(),
  messageSearchIn: readMessageSearchIn(),
  messageShowDeleted: readMessageShowDeleted(),
  messageListItems: [],
  messageListTotal: 0,
  messageListQuery: "",
  messageModelFilter: "",
  messageModels: [],
  /** Último error al cargar el listado; `null` si la carga fue correcta. */
  messageListError: null,
  /** Hay mensajes sin modelo conocido: se ofrece la opción «Sin modelo» en el filtro. */
  hasMissingModels: false,
  // Paginación del listado de mensajes (página actual + tamaño por página).
  messagePage: 1,
  messagePageSize: readMessagePageSize(),
  // Conversaciones (árbol de respuestas).
  conversations: [],
  deletedConversations: [],
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
  return normalizeMode(state.mode) === LEFT_HISTORY_MODE_MESSAGES;
}

export function isConversationsHistoryMode(state = historyStore.get()) {
  return normalizeMode(state.mode) === LEFT_HISTORY_MODE_CONVERSATIONS;
}

/** Compat: el modo conversaciones es el árbol de respuestas. */
export function isTreeHistoryMode(state = historyStore.get()) {
  return isConversationsHistoryMode(state);
}

export function currentLeftHistorySort(state = historyStore.get()) {
  return isMessagesHistoryMode(state) ? state.messageSort : state.conversationSort;
}
