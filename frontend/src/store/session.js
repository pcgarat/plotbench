import { createStore } from "./createStore.js";

export const LAST_CONVERSATION_STORAGE_KEY = "chatbot_last_conversation_id";

export const sessionStore = createStore({
  conversationId: null,
  conversationKind: "chat",
  title: "",
  autoTitle: false,
  messages: [],
  allMessages: [],
  activeLeafId: null,
  /** Mensaje ancla del historial izquierdo / salto unificado. */
  focusMessageId: null,
  /** Primer índice visible del camino activo; anteriores se revelan al hacer scroll arriba. */
  viewStartIndex: 0,
  /** Vista de mensaje aislado: solo el mensaje seleccionado (composer sigue disponible). */
  messageViewOnly: false,
  messageViewOnlyMessageId: null,
  messageViewOnlyConversationId: null,
  consultaAssistantId: null,
  rules: [],
  plannerRules: [],
  composerDraft: "",
  instructionOverride: "",
  streamingText: "",
  streamingStatus: null,
  abortController: null,
  collapsedMessageKeys: [],
  illustratingIds: [],
  readingModeIndex: null,
  lastUsage: null,
  contextLength: null,
  imageFilterNotice: false,
  pendingReveal: null,
});

export function saveLastConversationId(id) {
  try {
    if (id) localStorage.setItem(LAST_CONVERSATION_STORAGE_KEY, id);
    else localStorage.removeItem(LAST_CONVERSATION_STORAGE_KEY);
  } catch (_) {}
}

export function readLastConversationId() {
  try {
    return localStorage.getItem(LAST_CONVERSATION_STORAGE_KEY);
  } catch (_) {
    return null;
  }
}

export function resetSession() {
  sessionStore.set({
    conversationId: null,
    conversationKind: "chat",
    title: "",
    autoTitle: false,
    messages: [],
    allMessages: [],
    activeLeafId: null,
    focusMessageId: null,
    viewStartIndex: 0,
    messageViewOnly: false,
    messageViewOnlyMessageId: null,
    messageViewOnlyConversationId: null,
    consultaAssistantId: null,
    rules: [],
    composerDraft: "",
    instructionOverride: "",
    streamingText: "",
    streamingStatus: null,
    abortController: null,
    pendingReveal: null,
  });
  saveLastConversationId(null);
}
