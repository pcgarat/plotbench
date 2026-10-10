import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyPreferencesSnapshot,
  collectPreferencesSnapshot,
  hydratePreferencesFromServer,
  startPreferencesSync,
  stopPreferencesSync,
  clearLocalPreferencesCache,
} from "./userPreferencesSync.js";
import { layoutStore, updateLayout } from "./layout.js";
import { imagesStore, persistImagesPrefs, IMAGES_PREFS_KEY } from "./images.js";
import {
  historyStore,
  persistConversationSort,
  persistMessageSort,
  persistMessageSortDirection,
  persistMessageSearchIn,
  persistMessagePageSize,
  persistMessageShowDeleted,
  persistLeftHistoryMode,
  LEFT_HISTORY_MODE_CONVERSATIONS,
  LEFT_HISTORY_MODE_KEY,
  LEFT_HISTORY_SORT_CONVERSATIONS_KEY,
  LEFT_HISTORY_SORT_MESSAGES_KEY,
  LEFT_HISTORY_SORT_DIRECTION_KEY,
  LEFT_HISTORY_SEARCH_IN_KEY,
  LEFT_HISTORY_PAGE_SIZE_KEY,
  LEFT_HISTORY_SHOW_DELETED_KEY,
} from "./history.js";
import { saveLastConversationId, LAST_CONVERSATION_STORAGE_KEY } from "./session.js";
import { settingsStore, persistSettingsPrefs } from "./settings.js";
import * as auth from "./auth.js";

vi.mock("./auth.js", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    loadUserPreferences: vi.fn(),
    saveUserPreferences: vi.fn(async (preferences) => ({ preferences })),
  };
});

