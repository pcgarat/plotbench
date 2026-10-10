import * as imagesApi from "../api/images.js";
import { imagesStore } from "../store/images.js";
import { sessionStore } from "../store/session.js";
import { showError, showNotice } from "../store/ui.js";
import { escapeHtml } from "../lib/html.js";
import { findChatIllustration, resolvedSceneId } from "../lib/illustrationLocate.js";
import {
  isGalleryPanelVisible,
  setGalleryPanelVisible,
  setChatPanelVisible,
  initCenterPanelSplit,
} from "../store/layout.js";

export const GALLERY_PAGE_SIZE = 24;
export const GALLERY_TOOLBAR_FILTER_IDS = [
  "gallery-filter-prompt-model",
  "gallery-filter-prompt-provider",
  "gallery-filter-forge-model",
  "gallery-filter-steps",
  "gallery-filter-size",
  "gallery-filter-mode",
  "gallery-filter-seed",
];

let galleryLoadSeq = 0;
let galleryLightboxBusy = false;
let galleryPromptTimer = null;
let conversationFilterFilenames = null;
let conversationFilterPending = false;
let conversationFilterSeq = 0;
let conversationFilterTimer = null;
let galleryDidInit = false;
let chatViewerOpenBound = false;

function bindScrollReveal(el, scrollEl) {
  const node = scrollEl || el;
  if (!node) return;
  node.classList.toggle("is-scrollbar-visible", node.scrollHeight > node.clientHeight);
}

function emptyFilters() {
  return {
    promptModel: "",
    promptProvider: "",
    forgeModel: "",
    steps: "",
    size: "",
    mode: "",
    seed: "",
    promptQ: "",
    batchIds: [],
  };
}

function galleryFilterValue(id) {
  const node = document.getElementById(id);
  if (node) return String(node.value || "");
  const f = imagesStore.get().galleryFilters || emptyFilters();
  const map = {
    "gallery-filter-prompt-model": f.promptModel,
    "gallery-filter-prompt-provider": f.promptProvider,
    "gallery-filter-forge-model": f.forgeModel,
    "gallery-filter-steps": f.steps,
    "gallery-filter-size": f.size,
    "gallery-filter-mode": f.mode,
    "gallery-filter-seed": f.seed,
    "gallery-filter-prompt-q": f.promptQ,
  };
  return map[id] || "";
}

function selectedBatchIdsFromDom() {
  const sel = document.getElementById("gallery-filter-batch-ids");
  if (sel) {
    return [].filter
      .call(sel.selectedOptions || [], function (opt) {
        return Boolean(opt && opt.value);
      })
      .map(function (opt) {
        return String(opt.value);
      });
  }
  const f = imagesStore.get().galleryFilters || emptyFilters();
  return Array.isArray(f.batchIds) ? f.batchIds.filter(Boolean) : [];
}

function syncGalleryFiltersFromDom() {
  imagesStore.set({
    galleryFilters: {
      promptModel: galleryFilterValue("gallery-filter-prompt-model"),
      promptProvider: galleryFilterValue("gallery-filter-prompt-provider"),
      forgeModel: galleryFilterValue("gallery-filter-forge-model"),
      steps: galleryFilterValue("gallery-filter-steps"),
      size: galleryFilterValue("gallery-filter-size"),
      mode: galleryFilterValue("gallery-filter-mode"),
      seed: galleryFilterValue("gallery-filter-seed"),
      promptQ: galleryFilterValue("gallery-filter-prompt-q"),
      batchIds: selectedBatchIdsFromDom(),
    },
  });
}

export function appendGalleryToolbarFilters(params) {
  const model = galleryFilterValue("gallery-filter-prompt-model");
  if (model === "__none__") params.prompt_model = "";
  else if (model) params.prompt_model = model;
  const provider = galleryFilterValue("gallery-filter-prompt-provider");
  if (provider === "__none__") params.prompt_provider = "";
  else if (provider) params.prompt_provider = provider;
  const forge = galleryFilterValue("gallery-filter-forge-model");
  if (forge) params.forge_model = forge;
  const steps = galleryFilterValue("gallery-filter-steps");
  if (steps) params.steps = steps;
  const size = galleryFilterValue("gallery-filter-size");
  if (size) params.size = size;
  const mode = galleryFilterValue("gallery-filter-mode");
  if (mode) params.mode = mode;
  const seed = galleryFilterValue("gallery-filter-seed");
  if (seed) params.seed = seed;
  const q = galleryFilterValue("gallery-filter-prompt-q").trim();
  if (q) params.prompt_q = q;
  const batchIds = selectedBatchIdsFromDom();
  if (batchIds.length) params.batch_id = batchIds;
  return params;
}

function filterParams() {
  const params = {
    limit: GALLERY_PAGE_SIZE,
    offset: imagesStore.get().galleryOffset,
  };
  appendGalleryToolbarFilters(params);
  applyGalleryScopeToParams(params);
  return params;
}

export { filterParams as galleryListParams };

export function hasActiveGalleryToolbarFilters() {
  if (
    GALLERY_TOOLBAR_FILTER_IDS.some(function (id) {
      return Boolean(galleryFilterValue(id));
    })
  ) {
    return true;
  }
  if (selectedBatchIdsFromDom().length) return true;
  return Boolean(galleryFilterValue("gallery-filter-prompt-q").trim());
}

