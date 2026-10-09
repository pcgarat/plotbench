import { describe, it, expect, beforeEach, vi } from "vitest";
import { sessionStore } from "../store/session.js";
import { messagesForPane } from "../lib/messageViewOnly.js";

const getConversation = vi.fn();
const patchConversation = vi.fn();

vi.mock("../api/conversations.js", () => ({
  getConversation: (...args) => getConversation(...args),
  patchConversation: (...args) => patchConversation(...args),
  createConversation: vi.fn(),
  forkConversation: vi.fn(),
  deleteMessage: vi.fn(),
  streamUrl: vi.fn(() => "/api/conversations/c1/messages/stream"),
  deleteLastMessage: vi.fn(),
  promptGeneratorTurn: vi.fn(),
}));

vi.mock("./settingsActions.js", () => ({
  loadModelContract: vi.fn(async () => {}),
  loadModels: vi.fn(async () => {}),
  loadParamsForProvider: vi.fn(async () => {}),
  applyConversationParams: vi.fn(),
}));

vi.mock("./historyActions.js", () => ({
  applyConsultaChrome: vi.fn(),
  refreshLeftHistory: vi.fn(),
  syncMessageHistoryActiveItem: vi.fn(),
  refreshMessageTreePreservingExpansion: vi.fn(),
}));

vi.mock("./imagesPanel.js", () => ({
  persistImagesPanel: vi.fn(),
  applyImagesSnapshot: vi.fn(),
  imagesSnapshotForConversation: vi.fn(() => ({})),
}));

function convWithThread() {
  return {
    id: "c1",
    title: "faro",
    kind: "chat",
    auto_title: false,
    messages: [
      { id: "u1", role: "user", content: "pinta", parent_id: null },
      { id: "m1", role: "assistant", content: "El faro azul.", parent_id: "u1" },
      { id: "u2", role: "user", content: "sigue", parent_id: "m1" },
      { id: "m2", role: "assistant", content: "El mar.", parent_id: "u2" },
    ],
  };
}

describe("vista de mensaje aislado", () => {
  beforeEach(() => {
    getConversation.mockReset().mockResolvedValue(convWithThread());
    patchConversation.mockReset().mockResolvedValue({});
    sessionStore.set({
      conversationId: null,
      messages: [],
      allMessages: [],
      focusMessageId: null,
      consultaAssistantId: null,
      messageViewOnly: false,
      messageViewOnlyMessageId: null,
      messageViewOnlyConversationId: null,
    });
  });

  it("muestra SOLO el mensaje seleccionado, ni el prompt ni el resto del hilo", async () => {
    const { openIsolatedMessage } = await import("./sessionActions.js");
    await openIsolatedMessage("c1", "m2");
    const s = sessionStore.get();
    expect(s.messageViewOnly).toBe(true);
    expect(s.messageViewOnlyMessageId).toBe("m2");
    const visible = messagesForPane(s, s.messages);
    expect(visible.map((m) => m.id)).toEqual(["m2"]);
    expect(visible.some((m) => m.role === "user")).toBe(false);
  });

  it("abrir un nodo del árbol vuelve a la ventana completa (no aislada)", async () => {
    const { openIsolatedMessage, openMessageTreeNode } = await import("./sessionActions.js");
    await openIsolatedMessage("c1", "m2");
    expect(sessionStore.get().messageViewOnly).toBe(true);

    await openMessageTreeNode("c1", "m1");
    const s = sessionStore.get();
    expect(s.messageViewOnly).toBe(false);
    expect(messagesForPane(s, s.messages).map((m) => m.id)).toEqual(s.messages.map((m) => m.id));
  });

  it("enviar un mensaje desde la vista aislada la abandona y muestra la ventana", async () => {
    const { openIsolatedMessage } = await import("./sessionActions.js");
    await openIsolatedMessage("c1", "m2");
    expect(sessionStore.get().messageViewOnly).toBe(true);

    const encoder = new TextEncoder();
    const chunks = [
      encoder.encode(JSON.stringify({ content: "nueva respuesta" }) + "\n"),
      encoder.encode(JSON.stringify({ done: true, id: "m3" }) + "\n"),
    ];
    let i = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        body: {
          getReader: () => ({
            read: async () => (i < chunks.length ? { done: false, value: chunks[i++] } : { done: true }),
          }),
        },
      }))
    );
    sessionStore.set({ composerDraft: "sigue contando" });
    const { sendMessage } = await import("./sendMessage.js");
    await sendMessage();

    const s = sessionStore.get();
    expect(s.messageViewOnly).toBe(false);
    const visible = messagesForPane(s, s.messages);
    expect(visible.length).toBeGreaterThan(1);
    vi.unstubAllGlobals();
  });

  it("saltar desde el árbol/galería cancela la vista aislada antes de revelar", async () => {
    const { openIsolatedMessage, openConversationAtIllustration } = await import("./sessionActions.js");
    await openIsolatedMessage("c1", "m2");
    expect(sessionStore.get().messageViewOnly).toBe(true);

    await openConversationAtIllustration("c1", "m1", { filename: "faro.png" });
    const s = sessionStore.get();
    expect(s.messageViewOnly).toBe(false);
    expect(s.messageViewOnlyMessageId).toBeNull();
  });

  it("abrir la misma conversación sin foco explícito sale del modo aislado", async () => {
    const { openIsolatedMessage, setCurrentConversation } = await import("./sessionActions.js");
    await openIsolatedMessage("c1", "m2");
    expect(sessionStore.get().messageViewOnly).toBe(true);

    await setCurrentConversation(convWithThread(), { preserveView: true });
    expect(sessionStore.get().messageViewOnly).toBe(false);
  });
});
