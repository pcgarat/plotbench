import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { sessionStore } from "../store/session.js";
import { settingsStore } from "../store/settings.js";

vi.mock("../api/conversations.js", () => ({
  streamUrl: vi.fn(() => "/api/conversations/c1/messages/stream"),
  deleteLastMessage: vi.fn(),
  promptGeneratorTurn: vi.fn(),
}));

vi.mock("./settingsActions.js", () => ({
  loadModelContract: vi.fn(async () => {}),
  loadModels: vi.fn(async () => {}),
  loadParamsForProvider: vi.fn(async () => {}),
  applyConversationParams: vi.fn(),
  flushPendingConversationModelSync: vi.fn(async () => {}),
}));

vi.mock("./historyActions.js", () => ({
  applyConsultaChrome: vi.fn(),
  refreshLeftHistory: vi.fn(),
  refreshMessageTreePreservingExpansion: vi.fn(),
  syncMessageHistoryActiveItem: vi.fn(),
}));

vi.mock("./imagesPanel.js", () => ({
  persistImagesPanel: vi.fn(),
  applyImagesSnapshot: vi.fn(),
  imagesSnapshotForConversation: vi.fn(() => ({})),
}));

function stubStream() {
  const encoder = new TextEncoder();
  const chunks = [
    encoder.encode(JSON.stringify({ content: "hola" }) + "\n"),
    encoder.encode(JSON.stringify({ done: true, id: "m2" }) + "\n"),
  ];
  let i = 0;
  const fetchMock = vi.fn(async () => ({
    ok: true,
    body: {
      getReader: () => ({
        read: async () => (i < chunks.length ? { done: false, value: chunks[i++] } : { done: true }),
      }),
    },
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("sendMessage envía el proveedor/modelo seleccionados", () => {
  beforeEach(() => {
    settingsStore.set({
      currentProvider: "mancer",
      currentModel: "mistral-large",
      providers: ["mancer"],
      models: ["mistral-large"],
      paramsConfig: { provider: "mancer", params: {} },
      paramsBaseline: {},
      paramsValues: {},
      paramsSource: "default",
      saveToChromadb: "user",
    });
    sessionStore.set({
      conversationId: "c1",
      conversationKind: "chat",
      composerDraft: "hola",
      allMessages: [],
      messages: [],
      activeLeafId: null,
      instructionOverride: "",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStore.set({ conversationId: null, composerDraft: "" });
  });

  it("incluye provider y model en el body del stream", async () => {
    const fetchMock = stubStream();
    const { sendMessage } = await import("./sendMessage.js");
    await sendMessage();
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.provider).toBe("mancer");
    expect(body.model).toBe("mistral-large");
  });
});