export function clearGalleryToolbarFilters() {
  GALLERY_TOOLBAR_FILTER_IDS.forEach(function (id) {
    const node = document.getElementById(id);
    if (node) node.value = "";
  });
  const promptQ = document.getElementById("gallery-filter-prompt-q");
  if (promptQ) promptQ.value = "";
  const batchSel = document.getElementById("gallery-filter-batch-ids");
  if (batchSel) {
    [].forEach.call(batchSel.options || [], function (opt) {
      opt.selected = false;
    });
  }
  if (galleryPromptTimer) {
    window.clearTimeout(galleryPromptTimer);
    galleryPromptTimer = null;
  }
  imagesStore.set({ galleryFilters: emptyFilters(), galleryOffset: 0 });
  onGalleryToolbarFilterChange();
}

export function onGalleryToolbarFilterChange() {
  syncGalleryFiltersFromDom();
  imagesStore.set({ galleryOffset: 0 });
  if (isGalleryPanelVisible()) loadGalleryPage();
  refreshConversationImageFilter();
}

export function filenameFromIllustratedSrc(src) {
  if (!src) return "";
  try {
    const path = String(src).split("?")[0];
    const marker = "/illustrated-images/";
    const idx = path.indexOf(marker);
    if (idx >= 0) return decodeURIComponent(path.slice(idx + marker.length).replace(/^\/+/, ""));
    const parts = path.split("/");
    return decodeURIComponent(parts[parts.length - 1] || "");
  } catch (_) {
    return "";
  }
}

export function applyIllustrationFilterToRoot(root) {
  if (!root) return;
  const active = hasActiveGalleryToolbarFilters();
  root.querySelectorAll(".chat-illustration-frame").forEach(function (frame) {
    if (!active || (!conversationFilterPending && conversationFilterFilenames == null)) {
      frame.classList.remove("is-gallery-filter-hidden");
      return;
    }
    if (conversationFilterPending) {
      frame.classList.add("is-gallery-filter-hidden");
      return;
    }
    const img = frame.querySelector("img.chat-illustration");
    const filename = img
      ? img.getAttribute("data-filename") || filenameFromIllustratedSrc(img.getAttribute("src"))
      : "";
    frame.classList.toggle("is-gallery-filter-hidden", !conversationFilterFilenames.has(filename));
  });
}

function applyIllustrationFilterToVisibleRoots() {
  applyIllustrationFilterToRoot(document.getElementById("messages-container"));
  applyIllustrationFilterToRoot(document.getElementById("reading-mode-body"));
}

export async function refreshConversationImageFilter() {
  const seq = ++conversationFilterSeq;
  syncImageFilterNotice();
  const convId = sessionStore.get().conversationId;
  if (!hasActiveGalleryToolbarFilters() || !convId) {
    conversationFilterFilenames = null;
    conversationFilterPending = false;
    applyIllustrationFilterToVisibleRoots();
    return;
  }
  conversationFilterPending = true;
  conversationFilterFilenames = null;
  applyIllustrationFilterToVisibleRoots();
  try {
    const params = appendGalleryToolbarFilters({ conversation_id: convId });
    const data = await imagesApi.matchingFilenames(params);
    if (seq !== conversationFilterSeq) return;
    conversationFilterFilenames = new Set((data && data.filenames) || []);
    conversationFilterPending = false;
    applyIllustrationFilterToVisibleRoots();
  } catch (err) {
    if (seq !== conversationFilterSeq) return;
    conversationFilterFilenames = null;
    conversationFilterPending = false;
    applyIllustrationFilterToVisibleRoots();
    showError("No se pudieron aplicar los filtros de imágenes al chat: " + err.message);
  }
}

export function scheduleConversationImageFilter() {
  if (conversationFilterTimer) window.clearTimeout(conversationFilterTimer);
  conversationFilterTimer = window.setTimeout(function () {
    conversationFilterTimer = null;
    refreshConversationImageFilter();
  }, 80);
}

export function syncImageFilterNotice() {
  const notice = document.getElementById("conversation-image-filter-notice");
  if (!notice) return;
  notice.hidden = !hasActiveGalleryToolbarFilters();
}

function galleryScopedConversationId() {
  const { galleryScopeAll } = imagesStore.get();
  const convId = sessionStore.get().conversationId;
  if (galleryScopeAll || !convId) return "";
  return convId;
}

function applyGalleryScopeToParams(params) {
  const convId = galleryScopedConversationId();
  if (convId) params.conversation_id = convId;
  const { galleryMessageId } = imagesStore.get();
  if (galleryMessageId) params.message_id = galleryMessageId;
  return params;
}

function renderGalleryScopeBar() {
  const allBtn = document.getElementById("gallery-scope-all");
  const label = document.getElementById("gallery-scope-conv-label");
  const convId = galleryScopedConversationId();
  if (allBtn) allBtn.setAttribute("aria-pressed", convId ? "false" : "true");
  if (!label) return;
  if (!convId) {
    label.hidden = true;
    label.textContent = "";
    return;
  }
  const titleEl = document.getElementById("conversation-title");
  const title = (titleEl && titleEl.value.trim()) || sessionStore.get().title || "Conversación";
  label.hidden = false;
  label.textContent = title;
}

function renderGalleryMessageChips(items) {
  const wrap = document.getElementById("image-gallery-messages");
  if (!wrap) return;
  if (!galleryScopedConversationId()) {
    wrap.hidden = true;
    wrap.innerHTML = "";
    return;
  }
  wrap.hidden = false;
  const galleryMessageId = imagesStore.get().galleryMessageId;
  const allActive = !galleryMessageId ? " is-active" : "";
  const chips = [
    '<button type="button" class="image-gallery-msg-chip' +
      allActive +
      '" data-gallery-message="">Toda la conversación</button>',
  ];
  (items || []).forEach(function (item) {
    const active = item.message_id === galleryMessageId ? " is-active" : "";
    const count = item.image_count != null ? item.image_count : 0;
    chips.push(
      '<button type="button" class="image-gallery-msg-chip' +
        active +
        '" data-gallery-message="' +
        escapeHtml(item.message_id) +
        '" title="' +
        escapeHtml(item.excerpt || "") +
        '"><span class="image-gallery-msg-chip-text">' +
        escapeHtml(item.excerpt || "(sin texto)") +
        '</span><span class="image-gallery-msg-chip-count">' +
        String(count) +
        "</span></button>"
    );
  });
  wrap.innerHTML = chips.join("");
}

