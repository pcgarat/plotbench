import { useEffect } from "react";
import { useStore } from "../../hooks/useStore.js";
import { settingsStore } from "../../store/settings.js";
import { sessionStore } from "../../store/session.js";
import { debugStore, renderChatDebugLog, renderImagesDebugLog, syncDebugPanelDom } from "../../store/debug.js";
import { uiStore, currentStatus } from "../../store/ui.js";
import { historyStore } from "../../store/history.js";
import { getWorkspaceProfiles } from "../../app/profilesActions.js";
import { renderContextUsageBar } from "../status/StatusBarInfo.js";
import { applyThinkAndRecipesFromContract, syncSettingsPresetsMirrors } from "../../app/settingsActions.js";
import { applyParamsConfigToDom } from "../../lib/contractUi.js";
import { renderPlannerRecipes } from "../../app/imagesPanel.js";
import { imagesStore } from "../../store/images.js";
import { bindModelSelectCombobox, syncModelSelectFromStore } from "../../app/modelSelectUi.js";

function fillSelect(id, values, current) {
  const el = document.getElementById(id);
  if (!el) return;
  const names = values.map((v) => (typeof v === "string" ? v : v.name || v.id || "")).filter(Boolean);
  const html = names.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("");
  if (el.innerHTML !== html && (el.tagName === "SELECT")) {
    const keep = el.value;
    el.innerHTML = html || el.innerHTML;
    if (current && names.includes(current)) el.value = current;
    else if (names.includes(keep)) el.value = keep;
  } else if (current && el.value !== current) {
    el.value = current;
  }
}

