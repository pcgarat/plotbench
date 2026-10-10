import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent } from "@testing-library/react";
import { imagesStore } from "../store/images.js";
import { sessionStore } from "../store/session.js";
import {
  appendGalleryToolbarFilters,
  galleryListParams,
  clearGalleryToolbarFilters,
  loadGalleryPage,
  renderGalleryLightbox,
  renderGalleryGrid,
  fillGalleryBatchSelect,
  highlightIllustrationInConversation,
  closeGalleryLightbox,
  handleGalleryLightboxOverlayClick,
  openChatImageViewer,
  bindChatIllustrationViewerOpen,
  collectChatIllustrationItems,
  stepGalleryLightbox,
  galleryTotalPages,
  galleryCurrentPage,
  galleryOffsetForPage,
  goToGalleryPage,
  GALLERY_PAGE_SIZE,
} from "./galleryActions.js";

const openConversationAtIllustration = vi.fn();
const openConversationAtMessage = vi.fn();

vi.mock("./sessionActions.js", () => ({
  openConversationAtIllustration: (...args) => openConversationAtIllustration(...args),
  openConversationAtMessage: (...args) => openConversationAtMessage(...args),
  goToConversationTarget: (target = {}) => {
    if (target.filename || target.sceneId) {
      return openConversationAtIllustration(target.conversationId, target.messageId, {
        filename: target.filename || "",
        sceneId: target.sceneId || "",
      });
    }
    return openConversationAtMessage(target.conversationId, target.messageId);
  },
}));

