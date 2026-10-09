import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyStore } from "../store/history.js";
import { sessionStore } from "../store/session.js";

vi.mock("../api/messageTree.js", () => ({
  listMessageTreeRoots: vi.fn(),
  listMessageTreeChildren: vi.fn(),
  deleteHistoryNodes: vi.fn(async () => ({
    trashed_conversation_ids: ["c1"],
    deleted_message_ids: [],
  })),
}));

vi.mock("../api/conversations.js", () => ({
  listConversations: vi.fn(),
  listDeletedConversations: vi.fn(async () => []),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  restoreConversation: vi.fn(),
  permanentlyDeleteConversation: vi.fn(),
  purgeDeletedConversations: vi.fn(),
  clearConversationMessages: vi.fn(),
}));

vi.mock("../store/ui.js", () => ({
  showError: vi.fn(),
  showNotice: vi.fn(),
}));

import { deleteHistoryNodes } from "../api/messageTree.js";
import { showNotice } from "../store/ui.js";
import {
  applyHistoryNodeClick,
  applyHistoryNodeContextMenu,
  clearHistorySelection,
  deleteSelectedHistoryNodes,
} from "./historyActions.js";

describe("selección múltiple del historial", () => {
  beforeEach(() => {
    historyStore.set({
      treeRoots: [
        { id: "a", conversation_id: "c1", created_at: new Date().toISOString() },
        { id: "b", conversation_id: "c1", created_at: new Date().toISOString() },
        { id: "c", conversation_id: "c2", created_at: new Date().toISOString() },
      ],
      treeChildrenByParent: {},
      treeExpandedIds: {},
      treeMultiSelectedIds: [],
      treeSelectionAnchorId: null,
      deletedConversations: [],
    });
    sessionStore.set({ conversationId: null, messages: [], allMessages: [] });
    deleteHistoryNodes.mockClear();
    showNotice.mockClear();
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("ctrl+click acumula y no pide abrir", () => {
    const first = applyHistoryNodeClick("a", { ctrlKey: false, shiftKey: false });
    expect(first.shouldOpen).toBe(true);
    const second = applyHistoryNodeClick("c", { ctrlKey: true, shiftKey: false });
    expect(second.shouldOpen).toBe(false);
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["a", "c"]);
  });

  it("shift+click cubre el rango visible", () => {
    applyHistoryNodeClick("a", {});
    const ranged = applyHistoryNodeClick("c", { shiftKey: true });
    expect(ranged.shouldOpen).toBe(false);
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["a", "b", "c"]);
  });

  it("click derecho conserva la selección si el nodo ya está marcado", () => {
    applyHistoryNodeClick("a", { ctrlKey: true });
    applyHistoryNodeClick("c", { ctrlKey: true });
    applyHistoryNodeContextMenu("c");
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["a", "c"]);
    applyHistoryNodeContextMenu("b");
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["b"]);
  });

  it("eliminar envía los ids seleccionados", async () => {
    applyHistoryNodeClick("a", { ctrlKey: true });
    await deleteSelectedHistoryNodes();
    expect(deleteHistoryNodes).toHaveBeenCalledWith(["a"]);
    expect(historyStore.get().treeMultiSelectedIds).toEqual([]);
    expect(showNotice).toHaveBeenCalled();
  });

  it("si se cancela el confirm no llama a la API", async () => {
    window.confirm.mockReturnValueOnce(false);
    applyHistoryNodeClick("a", {});
    await deleteSelectedHistoryNodes();
    expect(deleteHistoryNodes).not.toHaveBeenCalled();
    expect(historyStore.get().treeMultiSelectedIds).toEqual(["a"]);
    clearHistorySelection();
    expect(historyStore.get().treeMultiSelectedIds).toEqual([]);
  });
});