function shortBatchLabel(batchId) {
  const id = String(batchId || "");
  if (id.length <= 8) return id;
  return id.slice(0, 8);
}

export function fillGalleryBatchSelect(batches) {
  const wrap = document.getElementById("image-gallery-families");
  const sel = document.getElementById("gallery-filter-batch-ids");
  if (!wrap || !sel) return;
  const galleryMessageId = imagesStore.get().galleryMessageId;
  const list = Array.isArray(batches)
    ? batches.filter(function (b) {
        return b && b.batch_id;
      })
    : [];
  if (!galleryMessageId || !list.length) {
    wrap.hidden = true;
    sel.innerHTML = "";
    return;
  }
  wrap.hidden = false;
  const filters = imagesStore.get().galleryFilters || emptyFilters();
  const selected = new Set(
    Array.isArray(filters.batchIds) ? filters.batchIds.filter(Boolean) : []
  );
  const validSelected = [];
  sel.innerHTML = "";
  list.forEach(function (item, index) {
    const id = String(item.batch_id);
    const count = item.image_count != null ? item.image_count : 0;
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = "Lote " + String(index + 1) + " · " + shortBatchLabel(id) + " (" + String(count) + ")";
    opt.title = id;
    if (selected.has(id)) {
      opt.selected = true;
      validSelected.push(id);
    }
    sel.appendChild(opt);
  });
  if (validSelected.length !== selected.size) {
    imagesStore.set(function (s) {
      return {
        ...s,
        galleryFilters: { ...(s.galleryFilters || emptyFilters()), batchIds: validSelected },
      };
    });
  }
}

function onGalleryBatchFilterChange() {
  syncGalleryFiltersFromDom();
  imagesStore.set({ galleryOffset: 0 });
  if (isGalleryPanelVisible()) loadGalleryPage();
  refreshConversationImageFilter();
}

async function loadGalleryMessageChips() {
  const convId = galleryScopedConversationId();
  if (!convId) {
    renderGalleryMessageChips([]);
    return;
  }
  try {
    const data = await imagesApi.listIllustratedMessages({ conversation_id: convId });
    renderGalleryMessageChips((data && data.items) || []);
  } catch (_) {
    renderGalleryMessageChips([]);
  }
}

function fillGallerySelect(selectId, values, extraNoneLabel) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">Todos</option>';
  if (extraNoneLabel) {
    const none = document.createElement("option");
    none.value = "__none__";
    none.textContent = extraNoneLabel;
    sel.appendChild(none);
  }
  (values || []).forEach(function (value) {
    const opt = document.createElement("option");
    opt.value = String(value);
    opt.textContent = String(value);
    sel.appendChild(opt);
  });
  if ([].some.call(sel.options, function (opt) { return opt.value === current; })) {
    sel.value = current;
  }
}

async function loadGalleryFacets() {
  try {
    const params = applyGalleryScopeToParams({});
    const data = await imagesApi.listIllustratedImageFacets(params);
    fillGallerySelect(
      "gallery-filter-prompt-model",
      data.prompt_models,
      data.has_missing_prompt_llm ? "Sin LLM" : ""
    );
    fillGallerySelect("gallery-filter-prompt-provider", data.prompt_providers, "");
    fillGallerySelect("gallery-filter-forge-model", data.forge_models, "");
    fillGallerySelect("gallery-filter-steps", data.steps, "");
    fillGallerySelect("gallery-filter-size", data.sizes, "");
    fillGallerySelect("gallery-filter-mode", data.modes, "");
    fillGallerySelect("gallery-filter-seed", data.seeds, "");
    const batches = data.batches || [];
    const selected = selectedBatchIdsFromDom();
    const validIds = new Set(
      batches.map(function (b) {
        return b && b.batch_id;
      }).filter(Boolean)
    );
    const stillValid = selected.filter(function (id) {
      return validIds.has(id);
    });
    if (stillValid.length !== selected.length) {
      imagesStore.set(function (s) {
        return {
          ...s,
          galleryFilters: { ...(s.galleryFilters || emptyFilters()), batchIds: stillValid },
        };
      });
    }
    imagesStore.set({
      galleryFilterOptions: {
        promptModel: data.prompt_models || [],
        promptProvider: data.prompt_providers || [],
        forgeModel: data.forge_models || [],
        steps: data.steps || [],
        size: data.sizes || [],
        mode: data.modes || [],
        seed: data.seeds || [],
        batches: batches,
      },
    });
    fillGalleryBatchSelect(batches);
  } catch (err) {
    showError("No se pudieron cargar los filtros de la galería: " + err.message);
  }
}

export async function refreshGalleryAfterScopeChange() {
  renderGalleryScopeBar();
  await Promise.all([loadGalleryFacets(), loadGalleryMessageChips()]);
  await loadGalleryPage();
}

function formatGalleryDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}

function galleryLlmLabel(item) {
  const bits = [item && item.prompt_provider, item && item.prompt_model].filter(Boolean);
  return bits.length ? bits.join(" · ") : "Sin LLM";
}

function formatIllustrationMetaValue(value) {
  if (value == null) return "—";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
  }
  return String(value);
}

function formatGenerationDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1000) return `${Math.round(n)} ms`;
  const seconds = n / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(2) : seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rem = seconds - minutes * 60;
  return `${minutes} min ${rem.toFixed(0)} s`;
}