describe("galería", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0 }),
    }));
    openConversationAtIllustration.mockReset();
    openConversationAtMessage.mockReset();
    sessionStore.set({ conversationId: "c1" });
    imagesStore.set({
      galleryOffset: 0,
      galleryScopeAll: false,
      galleryMessageId: null,
      galleryFilters: {
        promptModel: "sdxl",
        promptProvider: "",
        forgeModel: "",
        steps: "20",
        size: "",
        mode: "",
        seed: "",
        promptQ: "gato",
        batchIds: [],
      },
      galleryFilterOptions: { batches: [] },
    });
  });

  it("filtros activos van al query", () => {
    const params = appendGalleryToolbarFilters({});
    expect(params.prompt_model).toBe("sdxl");
    expect(params.steps).toBe("20");
    expect(params.prompt_q).toBe("gato");
    const listed = galleryListParams();
    expect(listed.conversation_id).toBe("c1");
    expect(listed.limit).toBe(24);
  });

  it("batchIds activos van al query de listado", () => {
    imagesStore.set({
      galleryFilters: {
        promptModel: "",
        promptProvider: "",
        forgeModel: "",
        steps: "",
        size: "",
        mode: "",
        seed: "",
        promptQ: "",
        batchIds: ["batch-a", "batch-b"],
      },
    });
    const params = appendGalleryToolbarFilters({});
    expect(params.batch_id).toEqual(["batch-a", "batch-b"]);
    expect(galleryListParams().batch_id).toEqual(["batch-a", "batch-b"]);
  });

  it("clearGalleryToolbarFilters vacía el store", () => {
    document.body.innerHTML = `
      <div id="image-gallery-families">
        <select id="gallery-filter-batch-ids" multiple>
          <option value="batch-1" selected>Lote 1</option>
        </select>
      </div>
    `;
    imagesStore.set({
      galleryFilters: {
        promptModel: "x",
        promptProvider: "",
        forgeModel: "",
        steps: "",
        size: "",
        mode: "",
        seed: "",
        promptQ: "y",
        batchIds: ["batch-1"],
      },
      galleryMessageId: "m1",
      galleryFilterOptions: { batches: [{ batch_id: "batch-1", image_count: 2 }] },
    });
    clearGalleryToolbarFilters();
    expect(imagesStore.get().galleryFilters.promptModel).toBe("");
    expect(imagesStore.get().galleryFilters.promptQ).toBe("");
    expect(imagesStore.get().galleryFilters.batchIds).toEqual([]);
  });

  it("fillGalleryBatchSelect solo con mensaje seleccionado y lotes", () => {
    document.body.innerHTML = `
      <div id="image-gallery-families" hidden>
        <select id="gallery-filter-batch-ids" multiple></select>
      </div>
    `;
    imagesStore.set({
      galleryMessageId: null,
      galleryFilters: { batchIds: [] },
    });
    fillGalleryBatchSelect([{ batch_id: "aaaaaaaa-bbbb", image_count: 3 }]);
    const wrap = document.getElementById("image-gallery-families");
    const sel = document.getElementById("gallery-filter-batch-ids");
    expect(wrap.hidden).toBe(true);

    imagesStore.set({ galleryMessageId: "m1", galleryFilters: { batchIds: ["aaaaaaaa-bbbb"] } });
    fillGalleryBatchSelect([{ batch_id: "aaaaaaaa-bbbb", image_count: 3 }]);
    expect(wrap.hidden).toBe(false);
    expect(sel.options).toHaveLength(1);
    expect(sel.options[0].value).toBe("aaaaaaaa-bbbb");
    expect(sel.options[0].textContent).toContain("Lote 1");
    expect(sel.options[0].selected).toBe(true);
  });

  it("loadGalleryPage pide /illustrated-images, no /messages sin conversation_id", async () => {
    const urls = [];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url) => {
      urls.push(String(url));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          items: [],
          total: 0,
          prompt_models: [],
          prompt_providers: [],
          forge_models: [],
          steps: [],
          sizes: [],
          modes: [],
          seeds: [],
        }),
      };
    }));
    imagesStore.set({
      galleryScopeAll: true,
      galleryOffset: 0,
      galleryMessageId: null,
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
    });
    await loadGalleryPage({ silent: true });
    const listUrls = urls.filter((u) => u.includes("/illustrated-images"));
    expect(listUrls.some((u) => /\/illustrated-images\?/.test(u))).toBe(true);
    expect(
      listUrls.some((u) => /\/illustrated-images\/messages\?/.test(u) && !u.includes("conversation_id"))
    ).toBe(false);
  });

  it("highlightIllustrationInConversation centra la foto, no el inicio del mensaje", () => {
    document.body.innerHTML = `
      <div id="messages-container">
        <div class="message-row" data-msg-id="m1">
          <img class="chat-illustration" data-filename="antes.png" src="/api/illustrated-images/antes.png" />
          <span class="chat-illustration-frame">
            <img class="chat-illustration" data-filename="faro.png" src="/api/illustrated-images/faro.png" />
          </span>
        </div>
      </div>
    `;
    const root = document.getElementById("messages-container");
    const frame = document.querySelector(".chat-illustration-frame");
    const msg = document.querySelector('[data-msg-id="m1"]');
    const msgScroll = vi.fn();
    const photoScroll = vi.fn();
    msg.scrollIntoView = msgScroll;
    frame.scrollIntoView = photoScroll;
    Object.defineProperty(root, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(root, "scrollHeight", { configurable: true, value: 2000 });
    let scrollTop = 0;
    Object.defineProperty(root, "scrollTop", {
      configurable: true,
      get() {
        return scrollTop;
      },
      set(v) {
        scrollTop = v;
      },
    });
    root.getBoundingClientRect = () => ({ top: 0, bottom: 400, height: 400, left: 0, right: 300, width: 300 });
    msg.getBoundingClientRect = () => ({ top: 0, bottom: 2000, height: 2000, left: 0, right: 300, width: 300 });
    frame.getBoundingClientRect = () => ({ top: 800, bottom: 1000, height: 200, left: 0, right: 300, width: 300 });
    highlightIllustrationInConversation("faro.png", "s1");
    expect(scrollTop).toBe(700);
    expect(photoScroll).not.toHaveBeenCalled();
    expect(msgScroll).not.toHaveBeenCalled();
    expect(frame.classList.contains("illustration-debug-highlight")).toBe(true);
  });

  it("si el filename de la galería no está en el chat, ancla por escena (alt)", () => {
    document.body.innerHTML = `
      <div id="messages-container">
        <div class="message-row" data-msg-id="m1">
          <span class="chat-illustration-frame" id="frame-s1">
            <img class="chat-illustration" data-filename="aaa_s1.jpg" alt="escena s1" src="/api/illustrated-images/aaa_s1.jpg" />
          </span>
          <span class="chat-illustration-frame" id="frame-s40">
            <img class="chat-illustration" data-filename="bbb_s40.jpg" alt="escena s40" src="/api/illustrated-images/bbb_s40.jpg" />
          </span>
        </div>
      </div>
    `;
    const root = document.getElementById("messages-container");
    const frameS1 = document.getElementById("frame-s1");
    const frameS40 = document.getElementById("frame-s40");
    Object.defineProperty(root, "clientHeight", { configurable: true, value: 400 });
    let scrollTop = 0;
    Object.defineProperty(root, "scrollTop", {
      configurable: true,
      get() {
        return scrollTop;
      },
      set(v) {
        scrollTop = v;
      },
    });
    root.getBoundingClientRect = () => ({ top: 0, bottom: 400, height: 400, left: 0, right: 300, width: 300 });
    frameS1.getBoundingClientRect = () => ({ top: 40, bottom: 240, height: 200, left: 0, right: 300, width: 300 });
    frameS40.getBoundingClientRect = () => ({ top: 800, bottom: 1000, height: 200, left: 0, right: 300, width: 300 });
    const found = highlightIllustrationInConversation("070ace_s40.jpg", "s40");
    expect(found).toBe(true);
    expect(scrollTop).toBe(700);
    expect(frameS40.classList.contains("illustration-debug-highlight")).toBe(true);
    expect(frameS1.classList.contains("illustration-debug-highlight")).toBe(false);
  });

  it("con messageId de un mensaje que aún no está en el DOM no ancla el s40 de otro relato", () => {
    document.body.innerHTML = `
      <div id="messages-container">
        <div class="message-row" data-msg-id="m-early">
          <span class="chat-illustration-frame" id="frame-early">
            <img class="chat-illustration" data-filename="aaa_s40.jpg" alt="escena s40" data-scene="s40" src="/api/illustrated-images/aaa_s40.jpg" />
          </span>
        </div>
      </div>
    `;
    const root = document.getElementById("messages-container");
    Object.defineProperty(root, "clientHeight", { configurable: true, value: 400 });
    let scrollTop = 0;
    Object.defineProperty(root, "scrollTop", {
      configurable: true,
      get() {
        return scrollTop;
      },
      set(v) {
        scrollTop = v;
      },
    });
    root.getBoundingClientRect = () => ({ top: 0, bottom: 400, height: 400, left: 0, right: 300, width: 300 });
    const early = document.getElementById("frame-early");
    early.getBoundingClientRect = () => ({ top: 800, bottom: 1000, height: 200, left: 0, right: 300, width: 300 });
    const found = highlightIllustrationInConversation("070ace_s40.jpg", "s40", {
      silent: true,
      messageId: "m-target",
    });
    expect(found).toBe(false);
    expect(early.classList.contains("illustration-debug-highlight")).toBe(false);
    expect(scrollTop).toBe(0);
  });

  it("Ir al mensaje del visor cierra el lightbox y salta a la foto concreta", async () => {
    document.body.innerHTML = `
      <div id="image-gallery-lightbox">
        <img id="image-gallery-lightbox-img" alt="" />
        <button type="button" id="image-gallery-lightbox-prev"></button>
        <button type="button" id="image-gallery-lightbox-next"></button>
        <div id="image-gallery-lightbox-meta"></div>
      </div>
    `;
    imagesStore.set({
      galleryItems: [
        {
          filename: "faro.png",
          scene_id: "scene-faro",
          message_id: "m1",
          conversation_id: "c-other",
          url: "/api/illustrated-images/faro.png",
          conversation_title: "faro",
          prompt: "un faro",
        },
      ],
      galleryLightboxIndex: 0,
      galleryOffset: 0,
      galleryTotal: 1,
    });
    sessionStore.set({
      conversationId: "c1",
      messages: [{ id: "m-other" }],
      pendingReveal: null,
    });
    const modal = document.getElementById("image-gallery-lightbox");
    modal.hidden = false;
    renderGalleryLightbox();
    document.getElementById("gallery-open-message").click();
    await vi.waitFor(() => {
      expect(openConversationAtIllustration).toHaveBeenCalled();
    });
    expect(openConversationAtIllustration).toHaveBeenCalledWith("c-other", "m1", {
      filename: "faro.png",
      sceneId: "scene-faro",
    });
    expect(openConversationAtMessage).not.toHaveBeenCalled();
    expect(modal.hidden).toBe(true);
    expect(imagesStore.get().galleryLightboxIndex).toBe(-1);
    expect(sessionStore.get().pendingReveal).toBeNull();
  });

  it("cierra el lightbox al pulsar el fondo fuera del contenido", () => {
    document.body.innerHTML = `
      <div id="image-gallery-lightbox" class="modal-overlay image-gallery-lightbox">
        <div class="modal-content image-gallery-lightbox-content">
          <img id="image-gallery-lightbox-img" alt="" />
        </div>
      </div>
    `;
    const modal = document.getElementById("image-gallery-lightbox");
    modal.hidden = false;
    imagesStore.set({ galleryLightboxIndex: 0 });
    handleGalleryLightboxOverlayClick({ target: modal });
    expect(modal.hidden).toBe(true);
    expect(imagesStore.get().galleryLightboxIndex).toBe(-1);
  });

  it("no cierra el lightbox al pulsar dentro del contenido", () => {
    document.body.innerHTML = `
      <div id="image-gallery-lightbox" class="modal-overlay image-gallery-lightbox">
        <div class="modal-content image-gallery-lightbox-content">
          <img id="image-gallery-lightbox-img" alt="" />
        </div>
      </div>
    `;
    const modal = document.getElementById("image-gallery-lightbox");
    const content = modal.querySelector(".image-gallery-lightbox-content");
    modal.hidden = false;
    imagesStore.set({ galleryLightboxIndex: 0 });
    handleGalleryLightboxOverlayClick({ target: content });
    expect(modal.hidden).toBe(false);
    expect(imagesStore.get().galleryLightboxIndex).toBe(0);
    closeGalleryLightbox();
  });

  it("galleryTotalPages y galleryOffsetForPage calculan y limitan el salto", () => {
    expect(galleryTotalPages(0)).toBe(0);
    expect(galleryTotalPages(24)).toBe(1);
    expect(galleryTotalPages(25)).toBe(2);
    expect(galleryTotalPages(100, GALLERY_PAGE_SIZE)).toBe(5);
    expect(galleryCurrentPage(0)).toBe(1);
    expect(galleryCurrentPage(24)).toBe(2);
    expect(galleryOffsetForPage(1, 100)).toBe(0);
    expect(galleryOffsetForPage(3, 100)).toBe(48);
    expect(galleryOffsetForPage(99, 100)).toBe(96);
    expect(galleryOffsetForPage(0, 100)).toBe(0);
    expect(galleryOffsetForPage(-2, 100)).toBe(0);
    expect(galleryOffsetForPage("x", 100)).toBe(0);
  });

  it("renderGalleryGrid muestra input de página y goToGalleryPage salta de offset", async () => {
    document.body.innerHTML = `
      <div id="image-gallery-grid"></div>
      <div id="image-gallery-pager"></div>
    `;
    const item = {
      filename: "a.png",
      url: "/api/illustrated-images/a.png",
      prompt: "gato",
      conversation_title: "c",
    };
    imagesStore.set({
      galleryItems: Array.from({ length: 24 }, (_, i) => ({ ...item, filename: `a${i}.png` })),
      galleryOffset: 0,
      galleryTotal: 60,
      galleryLightboxIndex: -1,
    });
    renderGalleryGrid();
    const input = document.getElementById("gallery-page-input");
    expect(input).toBeTruthy();
    expect(input.value).toBe("1");
    expect(input.max).toBe("3");
    expect(document.querySelector(".image-gallery-pager-jump")).toBeTruthy();
    expect(document.getElementById("image-gallery-pager").textContent).toContain("de 3");

    const urls = [];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url) => {
      urls.push(String(url));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          items: Array.from({ length: 12 }, (_, i) => ({ ...item, filename: `b${i}.png` })),
          total: 60,
          prompt_models: [],
          prompt_providers: [],
          forge_models: [],
          steps: [],
          sizes: [],
          modes: [],
          seeds: [],
        }),
      };
    }));
    goToGalleryPage(3);
    expect(imagesStore.get().galleryOffset).toBe(48);
    await vi.waitFor(() => {
      expect(urls.some((u) => u.includes("offset=48"))).toBe(true);
    });
  });

  it("Enter en el input de página salta y hace clamp fuera de rango", async () => {
    document.body.innerHTML = `
      <div id="image-gallery-grid"></div>
      <div id="image-gallery-pager"></div>
    `;
    const item = {
      filename: "a.png",
      url: "/api/illustrated-images/a.png",
      prompt: "gato",
      conversation_title: "c",
    };
    imagesStore.set({
      galleryItems: Array.from({ length: 24 }, (_, i) => ({ ...item, filename: `a${i}.png` })),
      galleryOffset: 0,
      galleryTotal: 50,
      galleryLightboxIndex: -1,
      galleryScopeAll: true,
      galleryMessageId: null,
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
    });
    renderGalleryGrid();
    const urls = [];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url) => {
      urls.push(String(url));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          items: Array.from({ length: 2 }, (_, i) => ({ ...item, filename: `z${i}.png` })),
          total: 50,
          prompt_models: [],
          prompt_providers: [],
          forge_models: [],
          steps: [],
          sizes: [],
          modes: [],
          seeds: [],
        }),
      };
    }));
    const input = document.getElementById("gallery-page-input");
    input.value = "99";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(imagesStore.get().galleryOffset).toBe(48);
    await vi.waitFor(() => {
      expect(urls.some((u) => u.includes("offset=48"))).toBe(true);
    });
  });

  describe("visor de fotos del chat", () => {
    function fixtureChat() {
      document.body.innerHTML = `
        <div id="image-gallery-lightbox" hidden>
          <img id="image-gallery-lightbox-img" alt="" />
          <button type="button" id="image-gallery-lightbox-prev"></button>
          <button type="button" id="image-gallery-lightbox-next"></button>
          <div id="image-gallery-lightbox-meta"></div>
        </div>
        <div id="messages-container">
          <div class="message-row" data-msg-id="m1">
            <span class="chat-illustration-frame">
              <img class="chat-illustration" data-filename="faro.png" data-scene="s1" src="/api/illustrated-images/faro.png" />
            </span>
          </div>
          <div class="message-row" data-msg-id="m2">
            <span class="chat-illustration-frame">
              <img class="chat-illustration" data-filename="playa.png" data-scene="s2" src="/api/illustrated-images/playa.png" />
            </span>
          </div>
        </div>
      `;
    }

    it("abre el visor con la foto pulsada y navega por las fotos de la conversación", async () => {
      fixtureChat();
      sessionStore.set({ conversationId: "c1" });
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ params: { prompt: "un faro" }, mode: "txt2img" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      expect(openChatImageViewer("playa.png")).toBe(true);
      const modal = document.getElementById("image-gallery-lightbox");
      expect(modal.hidden).toBe(false);
      expect(imagesStore.get().imageViewerSource).toBe("chat");
      expect(imagesStore.get().chatViewerItems.map((i) => i.filename)).toEqual([
        "faro.png",
        "playa.png",
      ]);
      expect(imagesStore.get().chatViewerIndex).toBe(1);
      expect(document.getElementById("image-gallery-lightbox-img").src).toContain("playa.png");
      expect(document.getElementById("image-gallery-lightbox-next").disabled).toBe(true);

      await vi.waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          "/api/illustrated-images/playa.png/meta",
          expect.anything()
        );
      });

      stepGalleryLightbox(-1);
      expect(imagesStore.get().chatViewerIndex).toBe(0);
      expect(document.getElementById("image-gallery-lightbox-img").src).toContain("faro.png");
      expect(document.getElementById("image-gallery-lightbox-prev").disabled).toBe(true);
    });

    it("Ir al mensaje desde el visor del chat cierra el visor y ancla la foto", async () => {
      fixtureChat();
      sessionStore.set({ conversationId: "c1" });
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ params: {} }) })
      );
      openChatImageViewer("faro.png");
      document.getElementById("gallery-open-message").click();
      await vi.waitFor(() => {
        expect(openConversationAtIllustration).toHaveBeenCalledWith("c1", "m1", {
          filename: "faro.png",
          sceneId: "s1",
        });
      });
      expect(document.getElementById("image-gallery-lightbox").hidden).toBe(true);
      expect(imagesStore.get().imageViewerSource).toBeNull();
    });

    it("pulsar una foto del chat abre el visor (delegación en captura)", () => {
      fixtureChat();
      sessionStore.set({ conversationId: "c1" });
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ params: {} }) })
      );
      bindChatIllustrationViewerOpen();
      const img = document.querySelector('img[data-filename="playa.png"]');
      fireEvent.click(img);
      expect(imagesStore.get().imageViewerSource).toBe("chat");
      expect(imagesStore.get().chatViewerIndex).toBe(1);
      expect(document.getElementById("image-gallery-lightbox").hidden).toBe(false);
    });

    it("cerrar el visor limpia la fuente activa", () => {
      fixtureChat();
      sessionStore.set({ conversationId: "c1" });
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ params: {} }) })
      );
      openChatImageViewer("faro.png");
      closeGalleryLightbox();
      expect(imagesStore.get().imageViewerSource).toBeNull();
      expect(imagesStore.get().galleryLightboxIndex).toBe(-1);
    });

    it("no incluye fotos ocultas por los filtros de galería", () => {
      fixtureChat();
      sessionStore.set({ conversationId: "c1" });
      document
        .querySelector('img[data-filename="faro.png"]')
        .closest(".chat-illustration-frame")
        .classList.add("is-gallery-filter-hidden");
      const items = collectChatIllustrationItems();
      expect(items.map((i) => i.filename)).toEqual(["playa.png"]);
    });
  });
});
