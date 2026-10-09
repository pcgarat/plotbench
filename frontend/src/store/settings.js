import { createStore } from "./createStore.js";

export const SETTINGS_PREFS_STORAGE_KEY = "chatbot_settings_prefs";

/** Ajustes del panel derecho que se guardan como preferencia (local + servidor). */
export const PERSISTED_SETTINGS_KEYS = [
  "currentProvider",
  "currentModel",
  "historyTurns",
  "saveToChromadb",
  "paramsValues",
  "paramsSource",
];

export function readStoredSettingsPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(SETTINGS_PREFS_STORAGE_KEY) || "{}");
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  } catch (_) {
    return {};
  }
}

export function persistSettingsPrefs(patch) {
  if (!patch || typeof patch !== "object") return;
  try {
    const current = readStoredSettingsPrefs();
    let changed = false;
    PERSISTED_SETTINGS_KEYS.forEach((key) => {
      if (key in patch) {
        current[key] = patch[key];
        changed = true;
      }
    });
    if (changed) {
      localStorage.setItem(SETTINGS_PREFS_STORAGE_KEY, JSON.stringify(current));
    }
  } catch (_) {}
}

const stored = readStoredSettingsPrefs();

export const settingsStore = createStore({
  providers: [],
  models: [],
  currentProvider: stored.currentProvider || "ollama",
  currentModel: stored.currentModel || "",
  paramsConfig: { provider: "", params: {} },
  paramsSource: stored.paramsSource === "user" ? "user" : "default",
  paramsBaseline: {},
  paramsValues: stored.paramsValues && typeof stored.paramsValues === "object" ? stored.paramsValues : {},
  paramsExcludedFromSendByConv: {},
  contract: null,
  libraryRules: [],
  plannerLibraryRules: [],
  plannerRulePresets: [],
  modelSelectQuery: "",
  modelSelectOpen: false,
  saveToChromadb: stored.saveToChromadb || "user",
  historyTurns: Number.isFinite(stored.historyTurns) ? stored.historyTurns : 20,
});
