import { describe, expect, it } from "vitest";
import { groupRootsByConversation, visibleHistoryNodeIds } from "./historyVisibleNodes.js";

describe("visibleHistoryNodeIds", () => {
  it("respeta grupos, orden interno y nodos expandidos", () => {
    const now = new Date().toISOString();
    const roots = [
      { id: "a2", conversation_id: "c1", conversation_title: "Uno", created_at: now },
      { id: "a1", conversation_id: "c1", conversation_title: "Uno", created_at: now },
    ];
    const ids = visibleHistoryNodeIds(
      roots,
      { a1: [{ id: "f1", created_at: now }] },
      { a1: true }
    );
    expect(ids).toEqual(["a1", "f1", "a2"]);
  });
});

describe("groupRootsByConversation", () => {
  it("agrupa y ordena por fecha", () => {
    const groups = groupRootsByConversation([
      { id: "b", conversation_id: "c", conversation_title: "T", created_at: "2026-01-02" },
      { id: "a", conversation_id: "c", conversation_title: "T", created_at: "2026-01-01" },
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].nodes.map((n) => n.id)).toEqual(["a", "b"]);
  });
});
