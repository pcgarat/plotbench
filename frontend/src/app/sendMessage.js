import { streamUrl, promptGeneratorTurn, deleteLastMessage } from "../api/conversations.js";
import { sessionStore } from "../store/session.js";
import { settingsStore } from "../store/settings.js";
import { appStatus, showError, showNotice } from "../store/ui.js";
import { pushChatDebugEntry, updateChatDebugEntry } from "../store/debug.js";
import { buildModelParams } from "../lib/params.js";
import { visibleMessages } from "../lib/tree.js";
import { clampViewStartIndex } from "../lib/messageWindow.js";
import { newConversation } from "./sessionActions.js";
import { refreshLeftHistory, refreshMessageTreePreservingExpansion } from "./historyActions.js";
import { createStreamBuffer } from "./stream.js";
import { maybeIllustrateAssistantMessage } from "./illustrate.js";
import { getChatRulesTextForSystem } from "./rulesActions.js";

function applyTreeToStore(allMessages, activeLeafId, extra = {}) {
  const state = sessionStore.get();
  // Al continuar la conversación (nuevo turno) se abandona la vista de mensaje aislado.
  const leaveIsolated = extra.keepIsolated !== true;
  const ephemerals = (state.messages || []).filter((m) => m.ephemeral_debug);
  const messages = visibleMessages(allMessages, activeLeafId, extra.keepEphemeral === false ? [] : ephemerals);
  const viewStartIndex = clampViewStartIndex(messages, state.viewStartIndex);
  sessionStore.set({
    allMessages,
    activeLeafId,
    messages,
    viewStartIndex,
    ...(leaveIsolated
      ? { messageViewOnly: false, messageViewOnlyMessageId: null, messageViewOnlyConversationId: null }
      : {}),
    ...extra,
  });
}

export function setComposerPrimaryActionState() {
  const btn = document.getElementById("btn-send");
  const streaming = Boolean(sessionStore.get().abortController);
  if (btn) btn.classList.toggle("is-stop", streaming);
}

export async function sendPromptGeneratorTurn({ force = false } = {}) {
  const session = sessionStore.get();
  const content = (session.composerDraft || "").trim();
  if (!content && !force) return;
  let conversationId = session.conversationId;
  if (!conversationId) {
    const { newPromptGeneratorConversation } = await import("./sessionActions.js");
    const conv = await newPromptGeneratorConversation();
    if (!conv) return;
    conversationId = conv.id;
  }
  const statusId = appStatus.push("chat", "chat.sending");
  try {
    await promptGeneratorTurn(conversationId, {
      message: content,
      force,
      model_params: buildModelParams(),
    });
    sessionStore.set({ composerDraft: "" });
    const { openConversation } = await import("./sessionActions.js");
    await openConversation(conversationId);
    await refreshMessageTreePreservingExpansion();
  } catch (e) {
    showError("Error al generar prompt: " + e.message);
  } finally {
    appStatus.pop(statusId);
  }
}