describe("userPreferencesSync", () => {
  beforeEach(() => {
    localStorage.clear();
    stopPreferencesSync();
    auth.loadUserPreferences.mockReset();
    auth.saveUserPreferences.mockReset();
    auth.saveUserPreferences.mockImplementation(async (preferences) => ({ preferences }));
    layoutStore.set({
      darkMode: false,
      renderMarkdown: true,
      autoScrollDuringGeneration: true,
    });
    imagesStore.set({ prefs: {} });
    historyStore.set({
      conversationSort: "activity",
      messageSort: "date",
      messageSortDirection: "desc",
      mode: "messages",
    });
    settingsStore.set({
      currentProvider: "ollama",
      currentModel: "",
      historyTurns: 20,
      saveToChromadb: "user",
      paramsValues: {},
      paramsSource: "default",
    });
    saveLastConversationId(null);
  });

  it("collect → apply roundtrip conserva layout, images y lastConversation", () => {
    updateLayout({ darkMode: true, renderMarkdown: false });
    persistImagesPrefs({ enabled: true, prompt: "faro" });
    imagesStore.set({ prefs: { enabled: true, prompt: "faro" } });
    persistConversationSort("created_at");
    historyStore.set({ conversationSort: "created_at" });
    saveLastConversationId("conv-42");

    const snap = collectPreferencesSnapshot();
    expect(snap.layout.darkMode).toBe(true);
    expect(snap.layout.renderMarkdown).toBe(false);
    expect(snap.imagesPrefs.prompt).toBe("faro");
    expect(snap.history.conversationSort).toBe("created_at");
    expect(snap.lastConversationId).toBe("conv-42");

    updateLayout({ darkMode: false, renderMarkdown: true });
    persistImagesPrefs({});
    imagesStore.set({ prefs: {} });
    saveLastConversationId(null);

    applyPreferencesSnapshot(snap);
    expect(layoutStore.get().darkMode).toBe(true);
    expect(layoutStore.get().renderMarkdown).toBe(false);
    expect(imagesStore.get().prefs.prompt).toBe("faro");
    expect(JSON.parse(localStorage.getItem(IMAGES_PREFS_KEY)).prompt).toBe("faro");
    expect(historyStore.get().conversationSort).toBe("created_at");
    expect(localStorage.getItem(LAST_CONVERSATION_STORAGE_KEY)).toBe("conv-42");
  });

  it("collect → apply roundtrip conserva modo, orden y ámbito de mensajes", () => {
    persistMessageSort("photos");
    persistMessageSortDirection("asc");
    persistMessageSearchIn("both");
    persistMessagePageSize(100);
    persistMessageShowDeleted(true);
    persistLeftHistoryMode(LEFT_HISTORY_MODE_CONVERSATIONS);
    historyStore.set({
      mode: LEFT_HISTORY_MODE_CONVERSATIONS,
      messageSort: "photos",
      messageSortDirection: "asc",
      messageSearchIn: "both",
      messagePageSize: 100,
      messageShowDeleted: true,
    });

    const snap = collectPreferencesSnapshot();
    expect(snap.history.mode).toBe(LEFT_HISTORY_MODE_CONVERSATIONS);
    expect(snap.history.messageSort).toBe("photos");
    expect(snap.history.messageSortDirection).toBe("asc");
    expect(snap.history.messageSearchIn).toBe("both");
    expect(snap.history.messagePageSize).toBe(100);
    expect(snap.history.messageShowDeleted).toBe(true);

    // Estado divergente antes de aplicar: el snapshot debe imponerse.
    persistMessageSort("date");
    persistMessageSortDirection("desc");
    persistMessageSearchIn("title");
    persistMessagePageSize(25);
    persistMessageShowDeleted(false);
    persistLeftHistoryMode("messages");
    historyStore.set({
      mode: "messages",
      messageSort: "date",
      messageSortDirection: "desc",
      messageSearchIn: "title",
      messagePageSize: 25,
      messageShowDeleted: false,
    });

    applyPreferencesSnapshot(snap);
    expect(historyStore.get().mode).toBe(LEFT_HISTORY_MODE_CONVERSATIONS);
    expect(historyStore.get().messageSort).toBe("photos");
    expect(historyStore.get().messageSortDirection).toBe("asc");
    expect(historyStore.get().messageSearchIn).toBe("both");
    expect(historyStore.get().messagePageSize).toBe(100);
    expect(historyStore.get().messageShowDeleted).toBe(true);
    expect(localStorage.getItem(LEFT_HISTORY_MODE_KEY)).toBe(LEFT_HISTORY_MODE_CONVERSATIONS);
    expect(localStorage.getItem(LEFT_HISTORY_SORT_MESSAGES_KEY)).toBe("photos");
    expect(localStorage.getItem(LEFT_HISTORY_SORT_DIRECTION_KEY)).toBe("asc");
    expect(localStorage.getItem(LEFT_HISTORY_SEARCH_IN_KEY)).toBe("both");
    expect(localStorage.getItem(LEFT_HISTORY_PAGE_SIZE_KEY)).toBe("100");
    expect(localStorage.getItem(LEFT_HISTORY_SHOW_DELETED_KEY)).toBe("true");
  });

  it("apply normaliza valores de historial desconocidos del servidor", () => {
    applyPreferencesSnapshot({
      version: 1,
      history: {
        mode: "raro",
        messageSort: "nope",
        messageSortDirection: "nope",
        conversationSort: "raro",
        messageSearchIn: "nope",
      },
    });
    expect(historyStore.get().mode).toBe("messages");
    expect(historyStore.get().messageSort).toBe("date");
    expect(historyStore.get().messageSortDirection).toBe("desc");
    expect(historyStore.get().conversationSort).toBe("activity");
    expect(historyStore.get().messageSearchIn).toBe("title");
    expect(localStorage.getItem(LEFT_HISTORY_SORT_CONVERSATIONS_KEY)).toBe("activity");
  });

  it("hydrate sin prefs en servidor siembra el snapshot local", async () => {
    updateLayout({ darkMode: true });
    auth.loadUserPreferences.mockResolvedValue({ preferences: {} });
    const result = await hydratePreferencesFromServer();
    expect(result.seeded).toBe(true);
    expect(auth.saveUserPreferences).toHaveBeenCalled();
    const sent = auth.saveUserPreferences.mock.calls[0][0];
    expect(sent.layout.darkMode).toBe(true);
  });

  it("hydrate con prefs del servidor las aplica", async () => {
    auth.loadUserPreferences.mockResolvedValue({
      preferences: {
        version: 1,
        layout: { darkMode: true },
        imagesPrefs: { steps: 28 },
        history: { conversationSort: "created_at" },
        lastConversationId: "from-server",
      },
    });
    const result = await hydratePreferencesFromServer();
    expect(result.seeded).toBe(false);
    expect(layoutStore.get().darkMode).toBe(true);
    expect(imagesStore.get().prefs.steps).toBe(28);
    expect(historyStore.get().conversationSort).toBe("created_at");
    expect(localStorage.getItem(LAST_CONVERSATION_STORAGE_KEY)).toBe("from-server");
  });

  it("startPreferencesSync programa push al cambiar layout", async () => {
    vi.useFakeTimers();
    startPreferencesSync();
    updateLayout({ darkMode: true });
    expect(auth.saveUserPreferences).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(700);
    expect(auth.saveUserPreferences).toHaveBeenCalled();
    stopPreferencesSync();
    vi.useRealTimers();
  });

  it("collect incluye los ajustes del panel derecho", () => {
    settingsStore.set({
      currentProvider: "mancer",
      currentModel: "m1",
      historyTurns: 9,
      saveToChromadb: "both",
      paramsValues: { temperature: 0.3 },
      paramsSource: "user",
    });
    const snap = collectPreferencesSnapshot();
    expect(snap.settings.currentProvider).toBe("mancer");
    expect(snap.settings.currentModel).toBe("m1");
    expect(snap.settings.historyTurns).toBe(9);
    expect(snap.settings.saveToChromadb).toBe("both");
    expect(snap.settings.paramsValues).toEqual({ temperature: 0.3 });
    expect(snap.settings.paramsSource).toBe("user");
  });

  it("apply restaura los ajustes del panel derecho desde el snapshot", () => {
    settingsStore.set({ currentProvider: "ollama", currentModel: "", historyTurns: 20 });
    applyPreferencesSnapshot({
      version: 1,
      settings: {
        currentProvider: "mancer",
        currentModel: "m1",
        historyTurns: 9,
        saveToChromadb: "both",
        paramsValues: { temperature: 0.3 },
        paramsSource: "user",
      },
    });
    const s = settingsStore.get();
    expect(s.currentProvider).toBe("mancer");
    expect(s.currentModel).toBe("m1");
    expect(s.historyTurns).toBe(9);
    expect(s.saveToChromadb).toBe("both");
    expect(s.paramsValues).toEqual({ temperature: 0.3 });
    const stored = JSON.parse(localStorage.getItem("chatbot_settings_prefs"));
    expect(stored.currentProvider).toBe("mancer");
  });

  it("no pierde paramsValues guardados si el source cae a default", () => {
    // Caché local con los params que el usuario fijó antes.
    localStorage.setItem(
      "chatbot_settings_prefs",
      JSON.stringify({ paramsValues: { temperature: 0.9 }, paramsSource: "user" })
    );
    // Abrir una conversación antigua resetea el source a default con otros params.
    settingsStore.set({ paramsValues: { temperature: 0.8 }, paramsSource: "default" });
    const snap = collectPreferencesSnapshot();
    expect(snap.settings.paramsValues).toEqual({ temperature: 0.9 });
    expect(snap.settings.paramsSource).toBe("user");
    // El proveedor sí refleja siempre el estado vivo.
    settingsStore.set({ currentProvider: "mancer" });
    expect(collectPreferencesSnapshot().settings.currentProvider).toBe("mancer");
  });

  it("clearLocalPreferencesCache borra la caché para no filtrar otro usuario", () => {
    updateLayout({ darkMode: true });
    imagesStore.set({ prefs: { enabled: true } });
    persistImagesPrefs({ enabled: true });
    settingsStore.set({ currentProvider: "mancer" });
    persistSettingsPrefs({ currentProvider: "mancer" });
    saveLastConversationId("conv-9");
    clearLocalPreferencesCache();
    expect(localStorage.getItem("darkMode")).toBeNull();
    expect(localStorage.getItem(IMAGES_PREFS_KEY)).toBeNull();
    expect(localStorage.getItem("chatbot_settings_prefs")).toBeNull();
    expect(localStorage.getItem(LAST_CONVERSATION_STORAGE_KEY)).toBeNull();
  });

  it("cambiar un ajuste persiste la caché local y programa push", async () => {
    vi.useFakeTimers();
    startPreferencesSync();
    settingsStore.set({ currentProvider: "mancer", currentModel: "m1" });
    const stored = JSON.parse(localStorage.getItem("chatbot_settings_prefs"));
    expect(stored.currentProvider).toBe("mancer");
    expect(stored.currentModel).toBe("m1");
    expect(auth.saveUserPreferences).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(700);
    const sent = auth.saveUserPreferences.mock.calls.at(-1)[0];
    expect(sent.settings.currentProvider).toBe("mancer");
    stopPreferencesSync();
    vi.useRealTimers();
  });
});
