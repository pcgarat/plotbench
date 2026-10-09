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
});