export async function sendMessage() {
  const session = sessionStore.get();
  const currentAbortController = session.abortController;
  if (currentAbortController) return;
  if (session.conversationKind === "prompt_generator") {
    await sendPromptGeneratorTurn({ force: false });
    return;
  }
  const content = (session.composerDraft || "").trim();
  if (!content) return;
  const instructionOverride = (session.instructionOverride || "").trim() || null;

  if (!session.conversationId) {
    const conv = await newConversation();
    if (!conv) return;
  }

  const latest = sessionStore.get();
  const parentId =
    latest.activeLeafId &&
    !String(latest.activeLeafId).startsWith("tmp-") &&
    latest.allMessages.some((m) => m.id === latest.activeLeafId && !m.inherited)
      ? latest.activeLeafId
      : null;
  const tempUserId = "tmp-" + Date.now();
  let resolvedUserId = tempUserId;
  const allMessages = latest.allMessages.concat([
    { role: "user", content, id: tempUserId, parent_id: parentId },
  ]);
  applyTreeToStore(allMessages, tempUserId, {
    composerDraft: "",
    streamingText: "",
    streamingStatus: "analyzing",
    keepEphemeral: false,
  });

  const streamBuf = createStreamBuffer((text) => {
    sessionStore.set({ streamingText: text, streamingStatus: "streaming" });
  });
  let analyzingTimer = setInterval(() => {
    const cur = sessionStore.get();
    if (cur.streamingStatus !== "analyzing") return;
    const n = ((cur._dots || 0) + 1) % 4;
    sessionStore.set({ streamingText: "Analizando" + ".".repeat(n), _dots: n });
  }, 400);

  const chatStatusId = appStatus.push("chat", "chat.preparing");
  const abortController = new AbortController();
  sessionStore.set({ abortController });
  let chatDebugEntry = null;
  try {
    appStatus.update(chatStatusId, "chat.sending");
    const modelParams = buildModelParams();
    const bodyPayload = {
      content,
      instruction_override: instructionOverride,
      system_instruction_global: getChatRulesTextForSystem(),
      save_to_chromadb: settingsStore.get().saveToChromadb || "user",
    };
    if (parentId) bodyPayload.parent_message_id = parentId;
    if (Object.keys(modelParams).length > 0) bodyPayload.model_params = modelParams;
    chatDebugEntry = pushChatDebugEntry({
      title: "Petición al LLM de chat",
      status: "sending",
      details: {
        conversation_id: sessionStore.get().conversationId,
        model: settingsStore.get().currentModel,
        provider: settingsStore.get().currentProvider,
        params: modelParams,
      },
    });
    const res = await fetch(streamUrl(sessionStore.get().conversationId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyPayload),
      signal: abortController.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    appStatus.update(chatStatusId, "chat.awaiting_response");
    updateChatDebugEntry(chatDebugEntry.id, { status: "waiting" });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullContent = "";
    let debugRequest = null;
    const debugMetaLines = [];
    let receivedFirstToken = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let data;
        try {
          data = JSON.parse(line);
        } catch (e) {
          if (e instanceof SyntaxError) continue;
          throw e;
        }
        const isContentChunk = data.content !== undefined && Object.keys(data).length === 1;
        if (!isContentChunk) {
          debugMetaLines.push(line);
          updateChatDebugEntry(chatDebugEntry.id, {
            request: debugRequest,
            response: debugMetaLines.join("\n"),
          });
        }
        if (data.debug_request) {
          debugRequest = data.debug_request;
          updateChatDebugEntry(chatDebugEntry.id, {
            request: debugRequest,
            response: debugMetaLines.join("\n"),
            status: "waiting",
          });
        }
        if (data.mcp_contexts) appStatus.update(chatStatusId, "chat.receiving_context");
        if (data.error) {
          clearInterval(analyzingTimer);
          analyzingTimer = null;
          fullContent += `[Error: ${data.error}]`;
          streamBuf.append(`[Error: ${data.error}]`);
          appStatus.update(chatStatusId, "chat.error");
          updateChatDebugEntry(chatDebugEntry.id, {
            status: "error",
            details: data.error,
          });
        }
        if (data.user_message_id) {
          const cur = sessionStore.get();
          const nextAll = cur.allMessages.map((m) =>
            m.id === resolvedUserId ? { ...m, id: data.user_message_id } : m
          );
          resolvedUserId = data.user_message_id;
          applyTreeToStore(nextAll, resolvedUserId, { keepEphemeral: false });
        }
        if (data.content !== undefined) {
          if (analyzingTimer) {
            clearInterval(analyzingTimer);
            analyzingTimer = null;
          }
          if (!receivedFirstToken) {
            receivedFirstToken = true;
            appStatus.update(chatStatusId, "chat.streaming");
            updateChatDebugEntry(chatDebugEntry.id, { status: "streaming" });
          }
          fullContent += data.content;
          streamBuf.append(data.content);
        }
        if (data.stream_metadata && data.stream_metadata.usage) {
          sessionStore.set({
            lastUsage: {
              prompt_tokens: data.stream_metadata.usage.prompt_tokens ?? 0,
              completion_tokens: data.stream_metadata.usage.completion_tokens ?? 0,
            },
          });
        }
        if (data.done) {
          if (analyzingTimer) {
            clearInterval(analyzingTimer);
            analyzingTimer = null;
          }
          streamBuf.syncFlush();
          appStatus.update(chatStatusId, "chat.finalizing");
          const assistantMsg = {
            role: "assistant",
            content: fullContent,
            id: data.id || null,
            parent_id: resolvedUserId,
            debug_request: debugRequest || null,
            debug_response: debugMetaLines.length > 0 ? debugMetaLines.join("\n") : null,
          };
          updateChatDebugEntry(chatDebugEntry.id, {
            status: "done",
            request: debugRequest,
            response: debugMetaLines.join("\n"),
            details: fullContent,
          });
          const cur = sessionStore.get();
          const nextAll = cur.allMessages.concat([assistantMsg]);
          applyTreeToStore(nextAll, assistantMsg.id || resolvedUserId, {
            streamingText: "",
            streamingStatus: null,
            abortController: null,
            keepEphemeral: false,
          });
          refreshMessageTreePreservingExpansion();
          if (assistantMsg.id) maybeIllustrateAssistantMessage(assistantMsg.id);
        }
      }
    }
    if (analyzingTimer) clearInterval(analyzingTimer);
    sessionStore.set({ abortController: null, streamingStatus: null });
    appStatus.pop(chatStatusId);
  } catch (e) {
    if (analyzingTimer) clearInterval(analyzingTimer);
    if (chatDebugEntry) {
      updateChatDebugEntry(chatDebugEntry.id, {
        status: e.name === "AbortError" ? "cancelled" : "error",
        details: e.message || e.name,
      });
    }
    const cur = sessionStore.get();
    const cleaned = cur.allMessages.filter((m) => m.id !== tempUserId && m.id !== resolvedUserId);
    if (e.name === "AbortError") {
      appStatus.update(chatStatusId, "chat.cancelled");
      applyTreeToStore(cleaned, parentId || null, {
        streamingText: "",
        streamingStatus: null,
        abortController: null,
        keepEphemeral: false,
      });
      sessionStore.set((s) => ({
        ...s,
        messages: s.messages.concat([{ role: "assistant", content: "Cancelado", ephemeral_debug: true }]),
      }));
      if (cur.conversationId) deleteLastMessage(cur.conversationId);
      showNotice("Mensaje anulado.");
    } else {
      appStatus.update(chatStatusId, "chat.error");
      applyTreeToStore(cleaned, parentId || null, {
        streamingText: "",
        streamingStatus: null,
        abortController: null,
        keepEphemeral: false,
      });
      sessionStore.set((s) => ({
        ...s,
        messages: s.messages.concat([
          { role: "assistant", content: "Error al enviar: " + e.message, ephemeral_debug: true },
        ]),
      }));
      showError("Error al enviar: " + e.message);
    }
    appStatus.pop(chatStatusId);
  }
}

export function cancelLastMessage() {
  const ctrl = sessionStore.get().abortController;
  if (ctrl) ctrl.abort();
}

export function onComposerPrimaryClick() {
  if (sessionStore.get().abortController) cancelLastMessage();
  else sendMessage();
}
