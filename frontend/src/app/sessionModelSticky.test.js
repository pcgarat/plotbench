import { beforeEach, describe, expect, it, vi } from "vitest";
import { sessionStore } from "../store/session.js";
import { settingsStore } from "../store/settings.js";

const getConversation = vi.fn();
const patchConversation = vi.fn();

vi.mock("../api/conversations.js", () => ({
  getConversation: (...args) => getConversation(...args),
  patchConversation: (...args) => patchConversation(...args),
  createConversation: vi.fn(),
  forkConversation: vi.fn(),
  deleteMessage: vi.fn(),
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
  setLeftHistoryMode: vi.fn(),
  syncMessageHistoryActiveItem: vi.fn(),
}));

vi.mock("./imagesPanel.js", () => ({
  persistImagesPanel: vi.fn(),
  applyImagesSnapshot: vi.fn(),
  imagesSnapshotForConversation: vi.fn(() => ({})),
}));

function sampleConv(overrides = {}) {
  return {
    id: "c2",
    title: "otra",
    kind: "chat",
    auto_title: false,
    provider: "ollama",
    model_id: "llama3.2",
    messages: [],
    ...overrides,
  };
}

describe("selección de modelo global (sticky)", () => {
  beforeEach(() => {
    getConversation.mockReset().mockResolvedValue(sampleConv());
    patchConversation.mockReset().mockResolvedValue({});
    settingsStore.set({
      currentProvider: "mancer",
      currentModel: "mistral-large",
      modelSelectionLocal: true,
    });
    sessionStore.set({ conversationId: "c1" });
  });

  it("abrir otra conversación NO pisa el proveedor/modelo elegidos por el usuario", async () => {
    const { setCurrentConversation } = await import("./sessionActions.js");
    await setCurrentConversation(sampleConv());
    expect(settingsStore.get().currentProvider).toBe("mancer");
    expect(settingsStore.get().currentModel).toBe("mistral-large");
  });

  it("sin elección explícita del usuario, la conversación abre con su modelo guardado", async () => {
    settingsStore.set({ currentProvider: "mancer", currentModel: "mistral-large", modelSelectionLocal: false });
    const { setCurrentConversation } = await import("./sessionActions.js");
    await setCurrentConversation(sampleConv());
    expect(settingsStore.get().currentProvider).toBe("ollama");
    expect(settingsStore.get().currentModel).toBe("llama3.2");
  });
});