export function StoreDomSync() {
  const providers = useStore(settingsStore, (s) => s.providers);
  const models = useStore(settingsStore, (s) => s.models);
  const provider = useStore(settingsStore, (s) => s.currentProvider);
  const model = useStore(settingsStore, (s) => s.currentModel);
  const library = useStore(settingsStore, (s) => s.libraryRules);
  const plannerLib = useStore(settingsStore, (s) => s.plannerLibraryRules);
  const plannerPresets = useStore(settingsStore, (s) => s.plannerRulePresets);
  const title = useStore(sessionStore, (s) => s.title);
  const draft = useStore(sessionStore, (s) => s.composerDraft);
  const instruction = useStore(sessionStore, (s) => s.instructionOverride);
  const kind = useStore(sessionStore, (s) => s.conversationKind);
  const abort = useStore(sessionStore, (s) => s.abortController);
  const chatLog = useStore(debugStore, (s) => s.chatLog);
  const imagesLog = useStore(debugStore, (s) => s.imagesLog);
  const chatOpen = useStore(debugStore, (s) => s.chatOpen);
  const imagesOpen = useStore(debugStore, (s) => s.imagesOpen);
  const mode = useStore(historyStore, (s) => s.mode);
  const contract = useStore(settingsStore, (s) => s.contract);
  const paramsConfig = useStore(settingsStore, (s) => s.paramsConfig);
  const paramsValues = useStore(settingsStore, (s) => s.paramsValues);
  const historyTurns = useStore(settingsStore, (s) => s.historyTurns);
  const saveToChromadb = useStore(settingsStore, (s) => s.saveToChromadb);
  const plannerContract = useStore(imagesStore, (s) => s.plannerContract);
  const useChatConfig = useStore(imagesStore, (s) => s.prefs.use_chat_config);
  useStore(uiStore);

  useEffect(() => {
    fillSelect("provider-select", providers, provider);
    const headerP = document.getElementById("header-provider-name");
    if (headerP) headerP.textContent = provider || "";
    fillSelect("images-prompt-provider", providers, imagesStore.get().prefs.prompt_provider || provider);
  }, [providers, provider]);

  useEffect(() => {
    bindModelSelectCombobox();
  }, []);

  useEffect(() => {
    fillSelect("model-select", models, model);
    const headerM = document.getElementById("header-model-name");
    if (headerM) headerM.textContent = model || "";
    syncModelSelectFromStore();
  }, [models, model]);

  useEffect(() => {
    const sel = document.getElementById("rule-library-select");
    if (sel) {
      sel.innerHTML =
        '<option value="">Elegir regla</option>' +
        library.map((r) => `<option value="${r.id}">${(r.title || "").replace(/</g, "")}</option>`).join("");
    }
  }, [library]);

  useEffect(() => {
    const sel = document.getElementById("planner-rule-library-select");
    if (sel) {
      sel.innerHTML =
        '<option value="">Elegir regla</option>' +
        plannerLib.map((r) => `<option value="${r.id}">${(r.title || "").replace(/</g, "")}</option>`).join("");
    }
  }, [plannerLib]);

  useEffect(() => {
    const sel = document.getElementById("planner-rule-preset-select");
    if (!sel) return;
    const list = plannerPresets || [];
    const current = sel.value;
    sel.innerHTML =
      '<option value="">Elegir preset</option>' +
      list.map((p) => `<option value="${p.id}">${(p.name || "").replace(/</g, "")}</option>`).join("");
    if (current) sel.value = current;
  }, [plannerPresets]);

  useEffect(() => {
    const t = document.getElementById("conversation-title");
    if (t && t !== document.activeElement) t.value = title || "";
  }, [title]);

  useEffect(() => {
    const ta = document.getElementById("message-input");
    if (ta && ta !== document.activeElement) ta.value = draft || "";
    const ins = document.getElementById("instruction-override");
    if (ins && ins !== document.activeElement) ins.value = instruction || "";
    const gen = document.getElementById("btn-generate-prompt");
    if (gen) gen.hidden = kind !== "prompt_generator";
    const send = document.getElementById("btn-send");
    if (send) {
      send.setAttribute("data-composer-action", abort ? "stop" : "send");
      send.title = abort ? "Parar" : "Enviar";
      send.setAttribute("aria-label", abort ? "Parar generación" : "Enviar mensaje");
    }
  }, [draft, instruction, kind, abort]);

  useEffect(() => {
    const wrap = document.getElementById("message-history-search-wrap");
    if (wrap) wrap.hidden = true;
    const sortWrap = document.getElementById("left-history-sort");
    if (sortWrap) sortWrap.hidden = true;
  }, [mode]);

  useEffect(() => {
    const turns = document.getElementById("history-turns-input");
    if (turns && turns !== document.activeElement) turns.value = String(historyTurns);
    const chroma = document.getElementById("save-to-chromadb-select");
    if (chroma && chroma !== document.activeElement) chroma.value = saveToChromadb;
  }, [historyTurns, saveToChromadb]);

  useEffect(() => {
    syncDebugPanelDom();
    renderChatDebugLog();
  }, [chatLog, chatOpen, imagesOpen]);

  useEffect(() => {
    syncDebugPanelDom();
    renderImagesDebugLog();
  }, [imagesLog, imagesOpen, chatOpen]);

  useEffect(() => {
    const st = currentStatus();
    const text = document.getElementById("app-status-text");
    const detail = document.getElementById("app-status-detail");
    const bar = document.getElementById("app-status-bar");
    if (text) text.textContent = st.label;
    if (detail) {
      detail.hidden = !st.detail;
      detail.textContent = st.detail || "";
    }
    if (bar) bar.classList.toggle("is-busy", st.busy);
    renderContextUsageBar();
  });

  useEffect(() => {
    applyThinkAndRecipesFromContract({ applyParamDefaults: false });
  }, [contract]);

  useEffect(() => {
    applyParamsConfigToDom(paramsConfig, paramsValues);
    syncSettingsPresetsMirrors();
  }, [paramsConfig, paramsValues]);

  useEffect(() => {
    renderPlannerRecipes();
  }, [plannerContract, useChatConfig]);

  useEffect(() => {
    const sel = document.getElementById("workspace-profile-select");
    if (!sel) return;
    const list = getWorkspaceProfiles();
    const current = sel.value;
    sel.innerHTML =
      '<option value="">Elegir perfil</option>' +
      list.map((p) => `<option value="${p.id}">${(p.name || "").replace(/</g, "")}</option>`).join("");
    if (current) sel.value = current;
  });

  return null;
}
