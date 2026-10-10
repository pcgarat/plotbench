import * as modelsApi from "../api/models.js";
import * as conversationsApi from "../api/conversations.js";
import { settingsStore } from "../store/settings.js";
import { sessionStore } from "../store/session.js";
import { showError } from "../store/ui.js";
import { buildModelParams } from "../lib/params.js";
import {
  applyParamsConfigToDom,
  capabilityBadgesFromContract,
  fillCapabilityBadgeHost,
  fillRecipeChipHost as paintRecipeChipHost,
  fillThinkOptions,
  getCanonicalParamControl,
  RECIPE_PARAM_LABELS,
  recipeIdsFromContract,
  recipeMatchesParams,
  recipesFromContract,
  setControlValueIfChanged,
  showThinking,
  thinkSelectValue,
  thinkingFromContract,
} from "../lib/contractUi.js";

export function normalizeModelsResponse(data) {
  function toNames(arr) {
    if (!Array.isArray(arr)) return [];
    return arr
      .map((m) => (m && typeof m === "object" && m.name != null ? String(m.name).trim() : null))
      .filter((name) => name !== null && name !== "");
  }
  if (Array.isArray(data)) return toNames(data);
  if (data && typeof data === "object") {
    const arr = data.data || data.models;
    if (Array.isArray(arr)) return toNames(arr);
    if (typeof arr === "object" && arr !== null && !Array.isArray(arr)) return toNames(Object.values(arr));
  }
  return [];
}

export async function loadProviders() {
  try {
    const data = await modelsApi.listProviders();
    const providers = (data || []).map((p) => (typeof p === "string" ? p : p.name)).filter(Boolean);
    const current = settingsStore.get().currentProvider;
    const next = providers.includes(current) ? current : providers[0] || "ollama";
    settingsStore.set({ providers, currentProvider: next });
    return providers;
  } catch (_) {
    settingsStore.set({ providers: ["ollama"], currentProvider: "ollama" });
    return ["ollama"];
  }
}

export async function tryLoadModelsForProvider(providerName) {
  try {
    const data = await modelsApi.listModels(providerName);
    const models = normalizeModelsResponse(data);
    const prev = settingsStore.get().currentModel;
    const currentModel = models.includes(prev) ? prev : models[0] || "";
    settingsStore.set({ models, currentProvider: providerName, currentModel });
    return true;
  } catch (_) {
    return false;
  }
}

export async function loadModels(preserveSelection = false) {
  const { currentProvider, currentModel } = settingsStore.get();
  const provider = currentProvider || "ollama";
  try {
    const data = await modelsApi.listModels(provider);
    const models = normalizeModelsResponse(data);
    let nextModel = currentModel;
    if (!preserveSelection || !models.includes(currentModel)) {
      nextModel = models[0] || "";
    }
    settingsStore.set({ models, currentModel: nextModel });
    return models;
  } catch (e) {
    showError(`No se pudieron cargar los modelos de ${provider}: ` + e.message);
    settingsStore.set({ models: [], currentModel: preserveSelection ? currentModel : "" });
    return [];
  }
}

export async function loadParamsForProvider(providerName) {
  try {
    const data = await modelsApi.listProviderParams(providerName);
    const params = (data && data.params) || data || {};
    settingsStore.set({
      paramsConfig: { provider: providerName, params },
    });
  } catch (_) {
    settingsStore.set({ paramsConfig: { provider: providerName, params: {} } });
  }
}

function mergeContractIntoParams(paramsConfig, contract) {
  const merged = {
    ...(paramsConfig.params || {}),
    ...((contract && contract.params) || {}),
  };
  if (showThinking(contract)) {
    const thinking = thinkingFromContract(contract);
    const spec = (contract.params && contract.params.think) || {
      api_key: "think",
      type: thinking.kind === "levels" ? "enum" : "boolean",
      default: thinking.default,
    };
    merged.think = spec;
  } else {
    delete merged.think;
  }
  return merged;
}

function baselineFromContract(contract, prev = {}) {
  const baseline = { ...prev };
  if (contract && contract.params) {
    Object.keys(contract.params).forEach((id) => {
      if (contract.params[id] && contract.params[id].default !== undefined) {
        baseline[id] = contract.params[id].default;
      }
    });
  }
  const thinking = thinkingFromContract(contract);
  if (showThinking(contract) && thinking && thinking.default !== undefined) {
    if (baseline.think === undefined) baseline.think = thinking.default;
  }
  return baseline;
}

