/** Paginación del listado de mensajes: tamaño de página, página actual y navegación. */

export const MESSAGE_PAGE_SIZE_OPTIONS = [25, 50, 100, 200];
export const MESSAGE_DEFAULT_PAGE_SIZE = 50;

export function normalizePageSize(size) {
  const n = Math.floor(Number(size));
  return MESSAGE_PAGE_SIZE_OPTIONS.includes(n) ? n : MESSAGE_DEFAULT_PAGE_SIZE;
}

export function totalPages(total, pageSize) {
  const t = Math.max(0, Math.floor(Number(total) || 0));
  const s = Math.max(1, Math.floor(Number(pageSize) || 1));
  return Math.max(1, Math.ceil(t / s));
}

export function clampPage(page, pages) {
  const n = Math.floor(Number(page));
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(n, Math.max(1, Math.floor(Number(pages) || 1)));
}

export function pageOffset(page, pageSize) {
  const p = Math.max(1, Math.floor(Number(page) || 1));
  const s = Math.max(1, Math.floor(Number(pageSize) || 1));
  return (p - 1) * s;
}

/** Rango 1-based de los elementos visibles: `{ from, to }` (to = 0 si no hay items). */
export function pageRange(page, pageSize, total) {
  if (!total) return { from: 0, to: 0 };
  const p = Math.max(1, Math.floor(Number(page) || 1));
  const s = Math.max(1, Math.floor(Number(pageSize) || 1));
  const from = (p - 1) * s + 1;
  return { from, to: Math.min(p * s, total) };
}
