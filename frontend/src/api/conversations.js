import { API, fetchJson } from "./client.js";

export function listConversations(sort = "activity") {
  return fetchJson(`${API}/conversations?sort=${encodeURIComponent(sort)}`);
}

export function getConversation(id) {
  return fetchJson(`${API}/conversations/${id}`);
}

export function createConversation(body) {
  return fetchJson(`${API}/conversations`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function patchConversation(id, body) {
  return fetchJson(`${API}/conversations/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteConversation(id) {
  const res = await fetch(`${API}/conversations/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
}

export async function clearConversationMessages(id) {
  const res = await fetch(`${API}/conversations/${id}/messages`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
}

export async function restoreConversation(id) {
  const res = await fetch(`${API}/conversations/${id}/restore`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
}

export async function permanentlyDeleteConversation(id) {
  const res = await fetch(`${API}/conversations/${id}/permanent`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
}

export async function purgeDeletedConversations() {
  return fetchJson(`${API}/conversations/deleted`, { method: "DELETE" });
}

export function listDeletedConversations() {
  return fetchJson(`${API}/conversations/deleted`);
}

export function forkConversation(id, body) {
  return fetchJson(`${API}/conversations/${id}/fork`, {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
}

export function listMessages(params) {
  const search = params instanceof URLSearchParams ? params : new URLSearchParams();
  if (!(params instanceof URLSearchParams)) {
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v == null || v === "") return;
      search.set(k, String(v));
    });
  }
  return fetchJson(`${API}/messages?${search.toString()}`);
}

export function listMessagesList(params) {
  const search = params instanceof URLSearchParams ? params : new URLSearchParams();
  if (!(params instanceof URLSearchParams)) {
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v == null || v === "") return;
      search.set(k, String(v));
    });
  }
  return fetchJson(`${API}/messages/list?${search.toString()}`);
}

export function listMessageModels() {
  return fetchJson(`${API}/messages/models`);
}

export async function deleteMessage(conversationId, messageId) {
  const res = await fetch(
    `${API}/conversations/${conversationId}/messages/${messageId}`,
    { method: "DELETE" }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
}

export function deleteLastMessage(conversationId) {
  return fetch(`${API}/conversations/${conversationId}/messages/last`, {
    method: "DELETE",
  }).catch(() => {});
}

export function promptGeneratorTurn(conversationId, body) {
  return fetchJson(`${API}/conversations/${conversationId}/prompt-generator/turn`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function streamUrl(conversationId) {
  return `${API}/conversations/${conversationId}/messages/stream`;
}
