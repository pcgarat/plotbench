import { describe, it, expect, beforeEach } from "vitest";
import {
  layoutStore,
  persistLayout,
  applyDocumentLayout,
  updateLayout,
  setSidebarTab,
  initAccordionState,
} from "./layout.js";

describe("layout store", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-sidebar-left");
  });

  it("persiste tema y colapso en localStorage", () => {
    updateLayout({ darkMode: true, leftSidebarCollapsed: true });
    expect(localStorage.getItem("darkMode")).toBe("true");
    expect(localStorage.getItem("leftSidebarCollapsed")).toBe("true");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-sidebar-left")).toBe("collapsed");
  });

  it("persiste la preferencia de Markdown en conversación", () => {
    updateLayout({ renderMarkdown: false });
    expect(localStorage.getItem("renderMarkdown")).toBe("false");
    updateLayout({ renderMarkdown: true });
    expect(localStorage.getItem("renderMarkdown")).toBe("true");
  });

  it("applyDocumentLayout respeta el estado actual", () => {
    layoutStore.set({ ...layoutStore.get(), darkMode: false, leftSidebarCollapsed: false });
    applyDocumentLayout(layoutStore.get());
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("al cambiar de tab muestra ese panel y oculta los demás", () => {
    document.body.innerHTML = `
      <div class="sidebar-tab-panel" id="tab-reglas" data-sidebar-panel="reglas"></div>
      <div class="sidebar-tab-panel" id="tab-parametros" data-sidebar-panel="parametros" hidden></div>
      <div class="sidebar-tab-panel" id="tab-imagenes" data-sidebar-panel="imagenes" hidden></div>
      <div class="sidebar-tab-panel" id="tab-preferencias" data-sidebar-panel="preferencias" hidden></div>
    `;
    setSidebarTab("parametros");
    expect(document.getElementById("tab-reglas").hidden).toBe(true);
    expect(document.getElementById("tab-parametros").hidden).toBe(false);
    expect(document.getElementById("tab-imagenes").hidden).toBe(true);
    expect(document.getElementById("tab-preferencias").hidden).toBe(true);
    setSidebarTab("imagenes");
    expect(document.getElementById("tab-parametros").hidden).toBe(true);
    expect(document.getElementById("tab-imagenes").hidden).toBe(false);
  });

  it("initAccordionState restaura los acordeones guardados", () => {
    document.body.innerHTML = `
      <div class="accordion-list">
        <div class="accordion-section is-open" data-accordion-section="a">
          <button class="accordion-header" aria-expanded="true"></button>
        </div>
        <div class="accordion-section" data-accordion-section="b">
          <button class="accordion-header" aria-expanded="false"></button>
        </div>
      </div>
    `;
    layoutStore.set({ ...layoutStore.get(), accordion: { a: false, b: true } });
    initAccordionState();
    const [a, b] = document.querySelectorAll(".accordion-section");
    expect(a.classList.contains("is-open")).toBe(false);
    expect(b.classList.contains("is-open")).toBe(true);
    expect(a.querySelector(".accordion-header").getAttribute("aria-expanded")).toBe("false");
    expect(b.querySelector(".accordion-header").getAttribute("aria-expanded")).toBe("true");
  });

  it("initAccordionState sin estado guardado deja el primero abierto", () => {
    document.body.innerHTML = `
      <div class="accordion-list">
        <div class="accordion-section is-open" data-accordion-section="a"><button class="accordion-header"></button></div>
        <div class="accordion-section is-open" data-accordion-section="b"><button class="accordion-header"></button></div>
      </div>
    `;
    layoutStore.set({ ...layoutStore.get(), accordion: {} });
    initAccordionState();
    const [a, b] = document.querySelectorAll(".accordion-section");
    expect(a.classList.contains("is-open")).toBe(true);
    expect(b.classList.contains("is-open")).toBe(false);
  });
});
