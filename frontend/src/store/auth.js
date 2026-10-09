/**
 * Cliente y store de autenticación multi-usuario.
 */

import { createStore } from "./createStore.js";
import { API, ApiError, fetchJson } from "../api/client.js";

export const authStore = createStore({
  ready: false,
  user: null,
  error: null,
});

export async function fetchMe() {
  try {
    const user = await fetchJson(`${API}/auth/me`, { credentials: "include" });
    authStore.set({ ready: true, user, error: null });
    return user;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      authStore.set({ ready: true, user: null, error: null });
      return null;
    }
    authStore.set({ ready: true, user: null, error: e.message || String(e) });
    return null;
  }
}

export async function login(username, password) {
  const user = await fetchJson(`${API}/auth/login`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  authStore.set({ ready: true, user, error: null });
  return user;
}

export async function register(username, password, email) {
  const body = { username, password };
  if (email) body.email = email;
  const user = await fetchJson(`${API}/auth/register`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify(body),
  });
  authStore.set({ ready: true, user, error: null });
  return user;
}

export async function logout() {
  try {
    const { flushPreferencesPush, stopPreferencesSync, clearLocalPreferencesCache } = await import(
      "./userPreferencesSync.js"
    );
    await flushPreferencesPush();
    stopPreferencesSync();
    clearLocalPreferencesCache();
  } catch (_) {}
  try {
    await fetchJson(`${API}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch (_) {}
  authStore.set({ ready: true, user: null, error: null });
}

export async function changePassword(currentPassword, newPassword) {
  await fetchJson(`${API}/auth/change-password`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export async function loadUserPreferences() {
  return fetchJson(`${API}/auth/preferences`, { credentials: "include" });
}

export async function saveUserPreferences(preferences) {
  return fetchJson(`${API}/auth/preferences`, {
    method: "PUT",
    credentials: "include",
    body: JSON.stringify({ preferences }),
  });
}
