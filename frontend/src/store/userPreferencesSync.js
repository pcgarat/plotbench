/**
 * Sync de preferencias de UI/imágenes/historial con el servidor (por usuario).
 * localStorage sigue como caché local; tras login el servidor es la fuente de verdad.
 */

import {
  applyDocumentLayout,
  layoutStore,
  persistLayout,
  SIDEBAR_TAB_STORAGE_KEY,
} from "./layout.js";
import { imagesStore, persistImagesPrefs, IMAGES_PREFS_KEY } from "./images.js";
import {
  historyStore,
  persistConversationSort,
  persistLeftHistoryMode,
  persistMessageSort,
  persistMessageSortDirection,
  persistMessageSearchIn,
  readStoredConversationSort,
  readStoredMessageSort,
  readStoredMessageSortDirection,
  readStoredMessageSearchIn,
  LEFT_HISTORY_MODE_CONVERSATIONS,
  LEFT_HISTORY_MODE_KEY,
  LEFT_HISTORY_SORT_CONVERSATIONS_KEY,
  LEFT_HISTORY_SORT_MESSAGES_KEY,
  LEFT_HISTORY_SORT_DIRECTION_KEY,
  LEFT_HISTORY_SEARCH_IN_KEY,
} from "./history.js";
import { debugStore, getStoredDebugLogSize, setStoredDebugLogSize, DEBUG_LOG_SIZE_STORAGE_KEY } from "./debug.js";
import {
  readLastConversationId,
  saveLastConversationId,
  LAST_CONVERSATION_STORAGE_KEY,
} from "./session.js";
import {
  settingsStore,
  persistSettingsPrefs,
  readStoredSettingsPrefs,
  PERSISTED_SETTINGS_KEYS,
  SETTINGS_PREFS_STORAGE_KEY,
} from "./settings.js";
import { loadUserPreferences, saveUserPreferences } from "./auth.js";

/**
 * Claves de la caché local de preferencias. Se limpian al cerrar sesión para que
 * otro usuario en el mismo navegador no herede las opciones del anterior.
 */
const PREFERENCE_CACHE_KEYS = [
  "darkMode",
  "leftSidebarCollapsed",
  "composerCollapsed",
  "sidebarLeftWidthPx",
  "sidebarRightWidthPx",
  "centerChatVisible",
  "centerGalleryVisible",
  "centerQueueVisible",
  "centerChatGalleryShare",
  "uiBaseFontScale",
  "chatbot_conversation_font_size_rem",
  "sidebarLeftFontScale",
  "sidebarRightFontScale",
  "chatbot_conversation_image_size",
  "chatbot_reading_mode_width_px",
  "autoScrollDuringGeneration",
  "renderMarkdown",
  SIDEBAR_TAB_STORAGE_KEY,
  "chatbot_sidebar_accordion",
  SETTINGS_PREFS_STORAGE_KEY,
  IMAGES_PREFS_KEY,
  LEFT_HISTORY_MODE_KEY,
  LEFT_HISTORY_SORT_CONVERSATIONS_KEY,
  LEFT_HISTORY_SORT_MESSAGES_KEY,
  LEFT_HISTORY_SORT_DIRECTION_KEY,
  DEBUG_LOG_SIZE_STORAGE_KEY,
  LAST_CONVERSATION_STORAGE_KEY,
];

export function clearLocalPreferencesCache() {
  try {
    PREFERENCE_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
  } catch (_) {}
}

/** Claves de settings que reflejan siempre el estado vivo (no dependen de params). */
const LIVE_SETTINGS_KEYS = ["currentProvider", "currentModel", "historyTurns", "saveToChromadb"];

/**
 * Preferencias de ajustes a persistir. La caché local es la base para no perder
 * los params guardados cuando el `paramsSource` cae temporalmente a "default"
 * (p. ej. al abrir una conversación antigua sin params).
 */
export function collectSettingsPrefs() {
  const stored = readStoredSettingsPrefs();
  const out = {};
  PERSISTED_SETTINGS_KEYS.forEach((key) => {
    if (key in stored) out[key] = stored[key];
  });
  const settings = settingsStore.get();
  LIVE_SETTINGS_KEYS.forEach((key) => {
    if (settings[key] !== undefined) out[key] = settings[key];
  });
  if (settings.paramsSource === "user") {
    out.paramsValues = settings.paramsValues;
    out.paramsSource = "user";
  }
  return out;
}

const LAYOUT_KEYS = [
  "darkMode",
  "leftSidebarCollapsed",
  "composerCollapsed",
  "leftWidthPx",
  "rightWidthPx",
  "centerChatVisible",
  "centerGalleryVisible",
  "centerQueueVisible",
  "centerChatGalleryShare",
  "uiBaseFontScale",
  "conversationFontRem",
  "sidebarLeftFontScale",
  "sidebarRightFontScale",
  "imageSizeFactor",
  "readingWidthPx",
  "autoScrollDuringGeneration",
  "renderMarkdown",
  "sidebarTab",
  "accordion",
];

const PUSH_DEBOUNCE_MS = 600;

let applying = false;
let watchStarted = false;
let pushTimer = null;
let unsubscribers = [];

