import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyStore } from "../store/history.js";

vi.mock("../api/conversations.js", () => ({
  listMessagesList: vi.fn(async () => ({ items: [], total: 0, models: [] })),
  listConversations: vi.fn(),
  listDeletedConversations: vi.fn(async () => []),
  getConversation: vi.fn(),
}));

vi.mock("../api/messageTree.js", () => ({
  listMessageTreeRoots: vi.fn(),
  listMessageTreeChildren: vi.fn(),
  deleteHistoryNodes: vi.fn(),
}));

vi.mock("../store/ui.js", () => ({
  showError: vi.fn(),
  showNotice: vi.fn(),
}));

import { listMessagesList } from "../api/conversations.js";
import {
  loadMessageList,
  onLeftHistorySortChange,
  onMessageSortDirectionToggle,
} from "./historyActions.js";

describe("orden del listado de mensajes", () => {
  beforeEach(() => {
    localStorage.clear();
    listMessagesList.mockClear();
    historyStore.set({
      mode: "messages",
      messageSort: "date",
      messageSortDirection: "desc",
      messageListItems: [],
      messageListQuery: "",
      messageSearchIn: "title",
      messageModelFilter: "",
    });
  });

  it("loadMessageList envía sort y direction a la API", async () => {
    historyStore.set({ messageSort: "title", messageSortDirection: "asc" });
    await loadMessageList();
    const params = listMessagesList.mock.calls[0][0];
    expect(params.get("sort")).toBe("title");
    expect(params.get("direction")).toBe("asc");
  });

  it("el toggle invierte la dirección y recarga con el nuevo valor", () => {
    onMessageSortDirectionToggle();
    expect(historyStore.get().messageSortDirection).toBe("asc");
    expect(listMessagesList.mock.calls.at(-1)[0].get("direction")).toBe("asc");

    onMessageSortDirectionToggle();
    expect(historyStore.get().messageSortDirection).toBe("desc");
    expect(listMessagesList.mock.calls.at(-1)[0].get("direction")).toBe("desc");
  });

  it("cambiar el criterio aplica su dirección por defecto", () => {
    historyStore.set({ messageSortDirection: "asc" });
    onLeftHistorySortChange("length");
    expect(historyStore.get().messageSort).toBe("length");
    // "length" usa por defecto desc (mayor primero).
    expect(historyStore.get().messageSortDirection).toBe("desc");
    const params = listMessagesList.mock.calls.at(-1)[0];
    expect(params.get("sort")).toBe("length");
    expect(params.get("direction")).toBe("desc");
  });

  it("título usa A→Z por defecto; fecha usa descendente por defecto", async () => {
    onLeftHistorySortChange("title");
    expect(historyStore.get().messageSortDirection).toBe("asc");
    expect(listMessagesList.mock.calls.at(-1)[0].get("direction")).toBe("asc");
    onLeftHistorySortChange("date");
    expect(historyStore.get().messageSortDirection).toBe("desc");
    expect(listMessagesList.mock.calls.at(-1)[0].get("direction")).toBe("desc");
  });
});
