import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyStore } from "../store/history.js";

vi.mock("../api/conversations.js", () => ({
  listMessagesList: vi.fn(async () => ({ items: [], total: 120, models: [] })),
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
  goToMessagePage,
  goToFirstMessagePage,
  goToLastMessagePage,
  goToPrevMessagePage,
  goToNextMessagePage,
  setMessagePageSize,
} from "./historyActions.js";

function lastParams() {
  return listMessagesList.mock.calls.at(-1)[0];
}

describe("paginación del listado de mensajes", () => {
  beforeEach(() => {
    localStorage.clear();
    listMessagesList.mockClear();
    historyStore.set({
      mode: "messages",
      messageSort: "date",
      messageSortDirection: "desc",
      messageListItems: [],
      messageListTotal: 0,
      messageListQuery: "",
      messageSearchIn: "title",
      messageModelFilter: "",
      messageModels: [],
      hasMissingModels: false,
      messagePage: 1,
      messagePageSize: 50,
    });
  });

  it("loadMessageList pide la primera página con el tamaño configurado", async () => {
    await loadMessageList();
    expect(lastParams().get("limit")).toBe("50");
    expect(lastParams().get("offset")).toBe("0");
  });

  it("respeta el tamaño de página guardado", async () => {
    historyStore.set({ messagePageSize: 25 });
    await loadMessageList();
    expect(lastParams().get("limit")).toBe("25");
  });

  it("goToMessagePage calcula el offset y no reinicia la página", async () => {
    historyStore.set({ messageListTotal: 120 });
    goToMessagePage(3);
    await Promise.resolve();
    expect(lastParams().get("limit")).toBe("50");
    expect(lastParams().get("offset")).toBe("100");
    expect(historyStore.get()).toMatchObject({ messagePage: 3 });
  });

  it("primera y última página usan los límites del total", async () => {
    historyStore.set({ messageListTotal: 120, messagePage: 2 });
    goToLastMessagePage();
    await Promise.resolve();
    expect(historyStore.get().messagePage).toBe(3);
    goToFirstMessagePage();
    await Promise.resolve();
    expect(historyStore.get().messagePage).toBe(1);
    expect(lastParams().get("offset")).toBe("0");
  });

  it("anterior y siguiente se mueven de una en una y no salen del rango", async () => {
    historyStore.set({ messageListTotal: 120, messagePage: 2 });
    goToNextMessagePage();
    await Promise.resolve();
    expect(historyStore.get().messagePage).toBe(3);
    goToNextMessagePage();
    await Promise.resolve();
    expect(historyStore.get().messagePage).toBe(3); // clamp: ya es la última
    goToPrevMessagePage();
    await Promise.resolve();
    expect(historyStore.get().messagePage).toBe(2);
  });

  it("cambiar el tamaño de página vuelve a la primera página", async () => {
    historyStore.set({ messageListTotal: 120, messagePage: 3 });
    setMessagePageSize(25);
    await Promise.resolve();
    expect(historyStore.get().messagePageSize).toBe(25);
    expect(historyStore.get().messagePage).toBe(1);
    expect(lastParams().get("limit")).toBe("25");
    expect(lastParams().get("offset")).toBe("0");
  });

  it("envía model_id=__none__ al filtrar por mensajes sin modelo", async () => {
    historyStore.set({ messageModelFilter: "__none__" });
    await loadMessageList();
    expect(lastParams().get("model_id")).toBe("__none__");
  });

  it("un fallo de carga queda expuesto y no como estado vacío silencioso", async () => {
    historyStore.set({ messageListError: null });
    listMessagesList.mockRejectedValueOnce(new Error("422: limit <= 100"));
    await loadMessageList();
    expect(historyStore.get().messageListError).toContain("422");
  });

  it("limpiar el error cuando la carga vuelve a funcionar", async () => {
    historyStore.set({ messageListError: "Error previo" });
    await loadMessageList();
    expect(historyStore.get().messageListError).toBe(null);
  });
});