export async function loadModelContract(opts = {}) {
  const { currentProvider, currentModel, paramsConfig } = settingsStore.get();
  if (!currentProvider || !currentModel) {
    settingsStore.set({ contract: null });
    applyThinkAndRecipesFromContract({ applyParamDefaults: false });
    return;
  }
  try {
    const contract = await modelsApi.getModelContract(currentProvider, currentModel);
    const merged = mergeContractIntoParams(paramsConfig, contract);
    const baseline = baselineFromContract(contract, settingsStore.get().paramsBaseline);
    const patch = {
      contract,
      paramsConfig: { ...paramsConfig, params: merged },
      paramsBaseline: baseline,
    };
    if (opts.applyParamDefaults && contract && contract.params) {
      const values = { ...settingsStore.get().paramsValues };
      Object.keys(merged).forEach((id) => {
        if (merged[id] && merged[id].default !== undefined) {
          values[id] = merged[id].default;
        }
      });
      patch.paramsValues = values;
      patch.paramsSource = "default";
    }
    settingsStore.set(patch);
  } catch (_) {
    settingsStore.set({ contract: null });
  }
  applyThinkAndRecipesFromContract({ applyParamDefaults: Boolean(opts.applyParamDefaults) });
}

export function applyConversationParams(modelParams) {
  if (!modelParams || typeof modelParams !== "object") return;
  settingsStore.set((s) => ({
    ...s,
    paramsValues: { ...s.paramsValues, ...modelParams },
    paramsSource: "user",
  }));
  applyParamsConfigToDom(settingsStore.get().paramsConfig, settingsStore.get().paramsValues);
  syncSettingsPresetsMirrors();
}

export function applyModelRecipe(recipe) {
  if (!recipe || typeof recipe !== "object") return;
  if (settingsStore.get().paramsSource === "user") {
    const label = recipe.label || recipe.id || "esta receta";
    const ok = window.confirm(
      `Esto sustituye los ajustes de esta conversación por la receta «${label}». ¿Continuar?`
    );
    if (!ok) return;
  }
  applyConversationParams(recipe.params || {});
  const conversationId = sessionStore.get().conversationId;
  if (conversationId) {
    conversationsApi.patchConversation(conversationId, { model_params: buildModelParams() }).catch(() => {});
  }
}

export async function refreshModels() {
  await loadModels(true);
  await loadModelContract({ applyParamDefaults: false });
}

export async function changeProvider(providerName) {
  settingsStore.set({ currentProvider: providerName, modelSelectionLocal: true });
  await loadParamsForProvider(providerName);
  const ok = await tryLoadModelsForProvider(providerName);
  if (!ok) await loadModels(false);
  await loadModelContract({ applyParamDefaults: true });
  scheduleConversationModelSync();
}

export function changeModel(modelId) {
  settingsStore.set({
    currentModel: modelId,
    modelSelectOpen: false,
    modelSelectQuery: "",
    modelSelectionLocal: true,
  });
  loadModelContract({ applyParamDefaults: true });
  scheduleConversationModelSync();
}

/**
 * Persiste en la conversación activa el proveedor/modelo elegidos en la UI.
 * Sin conversación abierta solo se guarda la preferencia local. El debounce evita
 * parches redundantes al recorrer el desplegable.
 */
const CONVERSATION_SYNC_DEBOUNCE_MS = 250;
let conversationSyncTimer = null;
let conversationSyncPromise = null;

function conversationModelPayload() {
  const { currentProvider, currentModel } = settingsStore.get();
  return { provider: currentProvider, model_id: currentModel };
}

export function scheduleConversationModelSync() {
  if (conversationSyncTimer) clearTimeout(conversationSyncTimer);
  conversationSyncPromise = new Promise((resolve) => {
    conversationSyncTimer = setTimeout(() => {
      conversationSyncTimer = null;
      resolve(pushConversationModelSync());
    }, CONVERSATION_SYNC_DEBOUNCE_MS);
  });
}

async function pushConversationModelSync() {
  const conversationId = sessionStore.get().conversationId;
  if (!conversationId) return;
  try {
    await conversationsApi.patchConversation(conversationId, conversationModelPayload());
  } catch (_) {
    // Silencioso: el envío del mensaje reenvía la selección viva y la persiste el backend.
  }
}

/** Fuerza el guardado pendiente antes de una operación que pueda leer la conversación. */
export async function flushPendingConversationModelSync() {
  if (conversationSyncTimer) {
    clearTimeout(conversationSyncTimer);
    conversationSyncTimer = null;
    conversationSyncPromise = Promise.resolve(pushConversationModelSync());
  }
  if (conversationSyncPromise) await conversationSyncPromise;
}