function renderIllustrationMetaBody(data) {
  const params = (data && data.params) || {};
  const model =
    params.model ||
    (params.override_settings && params.override_settings.sd_model_checkpoint) ||
    "—";
  const size =
    params.width != null && params.height != null ? `${params.width} × ${params.height}` : "—";
  const genTime =
    params.generation_time_ms != null && Number.isFinite(Number(params.generation_time_ms))
      ? formatGenerationDuration(Number(params.generation_time_ms))
      : null;
  const llmLabel =
    [data.prompt_provider, data.prompt_model].filter(Boolean).join(" · ") ||
    [params.prompt_llm_provider, params.prompt_llm_model].filter(Boolean).join(" · ") ||
    null;
  const rows = [
    ["LLM del prompt", llmLabel],
    ["Modo", data.mode || params.mode || "—"],
    ["Modelo", model],
    ["Tamaño", size],
    ["Tiempo de generación", genTime],
    ["Sampler", params.sampler_name || "—"],
    ["Scheduler", params.scheduler || "—"],
    ["Steps", params.steps != null ? params.steps : "—"],
    ["CFG", params.cfg_scale != null ? params.cfg_scale : "—"],
    ["Seed", params.seed != null ? params.seed : "—"],
    ["Denoising", params.denoising_strength != null ? params.denoising_strength : null],
    ["Escena", data.scene_id || null],
    ["Archivo", data.filename || null],
  ].filter(function (pair) {
    return pair[1] != null && pair[1] !== "";
  });
  let html = '<dl class="illustration-meta-grid">';
  rows.forEach(function (pair) {
    html += `<dt>${escapeHtml(pair[0])}</dt><dd>${escapeHtml(formatIllustrationMetaValue(pair[1]))}</dd>`;
  });
  html += "</dl>";
  html +=
    '<div class="illustration-meta-prompt"><h3>Prompt</h3><pre>' +
    escapeHtml(params.prompt || "—") +
    "</pre></div>";
  return html;
}

export function renderGalleryGrid() {
  const grid = document.getElementById("image-gallery-grid");
  const pager = document.getElementById("image-gallery-pager");
  const galleryItems = imagesStore.get().galleryItems;
  const galleryOffset = imagesStore.get().galleryOffset;
  const galleryTotal = imagesStore.get().galleryTotal;
  if (!grid) return;
  if (!galleryItems.length) {
    grid.innerHTML = '<p class="image-gallery-empty">No hay imágenes con estos filtros.</p>';
    if (pager) pager.innerHTML = "";
    return;
  }
  grid.innerHTML = galleryItems
    .map(function (item, index) {
      const size =
        item.width != null && item.height != null ? item.width + "×" + item.height : "";
      const meta = [
        item.steps != null ? item.steps + " steps" : null,
        size,
        item.seed != null ? "seed " + item.seed : null,
        item.forge_model,
        galleryLlmLabel(item),
      ]
        .filter(Boolean)
        .join(" · ");
      const prompt = (item.prompt || "").trim() || "(sin prompt)";
      const when = formatGalleryDate(item.created_at);
      const sizeAttrs =
        item.width > 0 && item.height > 0
          ? ' width="' +
            item.width +
            '" height="' +
            item.height +
            '" style="aspect-ratio: ' +
            item.width +
            " / " +
            item.height +
            '"'
          : "";
      return (
        '<button type="button" class="image-gallery-card" data-gallery-index="' +
        index +
        '">' +
        '<img src="' +
        escapeHtml(item.url || "") +
        '" alt="" loading="lazy"' +
        sizeAttrs +
        " />" +
        '<div class="image-gallery-card-body">' +
        '<p class="image-gallery-card-prompt">' +
        escapeHtml(prompt) +
        "</p>" +
        '<p class="image-gallery-card-meta">' +
        escapeHtml(meta) +
        (when ? " · " + escapeHtml(when) : "") +
        "</p>" +
        '<p class="image-gallery-card-conv">' +
        escapeHtml(item.conversation_title || "Conversación") +
        "</p>" +
        "</div></button>"
      );
    })
    .join("");
  grid.querySelectorAll(".image-gallery-card").forEach(function (card) {
    card.addEventListener("click", function () {
      const idx = parseInt(card.getAttribute("data-gallery-index"), 10);
      if (Number.isFinite(idx)) openGalleryLightbox(idx);
    });
  });
  if (!pager) return;
  const from = galleryOffset + 1;
  const to = galleryOffset + galleryItems.length;
  const totalPages = galleryTotalPages(galleryTotal);
  const currentPage = galleryCurrentPage(galleryOffset);
  const prevDisabled = galleryOffset <= 0 ? " disabled" : "";
  const nextDisabled = galleryOffset + galleryItems.length >= galleryTotal ? " disabled" : "";
  const jumpDisabled = totalPages <= 1 ? " disabled" : "";
  pager.innerHTML =
    '<button type="button" class="btn btn-secondary btn-small" id="gallery-page-prev"' +
    prevDisabled +
    ">Anterior</button>" +
    '<span class="image-gallery-pager-range">' +
    from +
    "–" +
    to +
    " de " +
    galleryTotal +
    "</span>" +
    '<label class="image-gallery-pager-jump" for="gallery-page-input">Pág. ' +
    '<input type="number" id="gallery-page-input" class="image-gallery-page-input" min="1" max="' +
    totalPages +
    '" value="' +
    currentPage +
    '" inputmode="numeric"' +
    jumpDisabled +
    " /> de " +
    totalPages +
    "</label>" +
    '<button type="button" class="btn btn-secondary btn-small" id="gallery-page-next"' +
    nextDisabled +
    ">Siguiente</button>";
  const prev = document.getElementById("gallery-page-prev");
  const next = document.getElementById("gallery-page-next");
  const pageInput = document.getElementById("gallery-page-input");
  if (prev) {
    prev.addEventListener("click", function () {
      imagesStore.set({ galleryOffset: Math.max(0, galleryOffset - GALLERY_PAGE_SIZE) });
      loadGalleryPage();
    });
  }
  if (next) {
    next.addEventListener("click", function () {
      imagesStore.set({ galleryOffset: galleryOffset + GALLERY_PAGE_SIZE });
      loadGalleryPage();
    });
  }
  if (pageInput) {
    const commitPageJump = function () {
      const raw = pageInput.value.trim();
      if (!raw) {
        pageInput.value = String(galleryCurrentPage(imagesStore.get().galleryOffset));
        return;
      }
      const page = parseInt(raw, 10);
      if (!Number.isFinite(page)) {
        pageInput.value = String(galleryCurrentPage(imagesStore.get().galleryOffset));
        return;
      }
      goToGalleryPage(page);
      pageInput.value = String(
        galleryCurrentPage(imagesStore.get().galleryOffset, GALLERY_PAGE_SIZE)
      );
    };
    pageInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        commitPageJump();
        pageInput.blur();
      }
    });
    pageInput.addEventListener("change", commitPageJump);
    pageInput.addEventListener("wheel", function (event) {
      event.preventDefault();
    }, { passive: false });
  }
}

