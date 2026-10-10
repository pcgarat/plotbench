import { describe, it, expect, beforeEach } from "vitest";
import {
  historyStore,
  persistConversationSort,
  persistMessageSort,
  persistMessageSortDirection,
  persistMessageSearchIn,
  persistLeftHistoryMode,
  readStoredConversationSort,
  readStoredMessageSort,
  readStoredMessageSortDirection,
  readStoredMessageSearchIn,
  isMessagesHistoryMode,
  isConversationsHistoryMode,
  isTreeHistoryMode,
  LEFT_HISTORY_MODE_KEY,
  LEFT_HISTORY_MODE_MESSAGES,
  LEFT_HISTORY_MODE_CONVERSATIONS,
  LEFT_HISTORY_PAGE_SIZE_KEY,
  LEFT_HISTORY_SHOW_DELETED_KEY,
  readStoredMessagePageSize,
  persistMessagePageSize,
  readStoredMessageShowDeleted,
  persistMessageShowDeleted,
  MESSAGE_MODEL_NONE,
} from "./history.js";
describe("history store", () => {
  beforeEach(() => {
    localStorage.clear();
    historyStore.set({
      mode: LEFT_HISTORY_MODE_MESSAGES,
      conversationSort: "activity",
      messageSort: "date",
      messageSortDirection: "desc",
      messageSearchIn: "title",
      conversations: [],
      deletedConversations: [],
      messageListItems: [],
      treeRoots: [],
      treeChildrenByParent: {},
      treeExpandedIds: {},
      messagePage: 1,
      messagePageSize: 50,
    });
  });

  it("persiste orden, ámbito y modo", () => {
    persistConversationSort("created_at");
    persistMessageSort("photos");
    persistMessageSortDirection("asc");
    persistMessageSearchIn("both");
    persistLeftHistoryMode(LEFT_HISTORY_MODE_CONVERSATIONS);
    expect(readStoredConversationSort()).toBe("created_at");
    expect(readStoredMessageSort()).toBe("photos");
    expect(readStoredMessageSortDirection()).toBe("asc");
    expect(readStoredMessageSearchIn()).toBe("both");
    expect(localStorage.getItem(LEFT_HISTORY_MODE_KEY)).toBe(LEFT_HISTORY_MODE_CONVERSATIONS);
  });

  it("persiste y normaliza el tamaño de página del listado de mensajes", () => {
    persistMessagePageSize(200);
    expect(readStoredMessagePageSize()).toBe(200);
    persistMessagePageSize(7);
    expect(readStoredMessagePageSize()).toBe(50);
    expect(localStorage.getItem(LEFT_HISTORY_PAGE_SIZE_KEY)).toBe("50");
  });

  it("persiste el check de mensajes eliminados", () => {
    expect(readStoredMessageShowDeleted()).toBe(false);
    persistMessageShowDeleted(true);
    expect(readStoredMessageShowDeleted()).toBe(true);
    expect(localStorage.getItem(LEFT_HISTORY_SHOW_DELETED_KEY)).toBe("true");
    persistMessageShowDeleted(false);
    expect(readStoredMessageShowDeleted()).toBe(false);
  });

  it("normaliza valores desconocidos a los defaults", () => {
    persistMessageSort("nope");
    persistMessageSortDirection("nope");
    persistMessageSearchIn("nope");
    persistLeftHistoryMode("nope");
    expect(readStoredMessageSort()).toBe("date");
    expect(readStoredMessageSortDirection()).toBe("desc");
    expect(readStoredMessageSearchIn()).toBe("title");
    expect(localStorage.getItem(LEFT_HISTORY_MODE_KEY)).toBe(LEFT_HISTORY_MODE_MESSAGES);
  });

  it("el modo mensajes es el default", () => {
    historyStore.set({ mode: LEFT_HISTORY_MODE_MESSAGES });
    expect(isMessagesHistoryMode()).toBe(true);
    expect(isConversationsHistoryMode()).toBe(false);
  });

  it("el modo conversaciones equivale al árbol", () => {
    historyStore.set({ mode: LEFT_HISTORY_MODE_CONVERSATIONS });
    expect(isConversationsHistoryMode()).toBe(true);
    expect(isTreeHistoryMode()).toBe(true);
    expect(isMessagesHistoryMode()).toBe(false);
  });

  it("expone el valor del filtro «Sin modelo» y su bandera", () => {
    expect(MESSAGE_MODEL_NONE).toBe("__none__");
    historyStore.set({ hasMissingModels: true });
    expect(historyStore.get().hasMissingModels).toBe(true);
    historyStore.set({ hasMissingModels: false });
    expect(historyStore.get().hasMissingModels).toBe(false);
  });
});
