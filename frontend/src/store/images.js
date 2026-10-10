import { createStore } from "./createStore.js";

export const IMAGES_PREFS_KEY = "chatbot_images_prefs";

function readPrefs() {
  try {
    return JSON.parse(localStorage.getItem(IMAGES_PREFS_KEY) || "{}") || {};
  } catch (_) {
    return {};
  }
}

export function persistImagesPrefs(prefs) {
  try {
    localStorage.setItem(IMAGES_PREFS_KEY, JSON.stringify(prefs || {}));
  } catch (_) {}
}

export const imagesStore = createStore({
  prefs: readPrefs(),
  galleryItems: [],
  galleryTotal: 0,
  galleryOffset: 0,
  galleryFilters: {
    promptModel: "",
    promptProvider: "",
    forgeModel: "",
    steps: "",
    size: "",
    mode: "",
    seed: "",
    promptQ: "",
    batchIds: [],
  },
  galleryFilterOptions: {
    promptModel: [],
    promptProvider: [],
    forgeModel: [],
    steps: [],
    size: [],
    mode: [],
    seed: [],
    batches: [],
  },
  galleryScopeAll: true,
  galleryUserChoseAll: false,
  galleryLightboxIndex: -1,
  /**
   * Fuente del visor compartido: "gallery" (colección filtrada) o "chat"
   * (fotos de la conversación abierta). null = visor cerrado.
   */
  imageViewerSource: null,
  chatViewerItems: [],
  chatViewerIndex: -1,
  galleryMessageId: null,
  queueItems: [],
  queueFilterStatus: "",
  queueExpandedId: null,
  queuePaused: false,
  queueSelectedIds: [],
  batchProgress: [],
  forgeDefaults: {},
  lastForgeParams: null,
  plannerContract: null,
});