export function galleryTotalPages(total, pageSize = GALLERY_PAGE_SIZE) {
  const count = Math.max(0, Number(total) || 0);
  const size = Math.max(1, Number(pageSize) || GALLERY_PAGE_SIZE);
  if (count <= 0) return 0;
  return Math.ceil(count / size);
}

export function galleryCurrentPage(offset, pageSize = GALLERY_PAGE_SIZE) {
  const from = Math.max(0, Number(offset) || 0);
  const size = Math.max(1, Number(pageSize) || GALLERY_PAGE_SIZE);
  return Math.floor(from / size) + 1;
}

export function galleryOffsetForPage(page, total, pageSize = GALLERY_PAGE_SIZE) {
  const totalPages = galleryTotalPages(total, pageSize);
  if (totalPages <= 0) return 0;
  const size = Math.max(1, Number(pageSize) || GALLERY_PAGE_SIZE);
  let target = Math.trunc(Number(page));
  if (!Number.isFinite(target)) return 0;
  target = Math.min(Math.max(1, target), totalPages);
  return (target - 1) * size;
}

export function goToGalleryPage(page) {
  const state = imagesStore.get();
  const nextOffset = galleryOffsetForPage(page, state.galleryTotal);
  if (nextOffset === state.galleryOffset) return;
  imagesStore.set({ galleryOffset: nextOffset });
  loadGalleryPage();
}

export function galleryPageOffsetForAbsolute(absoluteIndex) {
  if (!Number.isFinite(absoluteIndex) || absoluteIndex < 0) return 0;
  return Math.floor(absoluteIndex / GALLERY_PAGE_SIZE) * GALLERY_PAGE_SIZE;
}

export async function loadGalleryPage(options = {}) {
  const silent = !!(options && options.silent);
  const requestedOffset =
    options && Number.isFinite(options.offset) ? options.offset : imagesStore.get().galleryOffset;
  const seq = ++galleryLoadSeq;
  if (!silent) closeGalleryLightbox();
  const grid = document.getElementById("image-gallery-grid");
  if (grid && !silent) {
    grid.innerHTML = '<p class="image-gallery-empty">Cargando…</p>';
  }
  try {
    const params = filterParams();
    params.offset = requestedOffset;
    const data = await imagesApi.listIllustratedImages(params);
    if (seq !== galleryLoadSeq) return false;
    const items = (data && data.items) || [];
    imagesStore.set({
      galleryItems: items,
      galleryTotal: data && typeof data.total === "number" ? data.total : items.length,
      galleryOffset: data && typeof data.offset === "number" ? data.offset : requestedOffset,
    });
    renderGalleryGrid();
    return true;
  } catch (err) {
    if (seq !== galleryLoadSeq) return false;
    if (!silent) {
      imagesStore.set({ galleryItems: [], galleryTotal: 0 });
      if (grid) {
        grid.innerHTML = '<p class="image-gallery-empty">No se pudo cargar la galería.</p>';
      }
    }
    showError("Error al cargar la galería: " + err.message);
    return false;
  }
}

export function closeGalleryLightbox() {
  const modal = document.getElementById("image-gallery-lightbox");
  if (modal) modal.hidden = true;
  imagesStore.set({ galleryLightboxIndex: -1, imageViewerSource: null });
}

/** Cierra el visor si el clic es fuera del contenido (backdrop del overlay). */
export function handleGalleryLightboxOverlayClick(event) {
  const lightbox = document.getElementById("image-gallery-lightbox");
  if (!lightbox || lightbox.hidden) return;
  if (event.target.closest(".image-gallery-lightbox-content")) return;
  closeGalleryLightbox();
}

