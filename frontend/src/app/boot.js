import { applyDocumentLayout, layoutStore } from "../store/layout.js";
import { historyStore } from "../store/history.js";
import { readLastConversationId } from "../store/session.js";
import { showError } from "../store/ui.js";
import {
  loadProviders,
  tryLoadModelsForProvider,
  loadParamsForProvider,
  loadModelContract,
} from "./settingsActions.js";
import { settingsStore } from "../store/settings.js";
import { refreshLeftHistory, applyConsultaChrome } from "./historyActions.js";
import { openConversation } from "./sessionActions.js";
import {
  loadLibraryRules,
  loadPlannerLibraryRules,
  hydrateChatRulesFromLibrary,
  hydratePlannerRulesFromLibrary,
} from "./rulesActions.js";
import { refreshWorkspaceProfiles, refreshPlannerRulePresets } from "./profilesActions.js";
import { loadPlannerContract, ensureImagesPromptSelects, hydratePlannerRulesFromImagesPrefs } from "./imagesPanel.js";
import {
  hydratePreferencesFromServer,
  startPreferencesSync,
} from "../store/userPreferencesSync.js";

export async function bootApp() {
  try {
    await hydratePreferencesFromServer();
  } catch (_) {}
  startPreferencesSync();
  hydratePlannerRulesFromImagesPrefs();
  applyDocumentLayout(layoutStore.get());
  applyConsultaChrome();
  await loadProviders();
  const providers = settingsStore.get().providers;
  const preferred = settingsStore.get().currentProvider;
  const order = [preferred, ...providers.filter((p) => p !== preferred)];
  let loaded = false;
  for (const p of order) {
    if (await tryLoadModelsForProvider(p)) {
      loaded = true;
      break;
    }
  }
  if (!loaded && providers.length > 0) {
    showError("No se pudo cargar modelos de ningún proveedor. Comprueba Ollama/Mancer.");
  }
  await loadParamsForProvider(settingsStore.get().currentProvider);
  await loadModelContract({ applyParamDefaults: settingsStore.get().paramsSource !== "user" });
  await refreshLeftHistory();
  const storedId = readLastConversationId();
  if (storedId) {
    try {
      await openConversation(storedId);
    } catch (_) {}
  }
  loadLibraryRules().then(() => hydrateChatRulesFromLibrary());
  loadPlannerLibraryRules().then(() => hydratePlannerRulesFromLibrary());
  refreshWorkspaceProfiles();
  refreshPlannerRulePresets();
  await ensureImagesPromptSelects();
  await loadPlannerContract();
  historyStore.subscribe(() => applyConsultaChrome());
}