export function currentRecipes() {
  return recipesFromContract(settingsStore.get().contract);
}

export function fillRecipeChipHost(host, recipes, applyFn) {
  paintRecipeChipHost(host, recipes, applyFn);
}

export function syncRecipeChipSelection() {
  const recipes = currentRecipes();
  const values = settingsStore.get().paramsValues;
  const active = recipes.find((recipe) => recipeMatchesParams(recipe, values));
  const activeId = active && active.id;
  document.querySelectorAll("#composer-recipes .composer-recipe-chip, #settings-recipes .composer-recipe-chip").forEach((btn) => {
    const on = Boolean(activeId && btn.dataset.recipeId === activeId);
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const owned = active && active.params ? Object.keys(active.params) : [];
  document.querySelectorAll("#settings-recipe-params .settings-recipe-param").forEach((row) => {
    row.classList.toggle("is-owned", owned.includes(row.dataset.paramId));
  });
}

function recipeParamLabel(paramId) {
  const spec = settingsStore.get().paramsConfig.params && settingsStore.get().paramsConfig.params[paramId];
  return (spec && spec.label) || RECIPE_PARAM_LABELS[paramId] || paramId;
}

function writeMirrorToCanonical(mirror) {
  const paramId = mirror && mirror.getAttribute("data-recipe-param-id");
  const canonical = paramId ? getCanonicalParamControl(paramId) : null;
  if (!canonical || canonical.disabled) return;
  setControlValueIfChanged(canonical, mirror.value);
  canonical.dispatchEvent(new Event("input", { bubbles: true }));
  canonical.dispatchEvent(new Event("change", { bubbles: true }));
}

export function rebuildRecipeParamInspector() {
  const host = document.getElementById("settings-recipe-params");
  document.getElementById("settings-recipes");
  document.getElementById("settings-think");
  if (!host) return;
  const ids = recipeIdsFromContract(settingsStore.get().contract).filter((id) => id !== "think" && getCanonicalParamControl(id));
  host.innerHTML = "";
  if (!ids.length) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  ids.forEach((paramId) => {
    const canonical = getCanonicalParamControl(paramId);
    const row = document.createElement("div");
    row.className = "settings-recipe-param";
    row.dataset.paramId = paramId;
    const label = document.createElement("label");
    label.className = "settings-recipe-param-label";
    const controlId = "settings-recipe-param-" + paramId;
    label.setAttribute("for", controlId);
    label.textContent = recipeParamLabel(paramId);
    const mirror = canonical.cloneNode(true);
    mirror.removeAttribute("data-control-id");
    mirror.id = controlId;
    mirror.classList.add("param-control");
    mirror.setAttribute("data-recipe-param-id", paramId);
    mirror.addEventListener("input", () => writeMirrorToCanonical(mirror));
    mirror.addEventListener("change", () => writeMirrorToCanonical(mirror));
    row.appendChild(label);
    row.appendChild(mirror);
    host.appendChild(row);
  });
}

export function syncSettingsPresetsMirrors() {
  const recipes = currentRecipes();
  const canThink = showThinking(settingsStore.get().contract);
  const settingsRow = document.getElementById("settings-presets-controls");
  const emptyEl = document.getElementById("settings-presets-empty");
  const composerRow = document.getElementById("composer-model-row");
  if (settingsRow) settingsRow.hidden = !canThink && recipes.length === 0;
  if (emptyEl) emptyEl.hidden = recipes.length > 0;
  if (composerRow) composerRow.hidden = !canThink && recipes.length === 0;
  fillRecipeChipHost(document.getElementById("settings-recipes"), recipes, applyModelRecipe);
  fillRecipeChipHost(document.getElementById("composer-recipes"), recipes, applyModelRecipe);
  const canonicalThink = document.getElementById("param-think");
  const settingsThink = document.getElementById("settings-think");
  if (canonicalThink && settingsThink) {
    if (settingsThink.innerHTML !== canonicalThink.innerHTML) {
      settingsThink.innerHTML = canonicalThink.innerHTML;
    }
    settingsThink.disabled = canonicalThink.disabled;
    settingsThink.classList.toggle("control-disabled", canonicalThink.classList.contains("control-disabled"));
    setControlValueIfChanged(settingsThink, canonicalThink.value);
  }
  document.querySelectorAll("[data-recipe-param-id]").forEach((mirror) => {
    const canonical = getCanonicalParamControl(mirror.getAttribute("data-recipe-param-id"));
    if (!canonical) return;
    mirror.disabled = canonical.disabled;
    mirror.classList.toggle("control-disabled", canonical.classList.contains("control-disabled"));
    ["min", "max", "step", "placeholder"].forEach((attr) => {
      if (canonical.hasAttribute(attr)) mirror.setAttribute(attr, canonical.getAttribute(attr));
    });
    setControlValueIfChanged(mirror, canonical.value);
  });
  syncRecipeChipSelection();
}

export function applyThinkAndRecipesFromContract(opts = {}) {
  const applyParamDefaults = Boolean(opts.applyParamDefaults);
  const contract = settingsStore.get().contract;
  const row = document.getElementById("composer-model-row");
  const wrap = document.getElementById("composer-think-wrap");
  const control = document.getElementById("param-think");
  const settingsWrap = document.getElementById("settings-think-wrap");
  const settingsThink = document.getElementById("settings-think");
  const settingsRow = document.getElementById("settings-presets-controls");
  const emptyEl = document.getElementById("settings-presets-empty");
  const thinking = thinkingFromContract(contract);
  const recipes = currentRecipes();
  const canThink = showThinking(contract);
  const showRecipes = recipes.length > 0;
  if (row) row.hidden = !canThink && !showRecipes;
  if (settingsRow) settingsRow.hidden = !canThink && !showRecipes;
  if (emptyEl) emptyEl.hidden = showRecipes;
  if (wrap) wrap.hidden = !canThink;
  if (settingsWrap) settingsWrap.hidden = !canThink;
  const paramsConfig = settingsStore.get().paramsConfig;
  const params = { ...(paramsConfig.params || {}) };
  if (control) {
    if (canThink) {
      fillThinkOptions(control, thinking);
      const spec = params.think || {
        api_key: "think",
        type: thinking.kind === "levels" ? "enum" : "boolean",
        default: thinking.default,
      };
      params.think = spec;
      control.disabled = false;
      control.classList.remove("control-disabled");
      const def = spec.default !== undefined ? spec.default : thinking.default;
      const values = { ...settingsStore.get().paramsValues };
      const allowed = Array.from(control.options).map((o) => o.value);
      if (applyParamDefaults && def !== undefined && def !== null) {
        control.value = thinkSelectValue(def);
        values.think = def;
      } else if (!allowed.includes(thinkSelectValue(values.think)) && def !== undefined && def !== null) {
        control.value = thinkSelectValue(def);
        values.think = def;
      } else if (values.think !== undefined && values.think !== null) {
        control.value = thinkSelectValue(values.think);
      }
      const baseline = { ...settingsStore.get().paramsBaseline };
      if (def !== undefined && def !== null) baseline.think = def;
      settingsStore.set({
        paramsConfig: { ...paramsConfig, params },
        paramsBaseline: baseline,
        paramsValues: values,
      });
    } else {
      control.disabled = true;
      control.classList.add("control-disabled");
      control.innerHTML = "";
      delete params.think;
      settingsStore.set({ paramsConfig: { ...paramsConfig, params } });
    }
  }
  if (settingsThink) {
    if (canThink && control) {
      settingsThink.innerHTML = control.innerHTML;
      settingsThink.disabled = false;
      settingsThink.classList.remove("control-disabled");
      setControlValueIfChanged(settingsThink, control.value);
    } else {
      settingsThink.disabled = true;
      settingsThink.classList.add("control-disabled");
      settingsThink.innerHTML = "";
    }
  }
  fillRecipeChipHost(document.getElementById("composer-recipes"), recipes, applyModelRecipe);
  fillRecipeChipHost(document.getElementById("settings-recipes"), recipes, applyModelRecipe);
  const numCtx = document.getElementById("param-num-ctx");
  const ctxSpec = contract && contract.params && contract.params.num_ctx;
  if (numCtx && ctxSpec && ctxSpec.max != null) {
    numCtx.setAttribute("max", String(ctxSpec.max));
  }
  applyParamsConfigToDom(settingsStore.get().paramsConfig, settingsStore.get().paramsValues);
  fillCapabilityBadgeHost(document.getElementById("status-model-capabilities"), capabilityBadgesFromContract(contract));
  fillCapabilityBadgeHost(document.getElementById("settings-model-capabilities"), capabilityBadgesFromContract(contract));
  rebuildRecipeParamInspector();
  syncSettingsPresetsMirrors();
}

export function renderCapabilityBadges() {
  const contract = settingsStore.get().contract;
  const badges = capabilityBadgesFromContract(contract);
  fillCapabilityBadgeHost(document.getElementById("status-model-capabilities"), badges);
  fillCapabilityBadgeHost(document.getElementById("settings-model-capabilities"), badges);
}