export function collectPreferencesSnapshot() {
  const layout = layoutStore.get();
  const layoutOut = {};
  LAYOUT_KEYS.forEach((key) => {
    if (layout[key] !== undefined) layoutOut[key] = layout[key];
  });
  return {
    version: 1,
    layout: layoutOut,
    settings: collectSettingsPrefs(),
    imagesPrefs: { ...(imagesStore.get().prefs || {}) },
    history: {
      mode: historyStore.get().mode,
      conversationSort: historyStore.get().conversationSort,
      messageSort: historyStore.get().messageSort,
      messageSortDirection: historyStore.get().messageSortDirection,
      messageSearchIn: historyStore.get().messageSearchIn,
    },
    debugLogSize: getStoredDebugLogSize(),
    lastConversationId: readLastConversationId() || null,
  };
}

export function applyPreferencesSnapshot(raw) {
  if (!raw || typeof raw !== "object") return;
  applying = true;
  try {
    const layoutPatch = raw.layout && typeof raw.layout === "object" ? raw.layout : null;
    if (layoutPatch) {
      const patch = {};
      LAYOUT_KEYS.forEach((key) => {
        if (key in layoutPatch) patch[key] = layoutPatch[key];
      });
      if (Object.keys(patch).length) {
        layoutStore.set(patch);
        persistLayout(patch);
        applyDocumentLayout(layoutStore.get());
      }
    }

    if (raw.settings && typeof raw.settings === "object") {
      const settingsPatch = {};
      PERSISTED_SETTINGS_KEYS.forEach((key) => {
        if (key in raw.settings) settingsPatch[key] = raw.settings[key];
      });
      if (Object.keys(settingsPatch).length) {
        settingsStore.set(settingsPatch);
        persistSettingsPrefs(settingsPatch);
      }
    }

    if (raw.imagesPrefs && typeof raw.imagesPrefs === "object") {
      persistImagesPrefs(raw.imagesPrefs);
      imagesStore.set((s) => ({ ...s, prefs: { ...raw.imagesPrefs } }));
    }

    if (raw.history && typeof raw.history === "object") {
      const histPatch = {};
      if (raw.history.mode != null) {
        persistLeftHistoryMode(raw.history.mode);
        histPatch.mode =
          raw.history.mode === LEFT_HISTORY_MODE_CONVERSATIONS
            ? LEFT_HISTORY_MODE_CONVERSATIONS
            : "messages";
      }
      if (raw.history.conversationSort != null) {
        persistConversationSort(raw.history.conversationSort);
        histPatch.conversationSort = readStoredConversationSort();
      }
      if (raw.history.messageSort != null) {
        persistMessageSort(raw.history.messageSort);
        histPatch.messageSort = readStoredMessageSort();
      }
      if (raw.history.messageSortDirection != null) {
        persistMessageSortDirection(raw.history.messageSortDirection);
        histPatch.messageSortDirection = readStoredMessageSortDirection();
      }
      if (raw.history.messageSearchIn != null) {
        persistMessageSearchIn(raw.history.messageSearchIn);
        histPatch.messageSearchIn = readStoredMessageSearchIn();
      }
      if (Object.keys(histPatch).length) historyStore.set(histPatch);
    }

    if (raw.debugLogSize != null) {
      const n = Number(raw.debugLogSize);
      if (Number.isFinite(n)) {
        setStoredDebugLogSize(n);
        debugStore.set({ logSize: n });
      }
    }

    if ("lastConversationId" in raw) {
      saveLastConversationId(raw.lastConversationId || null);
    }
  } finally {
    applying = false;
  }
}

export async function hydratePreferencesFromServer() {
  const data = await loadUserPreferences();
  const prefs = (data && data.preferences) || {};
  const hasServer =
    prefs &&
    typeof prefs === "object" &&
    (prefs.layout ||
      prefs.settings ||
      prefs.imagesPrefs ||
      prefs.history ||
      prefs.debugLogSize != null);

  if (!hasServer) {
    const snapshot = collectPreferencesSnapshot();
    await saveUserPreferences(snapshot);
    return { seeded: true, preferences: snapshot };
  }

  applyPreferencesSnapshot(prefs);
  return { seeded: false, preferences: prefs };
}

export function schedulePreferencesPush() {
  if (applying || !watchStarted) return;
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(() => {
    pushTimer = null;
    void flushPreferencesPush();
  }, PUSH_DEBOUNCE_MS);
}

export async function flushPreferencesPush() {
  if (applying) return;
  try {
    await saveUserPreferences(collectPreferencesSnapshot());
  } catch (_) {}
}

function onStoreChange() {
  schedulePreferencesPush();
}

let lastSettingsPersisted = null;

function onSettingsChange() {
  const snapshot = collectSettingsPrefs();
  const serialized = JSON.stringify(snapshot);
  if (serialized === lastSettingsPersisted) return;
  lastSettingsPersisted = serialized;
  persistSettingsPrefs(snapshot);
  schedulePreferencesPush();
}

export function startPreferencesSync() {
  if (watchStarted) return;
  watchStarted = true;
  unsubscribers = [
    layoutStore.subscribe(onStoreChange),
    settingsStore.subscribe(onSettingsChange),
    imagesStore.subscribe(onStoreChange),
    historyStore.subscribe(onStoreChange),
  ];
}

export function stopPreferencesSync() {
  watchStarted = false;
  if (pushTimer) {
    clearTimeout(pushTimer);
    pushTimer = null;
  }
  unsubscribers.forEach((u) => u && u());
  unsubscribers = [];
}