/** Fotos ilustradas presentes ahora mismo en el chat, en orden de lectura. */
export function collectChatIllustrationItems(root) {
  const scope = root || document.getElementById("messages-container");
  if (!scope) return [];
  const conversationId = sessionStore.get().conversationId || "";
  return Array.from(scope.querySelectorAll("img.chat-illustration"))
    .map(function (img) {
      const frame = img.closest(".chat-illustration-frame");
      // Las fotos que la toolbar de galería oculta (o rotas) no participan en el recorrido.
      if (
        frame &&
        (frame.classList.contains("is-gallery-filter-hidden") ||
          frame.classList.contains("chat-illustration-missing"))
      ) {
        return null;
      }
      const filename =
        img.getAttribute("data-filename") || filenameFromIllustratedSrc(img.getAttribute("src"));
      if (!filename) return null;
      const row = img.closest(".message-row");
      return {
        filename: filename,
        url: img.getAttribute("src") || "",
        scene_id: img.getAttribute("data-scene") || resolvedSceneId(filename, ""),
        conversation_id: conversationId,
        message_id: row ? row.getAttribute("data-msg-id") || null : null,
      };
    })
    .filter(Boolean);
}

function chatViewerStartIndex(items, filename) {
  const idx = items.findIndex(function (item) {
    return item.filename === filename;
  });
  return idx >= 0 ? idx : 0;
}

/** Abre el visor de la galería sobre una foto concreta del panel conversación. */
export function openChatImageViewer(filename, options = {}) {
  if (!filename) return false;
  const items = collectChatIllustrationItems(options.root);
  if (!items.length) return false;
  const index = chatViewerStartIndex(items, filename);
  imagesStore.set({
    imageViewerSource: "chat",
    chatViewerItems: items,
    chatViewerIndex: index,
    galleryLightboxIndex: -1,
  });
  const modal = document.getElementById("image-gallery-lightbox");
  if (modal) modal.hidden = false;
  renderGalleryLightbox();
  return true;
}

/**
 * El visor de fotos del chat vive en el documento (como el propio overlay): pulsar
 * cualquier `img.chat-illustration` —panel conversación o modo lectura— lo abre con
 * sus parámetros. En captura, para que no dispare además el filtro de galería por fila;
 * sin stopPropagation, el resto de handlers del clic siguen funcionando.
 */
export function bindChatIllustrationViewerOpen() {
  if (chatViewerOpenBound) return;
  chatViewerOpenBound = true;
  document.addEventListener(
    "click",
    function (e) {
      const img = e.target.closest && e.target.closest("img.chat-illustration");
      if (!img) return;
      e.preventDefault();
      const filename =
        img.getAttribute("data-filename") || filenameFromIllustratedSrc(img.getAttribute("src"));
      const readingRoot = img.closest("#reading-mode-body");
      openChatImageViewer(filename, readingRoot ? { root: readingRoot } : {});
    },
    true
  );
}

function viewerActiveMeta() {
  const state = imagesStore.get();
  if (state.imageViewerSource === "chat") {
    const item = state.chatViewerItems[state.chatViewerIndex];
    return { item: item || null, total: state.chatViewerItems.length, abs: state.chatViewerIndex };
  }
  const item = state.galleryItems[state.galleryLightboxIndex];
  return {
    item: item || null,
    total: state.galleryTotal,
    abs: state.galleryOffset + state.galleryLightboxIndex,
  };
}

function setViewerPosition(absIndex) {
  const state = imagesStore.get();
  if (state.imageViewerSource === "chat") {
    imagesStore.set({ chatViewerIndex: absIndex });
  } else {
    imagesStore.set({ galleryLightboxIndex: absIndex - state.galleryOffset });
  }
}

/** Params de generación completos: la BD es la fuente de verdad en ambas fuentes. */
async function fetchViewerMeta(item) {
  if (!item || !item.filename) return null;
  const selected = item.filename;
  try {
    const data = await imagesApi.getIllustratedMeta(selected);
    const state = imagesStore.get();
    const source = state.imageViewerSource;
    const stillOpen =
      source === "chat"
        ? (state.chatViewerItems[state.chatViewerIndex] || {}).filename === selected
        : source === "gallery" &&
          (state.galleryItems[state.galleryLightboxIndex] || {}).filename === selected;
    if (!stillOpen || !data) return null;
    return {
      mode: data.mode || item.mode,
      params: data.params || {},
      scene_id: data.scene_id || item.scene_id,
      filename: data.filename || selected,
      prompt_model: data.prompt_model || item.prompt_model,
      prompt_provider: data.prompt_provider || item.prompt_provider,
    };
  } catch (_) {
    return {
      mode: item.mode,
      params: item.params || {},
      scene_id: item.scene_id,
      filename: selected,
      prompt_model: item.prompt_model,
      prompt_provider: item.prompt_provider,
    };
  }
}

function applyViewerMeta(meta) {
  if (!meta) return;
  const body = document.getElementById("image-gallery-lightbox-meta");
  if (!body) return;
  const patch = {
    mode: meta.mode,
    params: meta.params || {},
    scene_id: meta.scene_id,
    filename: meta.filename,
    prompt_model: meta.prompt_model,
    prompt_provider: meta.prompt_provider,
  };
  body.innerHTML =
    (body.dataset.link || "") +
    '<p class="image-gallery-card-meta" style="margin:0 0 8px">LLM del prompt: ' +
    escapeHtml(galleryLlmLabel(patch)) +
    "</p>" +
    renderIllustrationMetaBody(patch);
}

