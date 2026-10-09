import { fireEvent, render } from "@testing-library/react";
import { vi, beforeEach, describe, expect, it } from "vitest";
import App from "../../App.jsx";
import { layoutStore } from "../../store/layout.js";
import { debugStore, DEBUG_LOG_SIZE_DEFAULT } from "../../store/debug.js";

vi.mock("../../app/boot.js", () => ({
  bootApp: vi.fn(),
}));

vi.mock("../../store/auth.js", async () => {
  const { createStore } = await import("../../store/createStore.js");
  const authStore = createStore({
    ready: true,
    user: { id: "u1", username: "tester", is_admin: false },
    error: null,
  });
  return {
    authStore,
    fetchMe: vi.fn(async () => authStore.get().user),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
    loadUserPreferences: vi.fn(async () => ({ preferences: {} })),
    saveUserPreferences: vi.fn(),
  };
});

function resetPrefs() {
  localStorage.clear();
  layoutStore.set({
    ...layoutStore.get(),
    uiBaseFontScale: 1,
    conversationFontRem: 0.8,
    sidebarLeftFontScale: 1,
    sidebarRightFontScale: 1,
    imageSizeFactor: 1,
    renderMarkdown: true,
  });
  debugStore.set({ logSize: DEBUG_LOG_SIZE_DEFAULT });
}

describe("controles de Interfaz en Preferencias", () => {
  beforeEach(() => {
    resetPrefs();
  });

  it("al subir el texto base actualiza el porcentaje del panel", () => {
    render(<App />);
    const label = document.getElementById("pref-font-base-value");
    expect(label.textContent).toBe("100%");
    fireEvent.click(document.getElementById("pref-font-base-increase"));
    expect(label.textContent).toBe("105%");
    expect(document.documentElement.style.getPropertyValue("--ui-base-font-scale")).toBe("1.05");
  });

  it("al bajar el tamaño de ilustraciones actualiza el porcentaje y la variable CSS", () => {
    render(<App />);
    const label = document.getElementById("pref-image-value");
    expect(label.textContent).toBe("100%");
    fireEvent.click(document.getElementById("pref-image-decrease"));
    expect(label.textContent).toBe("90%");
    expect(document.documentElement.style.getPropertyValue("--chat-image-max-width")).toBe("90%");
    expect(layoutStore.get().imageSizeFactor).toBeCloseTo(0.9);
  });

  it("al subir el historial de debug actualiza el valor del panel", () => {
    render(<App />);
    const label = document.getElementById("pref-debug-log-value");
    expect(label.textContent).toBe("100");
    fireEvent.click(document.getElementById("pref-debug-log-increase"));
    expect(label.textContent).toBe("120");
  });

  it("el toggle de Markdown actualiza layoutStore y localStorage", () => {
    layoutStore.set({ ...layoutStore.get(), renderMarkdown: true });
    render(<App />);
    const toggle = document.getElementById("render-markdown-toggle");
    expect(toggle).toBeTruthy();
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    expect(layoutStore.get().renderMarkdown).toBe(false);
    expect(localStorage.getItem("renderMarkdown")).toBe("false");
  });
});
