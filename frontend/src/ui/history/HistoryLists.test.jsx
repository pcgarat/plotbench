import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyStore } from "../../store/history.js";
import { sessionStore } from "../../store/session.js";

const openMessageTreeNode = vi.fn();
const deleteSelectedHistoryNodes = vi.fn();

vi.mock("../../app/sessionActions.js", () => ({
  openMessageTreeNode: (...args) => openMessageTreeNode(...args),
  newConversation: vi.fn(),
  newPromptGeneratorConversation: vi.fn(),
}));

vi.mock("../../app/historyActions.js", async () => {
  const actual = await vi.importActual("../../app/historyActions.js");
  return {
    ...actual,
    deleteSelectedHistoryNodes: (...args) => deleteSelectedHistoryNodes(...args),
  };
});

import { ConversationsList } from "./HistoryLists.jsx";

const now = new Date().toISOString();

describe("ConversationsList selección y menú", () => {
  beforeEach(() => {
    openMessageTreeNode.mockClear();
    deleteSelectedHistoryNodes.mockClear();
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
    sessionStore.set({ focusMessageId: null, consultaAssistantId: null });
  });

  it("ctrl+click selecciona varios y no abre el hilo", () => {
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
    render(<ConversationsList />);
    const first = document.querySelector('[data-id="m1"]');
    fireEvent.contextMenu(first, { clientX: 40, clientY: 60 });
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    expect(deleteSelectedHistoryNodes).toHaveBeenCalled();
  });
});