export function renderGalleryLightbox() {
  const { item, total, abs } = viewerActiveMeta();
  const img = document.getElementById("image-gallery-lightbox-img");
  const meta = document.getElementById("image-gallery-lightbox-meta");
  const prev = document.getElementById("image-gallery-lightbox-prev");
  const next = document.getElementById("image-gallery-lightbox-next");
  if (!item || !img || !meta) {
    const disabled = total <= 1;
    void prev;
    void next;
    return total > 1
      ? { prev: { disabled }, next: { disabled } }
      : { prev: { disabled }, next: { disabled } };
  }
  img.src = item.url || "";
  img.alt = (item.prompt || "").slice(0, 180);
  const showNav = total > 1;
  if (prev) {
    prev.hidden = !showNav;
    prev.disabled = abs <= 0;
  }
  if (next) {
    next.hidden = !showNav;
    next.disabled = abs >= total - 1;
  }
  const convLabel = item.conversation_title || "Conversación";
  const goBtn =
    '<p class="image-gallery-lightbox-link">' +
    '<button type="button" class="btn btn-primary btn-small" id="gallery-open-message">' +
    "Ir al mensaje</button> " +
    '<span class="image-gallery-card-meta">' +
    escapeHtml(convLabel) +
    (item.created_at ? " · " + escapeHtml(formatGalleryDate(item.created_at)) : "") +
    "</span></p>";
  meta.dataset.link = goBtn;
  meta.innerHTML =
    goBtn +
    '<p class="image-gallery-card-meta" style="margin:0 0 8px">LLM del prompt: ' +
    escapeHtml(galleryLlmLabel(item)) +
    "</p>" +
    renderIllustrationMetaBody({
      mode: item.mode,
      params: item.params || {},
      scene_id: item.scene_id,
      filename: item.filename,
      prompt_model: item.prompt_model,
      prompt_provider: item.prompt_provider,
    });
  const go = document.getElementById("gallery-open-message");
  if (go) {
    go.addEventListener("click", function () {
      closeGalleryLightbox();
      import("./sessionActions.js").then(function (mod) {
        return mod.goToConversationTarget({
          conversationId: item.conversation_id,
          messageId: item.message_id || null,
          filename: item.filename || "",
          sceneId: item.scene_id || "",
        });
      });
    });
  }
  fetchViewerMeta(item).then(applyViewerMeta);
  return { prev: { disabled: prev ? prev.disabled : true }, next: { disabled: next ? next.disabled : true } };
}

export function openGalleryLightbox(index) {
  const galleryItems = imagesStore.get().galleryItems;
  if (index < 0 || index >= galleryItems.length) return;
  imagesStore.set({
    galleryLightboxIndex: index,
    imageViewerSource: "gallery",
    chatViewerItems: [],
    chatViewerIndex: -1,
  });
  const modal = document.getElementById("image-gallery-lightbox");
  if (modal) modal.hidden = false;
  renderGalleryLightbox();
}

export async function stepGalleryLightbox(delta) {
  const state = imagesStore.get();
  const { item, total, abs } = viewerActiveMeta();
  if (!item || total < 2 || galleryLightboxBusy) return;
  const target = abs + delta;
  if (target < 0 || target >= total) return;
  if (state.imageViewerSource === "chat") {
    setViewerPosition(target);
    renderGalleryLightbox();
    return;
  }
  const { galleryItems, galleryOffset } = state;
  const pageOffset = galleryPageOffsetForAbsolute(target);
  if (pageOffset === galleryOffset) {
    openGalleryLightbox(target - galleryOffset);
    return;
  }
  galleryLightboxBusy = true;
  try {
    const ok = await loadGalleryPage({ silent: true, offset: pageOffset });
    if (!ok || imagesStore.get().galleryLightboxIndex < 0) return;
    const idx = target - imagesStore.get().galleryOffset;
    if (idx < 0 || idx >= imagesStore.get().galleryItems.length) {
      closeGalleryLightbox();
      return;
    }
    openGalleryLightbox(idx);
  } finally {
    galleryLightboxBusy = false;
  }
  void galleryItems;
}

export function setGalleryFilter(patch) {
  imagesStore.set((s) => ({
    ...s,
    galleryFilters: { ...s.galleryFilters, ...patch },
    galleryOffset: 0,
  }));
  loadGalleryPage();
  scheduleConversationImageFilter();
}

export function setGalleryScopeAll(all) {
  imagesStore.set(function (s) {
    return {
      ...s,
      galleryScopeAll: !!all,
      galleryUserChoseAll: !!all,
      galleryMessageId: all ? null : s.galleryMessageId,
      galleryOffset: 0,
      galleryFilters: {
        ...(s.galleryFilters || emptyFilters()),
        batchIds: all ? [] : (s.galleryFilters && s.galleryFilters.batchIds) || [],
      },
    };
  });
  refreshGalleryAfterScopeChange();
}

export async function purgeOrphans() {
  return purgeOrphanIllustratedFiles();
}

export async function purgeOrphanIllustratedFiles() {
  const btn = document.getElementById("gallery-purge-orphans");
  try {
    if (btn) btn.disabled = true;
    const preview = await imagesApi.listOrphans();
    const count = (preview && preview.count) || (preview && preview.filenames && preview.filenames.length) || 0;
    if (!count) {
      showNotice("No hay archivos huérfanos.");
      return;
    }
    const noun = count === 1 ? "archivo" : "archivos";
    if (!window.confirm("Se eliminarán " + count + " " + noun + " no incrustados en ningún mensaje. ¿Continuar?")) {
      return;
    }
    const result = await imagesApi.purgeOrphanIllustratedFiles();
    showNotice("Eliminados " + ((result && result.deleted_files) || 0) + " archivos huérfanos.");
    await refreshGalleryAfterScopeChange();
  } catch (e) {
    showError("No se pudieron eliminar archivos huérfanos: " + (e.message || e));
  } finally {
    if (btn) btn.disabled = false;
  }
}

export function enterGalleryView() {
  const convId = sessionStore.get().conversationId;
  const { galleryUserChoseAll } = imagesStore.get();
  if (convId && !galleryUserChoseAll) {
    imagesStore.set({ galleryScopeAll: false, galleryOffset: 0 });
  } else {
    imagesStore.set({ galleryOffset: 0 });
  }
  setGalleryPanelVisible(true);
  refreshGalleryAfterScopeChange();
}

