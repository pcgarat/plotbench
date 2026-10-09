import { beforeEach, describe, expect, it, vi } from "vitest";

describe("settingsStore: persistencia de ajustes del panel derecho", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("las claves persistidas parten de localStorage al reabrir", async () => {
    localStorage.setItem(
      "chatbot_settings_prefs",
      JSON.stringify({
        currentProvider: "mancer",
        currentModel: "gpt-oss:120b",
        historyTurns: 12,
        saveToChromadb: "both",
        paramsValues: { temperature: 0.4 },
        paramsSource: "user",
      })
    );

    const { settingsStore } = await import("./settings.js");
    const s = settingsStore.get();
    expect(s.currentProvider).toBe("mancer");
    expect(s.currentModel).toBe("gpt-oss:120b");
    expect(s.historyTurns).toBe(12);
    expect(s.saveToChromadb).toBe("both");
    expect(s.paramsValues).toEqual({ temperature: 0.4 });
    expect(s.paramsSource).toBe("user");
  });

  it("persistSettingsPrefs guarda solo las claves conocidas", async () => {
    const { persistSettingsPrefs, readStoredSettingsPrefs } = await import("./settings.js");
    persistSettingsPrefs({ currentProvider: "ollama", ignored: true });
    const stored = readStoredSettingsPrefs();
    expect(stored.currentProvider).toBe("ollama");
    expect(stored.ignored).toBeUndefined();
  });

  it("usa valores por defecto si no hay nada guardado", async () => {
    const { settingsStore } = await import("./settings.js");
    const s = settingsStore.get();
    expect(s.currentProvider).toBe("ollama");
    expect(s.currentModel).toBe("");
    expect(s.historyTurns).toBe(20);
    expect(s.saveToChromadb).toBe("user");
    expect(s.paramsSource).toBe("default");
  });

  it("ignora JSON corrupto y vuelve a los defaults", async () => {
    localStorage.setItem("chatbot_settings_prefs", "{no-json");
    const { settingsStore } = await import("./settings.js");
    expect(settingsStore.get().currentProvider).toBe("ollama");
  });
});
