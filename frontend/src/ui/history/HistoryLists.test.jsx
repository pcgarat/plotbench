import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyStore, LEFT_HISTORY_MODE_CONVERSATIONS } from "../../store/history.js";
import { sessionStore } from "../../store/session.js";

const openMessageTreeNode = vi.fn();
const deleteSelectedHistoryNodes = vi.fn();
const openIsolatedMessage = vi.fn();
const setLeftHistoryMode = vi.fn();

vi.mock("../../app/sessionActions.js", () => ({
  openMessageTreeNode: (...args) => openMessageTreeNode(...args),
  openIsolatedMessage: (...args) => openIsolatedMessage(...args),
  newConversation: vi.fn(),
  newPromptGeneratorConversation: vi.fn(),
}));

vi.mock("../../app/historyActions.js", async () => {
  const actual = await vi.importActual("../../app/historyActions.js");
  return {
    ...actual,
    deleteSelectedHistoryNodes: (...args) => deleteSelectedHistoryNodes(...args),
    setLeftHistoryMode: (...args) => setLeftHistoryMode(...args),
  };
});

import { ConversationsList } from "./HistoryLists.jsx";

const now = new Date().toISOString();

function seedTree() {
  historyStore.set({
    treeRoots: [
      {
        id: "m1",
        conversation_id: "c1",
        conversation_title: "Chat",
        content_preview: "primera",
        created_at: now,
        has_children: false,
        is_fork_edge: false,
      },
      {
        id: "m2",
        conversation_id: "c1",
        conversation_title: "Chat",
        content_preview: "segunda",
        created_at: now,
        has_children: false,
        is_fork_edge: false,
      },
    ],
    treeRootsTotal: 2,
    treeChildrenByParent: {},
    treeExpandedIds: {},
    treeMultiSelectedIds: [],
    treeSelectionAnchorId: null,
    treeSelectedMessageId: null,
    deletedConversations: [],
  });
}

function seedMessages() {
  historyStore.set({
    mode: "messages",
    messageListItems: [
      {
        id: "a1",
        conversation_id: "c1",
        conversation_title: "Chat",
        title: "El faro azul",
        length: 42,
        photo_count: 2,
        created_at: now,
        model_id: "llama3.2",
        provider: "ollama",
      },
    ],
    messageListTotal: 1,
    messageListQuery: "",
    messageSearchIn: "title",
    messageSort: "date",
    messageSortDirection: "desc",
    messageModelFilter: "",
    messageModels: [{ provider: "ollama", model_id: "llama3.2", count: 1 }],
  });
}

describe("ConversationsList selección y menú", () => {
  beforeEach(() => {
    openMessageTreeNode.mockClear();
    deleteSelectedHistoryNodes.mockClear();
    openIsolatedMessage.mockClear();
    setLeftHistoryMode.mockClear();
    seedTree();
    sessionStore.set({ focusMessageId: null, consultaAssistantId: null, messageViewOnlyMessageId: null });
  });

  it("ctrl+click selecciona varios y no abre el hilo", () => {
    historyStore.set({ mode: LEFT_HISTORY_MODE_CONVERSATIONS });
    render(<ConversationsList />);
    const first = document.querySelector('[data-id="m1"]');
    const second = document.querySelector('[data-id="m2"]');
    fireEvent.click(first);
    fireEvent.click(second, { ctrlKey: true });
    expect(openMessageTreeNode).toHaveBeenCalledTimes(1);
    expect(openMessageTreeNode).toHaveBeenCalledWith("c1", "m1");
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["m1", "m2"]);
    expect(first.classList.contains("is-selected")).toBe(true);
    expect(second.classList.contains("is-selected")).toBe(true);
  });

  it("click derecho abre el menú Eliminar", () => {
    historyStore.set({ mode: LEFT_HISTORY_MODE_CONVERSATIONS });
    render(<ConversationsList />);
    const first = document.querySelector('[data-id="m1"]');
    fireEvent.contextMenu(first, { clientX: 40, clientY: 60 });
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    expect(deleteSelectedHistoryNodes).toHaveBeenCalled();
  });
});

describe("ConversationsList vista de mensajes", () => {
  beforeEach(() => {
    openMessageTreeNode.mockClear();
    openIsolatedMessage.mockClear();
    setLeftHistoryMode.mockClear();
    seedMessages();
    sessionStore.set({ focusMessageId: null, consultaAssistantId: null, messageViewOnlyMessageId: null });
  });

  it("muestra el conmutador con Mensajes activo y los controles", () => {
    render(<ConversationsList />);
    expect(screen.getByRole("tab", { name: "Mensajes" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "Conversaciones" }).getAttribute("aria-selected")).toBe("false");
    expect(document.getElementById("message-history-search")).toBeTruthy();
    expect(document.getElementById("message-search-in")).toBeTruthy();
    expect(document.getElementById("left-history-sort-select")).toBeTruthy();
    expect(document.getElementById("message-model-filter")).toBeTruthy();
  });

  it("lista título, fecha y métricas del mensaje", () => {
    render(<ConversationsList />);
    const row = document.querySelector('[data-id="a1"]');
    expect(row.classList.contains("message-list-item")).toBe(true);
    expect(row.querySelector(".conv-title").textContent).toBe("El faro azul");
    expect(row.querySelector(".message-list-stats").textContent).toContain("42 car.");
    expect(row.querySelector(".message-list-stats").textContent).toContain("2 fotos");
    expect(row.querySelector(".message-history-created").textContent).toBeTruthy();
  });

  it("al hacer click abre el mensaje aislado (conversación, mensaje)", () => {
    render(<ConversationsList />);
    fireEvent.click(document.querySelector('[data-id="a1"]'));
    expect(openIsolatedMessage).toHaveBeenCalledWith("c1", "a1");
  });

  it("el mensaje abierto queda marcado como activo", () => {
    sessionStore.set({ messageViewOnlyMessageId: "a1" });
    render(<ConversationsList />);
    expect(document.querySelector('[data-id="a1"]').classList.contains("active")).toBe(true);
  });

  it("el filtro de modelos solo ofrece los que han generado mensajes", () => {
    render(<ConversationsList />);
    const select = document.getElementById("message-model-filter");
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.value);
    expect(options).toEqual(["", "llama3.2"]);
  });

  it("cambiar el orden de mensajes llama a onLeftHistorySortChange", () => {
    render(<ConversationsList />);
    fireEvent.change(document.getElementById("left-history-sort-select"), { target: { value: "photos" } });
    expect(historyStore.get().messageSort).toBe("photos");
  });

  it("el botón de dirección invierte asc/desc y persiste", () => {
    render(<ConversationsList />);
    const btn = document.getElementById("message-sort-direction");
    expect(btn.textContent).toBe("↓");
    expect(historyStore.get().messageSortDirection).toBe("desc");
    fireEvent.click(btn);
    expect(historyStore.get().messageSortDirection).toBe("asc");
    expect(document.getElementById("message-sort-direction").textContent).toBe("↑");
    fireEvent.click(document.getElementById("message-sort-direction"));
    expect(historyStore.get().messageSortDirection).toBe("desc");
  });
});