export function highlightIllustrationInConversation(filename, sceneId, options = {}) {
  const root = document.getElementById("messages-container");
  if (!root) {
    if (!options.silent) showNotice("No se encontró la imagen en la conversación.");
    return false;
  }
  const found = findChatIllustration(root, {
    filename,
    sceneId,
    messageId: options.messageId,
  });
  const img = found && found.img;
  const target = found && found.frame;
  if (!target) {
    if (!options.silent) showNotice("No se encontró la imagen en la conversación.");
    return false;
  }
  target.classList.remove("is-gallery-filter-hidden");
  const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
  const height = target.getBoundingClientRect().height;
  root.scrollTop = Math.max(0, top - Math.max(0, (root.clientHeight - height) / 2));
  target.classList.add("illustration-debug-highlight");
  window.setTimeout(function () {
    target.classList.remove("illustration-debug-highlight");
  }, 2200);
  if (img && !img.complete) {
    img.addEventListener(
      "load",
      function () {
        highlightIllustrationInConversation(filename, sceneId, { silent: true, messageId: options.messageId });
      },
      { once: true }
    );
  }
  return true;
}

export function galleryQueryString() {
  const p = filterParams();
  const search = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => {
    if (v == null || v === "") return;
    if (Array.isArray(v)) {
      v.forEach(function (item) {
        if (item == null || item === "") return;
        search.append(k, String(item));
      });
      return;
    }
    search.set(k, String(v));
  });
  return search.toString();
}

export function initImageGallery() {
  if (galleryDidInit) return;
  galleryDidInit = true;
  document.getElementById("btn-image-gallery");
  document.getElementById("btn-center-chat");
  initCenterPanelSplit();
  if (isGalleryPanelVisible()) {
    refreshGalleryAfterScopeChange();
  }
  const messagesContainer = document.getElementById("messages-container");
  if (messagesContainer) {
    messagesContainer.addEventListener("click", function (e) {
      const illustrationImg = e.target.closest("img.chat-illustration");
      if (illustrationImg) return;
      if (!isGalleryPanelVisible()) return;
      if (e.target.closest("button, a, textarea, input, select")) return;
      const row = e.target.closest(".message-row");
      if (!row || !messagesContainer.contains(row)) return;
      const msgId = row.getAttribute("data-msg-id");
      if (!msgId) return;
      imagesStore.set(function (s) {
        return {
          ...s,
          galleryScopeAll: false,
          galleryMessageId: msgId,
          galleryOffset: 0,
          galleryFilters: { ...(s.galleryFilters || emptyFilters()), batchIds: [] },
        };
      });
      refreshGalleryAfterScopeChange();
    });
  }
  GALLERY_TOOLBAR_FILTER_IDS.forEach(function (id) {
    const node = document.getElementById(id);
    if (!node) return;
    node.addEventListener("change", onGalleryToolbarFilterChange);
  });
  const scopeAll = document.getElementById("gallery-scope-all");
  if (scopeAll) {
    scopeAll.addEventListener("click", function () {
      setGalleryScopeAll(true);
    });
  }
  const purgeOrphansBtn = document.getElementById("gallery-purge-orphans");
  if (purgeOrphansBtn) {
    purgeOrphansBtn.addEventListener("click", function () {
      purgeOrphanIllustratedFiles();
    });
  }
  const msgWrap = document.getElementById("image-gallery-messages");
  if (msgWrap) {
    msgWrap.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-gallery-message]");
      if (!btn || !msgWrap.contains(btn)) return;
      const next = btn.getAttribute("data-gallery-message") || "";
      imagesStore.set(function (s) {
        return {
          ...s,
          galleryMessageId: next || null,
          galleryOffset: 0,
          galleryFilters: { ...(s.galleryFilters || emptyFilters()), batchIds: [] },
        };
      });
      refreshGalleryAfterScopeChange();
    });
  }
  const batchSel = document.getElementById("gallery-filter-batch-ids");
  if (batchSel) {
    batchSel.addEventListener("change", onGalleryBatchFilterChange);
  }
  const promptQ = document.getElementById("gallery-filter-prompt-q");
  if (promptQ) {
    promptQ.addEventListener("input", function () {
      if (galleryPromptTimer) window.clearTimeout(galleryPromptTimer);
      galleryPromptTimer = window.setTimeout(function () {
        onGalleryToolbarFilterChange();
      }, 280);
    });
  }
  syncImageFilterNotice();
  const lightbox = document.getElementById("image-gallery-lightbox");
  const closeBtn = document.getElementById("image-gallery-lightbox-close");
  const prev = document.getElementById("image-gallery-lightbox-prev");
  const next = document.getElementById("image-gallery-lightbox-next");
  if (closeBtn) {
    closeBtn.addEventListener("click", function (e) {
      e.preventDefault();
      closeGalleryLightbox();
    });
  }
  if (lightbox) {
    lightbox.addEventListener("click", handleGalleryLightboxOverlayClick);
  }
  if (prev) {
    prev.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      stepGalleryLightbox(-1);
    });
  }
  if (next) {
    next.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      stepGalleryLightbox(1);
    });
  }
  document.addEventListener("keydown", function (e) {
    const modal = document.getElementById("image-gallery-lightbox");
    if (!modal || modal.hidden) return;
    if (e.key === "Escape") {
      e.preventDefault();
      closeGalleryLightbox();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      stepGalleryLightbox(-1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      stepGalleryLightbox(1);
    }
  });
  bindChatIllustrationViewerOpen();
  const galleryPanel = document.getElementById("image-gallery-panel");
  const galleryGrid = document.getElementById("image-gallery-grid");
  bindScrollReveal(galleryPanel || galleryGrid, galleryGrid);
  void setChatPanelVisible;
}
