import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { settingsStore } from "../store/settings.js";
import { sessionStore } from "../store/session.js";

const patchConversation = vi.fn(async () => ({}));

vi.mock("../api/conversations.js", () => ({
  patchConversation: (...args) => patchConversation(...args),
  getConversation: vi.fn(),
}));

vi.mock("../api/models.js", () => ({
  listProviders: vi.fn(async () => []),
  listModels: vi.fn(async () => []),
  listProviderParams: vi.fn(async () => ({ params: {} })),
  getModelContract: vi.fn(async () => ({ capabilities: {}, params: {}, recipes: [], quirks: [] })),
}));

describe("sincronización de proveedor/modelo con la conversación", () => {
  beforeEach(() => {
    patchConversation.mockClear();
    sessionStore.set({ conversationId: "c1" });
    settingsStore.set({ currentProvider: "ollama", currentModel: "llama" });
  });

  afterEach(() => {
    sessionStore.set({ conversationId: null });
  });

  it("changeModel persiste el modelo elegido en la conversación activa", async () => {
    const { changeModel } = await import("./settingsActions.js");
    changeModel("mistral");
    expect(settingsStore.get().currentModel).toBe("mistral");
    await vi.waitFor(() =>
      expect(patchConversation).toHaveBeenCalledWith(
        "c1",
        expect.objectContaining({ model_id: "mistral" })
      )
    );
  });

  it("changeProvider persiste el proveedor en la conversación activa", async () => {
    const { changeProvider, flushPendingConversationModelSync } = await import("./settingsActions.js");
    await changeProvider("mancer");
    expect(settingsStore.get().currentProvider).toBe("mancer");
    await flushPendingConversationModelSync();
    expect(patchConversation).toHaveBeenCalledWith(
      "c1",
      expect.objectContaining({ provider: "mancer" })
    );
  });

  it("sin conversación activa el cambio de modelo no llama a la API", async () => {
    sessionStore.set({ conversationId: null });
    const { changeModel } = await import("./settingsActions.js");
    changeModel("mistral");
    await Promise.resolve();
    expect(patchConversation).not.toHaveBeenCalled();
    expect(settingsStore.get().currentModel).toBe("mistral");
  });

  it("flushPendingConversationModelSync espera al guardado pendiente", async () => {
    let resolvePatch;
    patchConversation.mockImplementationOnce(
      () => new Promise((res) => { resolvePatch = res; })
    );
    const { changeModel, flushPendingConversationModelSync } = await import("./settingsActions.js");
    changeModel("mistral");
    let flushed = false;
    const p = flushPendingConversationModelSync().then(() => { flushed = true; });
    await Promise.resolve();
    expect(flushed).toBe(false);
    resolvePatch({});
    await p;
    expect(flushed).toBe(true);
  });
});
