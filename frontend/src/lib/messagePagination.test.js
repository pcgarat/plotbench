import { describe, it, expect } from "vitest";
import {
  MESSAGE_PAGE_SIZE_OPTIONS,
  MESSAGE_DEFAULT_PAGE_SIZE,
  normalizePageSize,
  totalPages,
  clampPage,
  pageOffset,
  pageRange,
} from "./messagePagination.js";

describe("messagePagination", () => {
  it("normaliza el tamaño de página a las opciones válidas", () => {
    expect(normalizePageSize(25)).toBe(25);
    expect(normalizePageSize(100)).toBe(100);
    expect(normalizePageSize(7)).toBe(MESSAGE_DEFAULT_PAGE_SIZE);
    expect(normalizePageSize("nope")).toBe(MESSAGE_DEFAULT_PAGE_SIZE);
    expect(MESSAGE_PAGE_SIZE_OPTIONS).toContain(MESSAGE_DEFAULT_PAGE_SIZE);
  });

  it("calcula el total de páginas (mínimo 1)", () => {
    expect(totalPages(0, 50)).toBe(1);
    expect(totalPages(50, 50)).toBe(1);
    expect(totalPages(51, 50)).toBe(2);
    expect(totalPages(200, 25)).toBe(8);
  });

  it("acota la página al rango 1..totalPages", () => {
    expect(clampPage(0, 3)).toBe(1);
    expect(clampPage(2, 3)).toBe(2);
    expect(clampPage(99, 3)).toBe(3);
    expect(clampPage("nope", 3)).toBe(1);
  });

  it("traduce página a offset", () => {
    expect(pageOffset(1, 50)).toBe(0);
    expect(pageOffset(3, 50)).toBe(100);
    expect(pageOffset(0, 50)).toBe(0);
  });

  it("describe el rango visible de la página", () => {
    expect(pageRange(1, 50, 0)).toEqual({ from: 0, to: 0 });
    expect(pageRange(1, 50, 120)).toEqual({ from: 1, to: 50 });
    expect(pageRange(3, 50, 120)).toEqual({ from: 101, to: 120 });
  });
});
