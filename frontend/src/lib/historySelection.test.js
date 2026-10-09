import { describe, expect, it } from "vitest";
import {
  isAdditiveHistoryClick,
  isRangeHistoryClick,
  nextHistorySelection,
  selectionForContextMenu,
} from "./historySelection.js";

const visible = ["a", "b", "c", "d"];

describe("nextHistorySelection", () => {
  it("click simple deja solo el nodo pulsado", () => {
    const next = nextHistorySelection({
      visibleIds: visible,
      selectedIds: ["a", "b"],
      anchorId: "a",
      clickedId: "c",
    });
    expect(next).toEqual({ selectedIds: ["c"], anchorId: "c" });
  });

  it("ctrl alterna el nodo y lo usa como ancla", () => {
    const added = nextHistorySelection({
      visibleIds: visible,
      selectedIds: ["a"],
      anchorId: "a",
      clickedId: "c",
      additive: true,
    });
    expect(added.selectedIds).toEqual(["a", "c"]);
    expect(added.anchorId).toBe("c");

    const removed = nextHistorySelection({
      visibleIds: visible,
      selectedIds: ["a", "c"],
      anchorId: "c",
      clickedId: "a",
      additive: true,
    });
    expect(removed.selectedIds).toEqual(["c"]);
    expect(removed.anchorId).toBe("a");
  });

  it("shift selecciona el rango desde el ancla", () => {
    const next = nextHistorySelection({
      visibleIds: visible,
      selectedIds: ["b"],
      anchorId: "b",
      clickedId: "d",
      range: true,
    });
    expect(next).toEqual({ selectedIds: ["b", "c", "d"], anchorId: "b" });
  });
});

describe("selectionForContextMenu", () => {
  it("si el nodo ya está seleccionado, conserva la selección", () => {
    expect(selectionForContextMenu(["a", "c"], "c")).toEqual({ selectedIds: ["a", "c"] });
  });

  it("si el nodo no está seleccionado, deja solo ese nodo", () => {
    expect(selectionForContextMenu(["a", "c"], "b")).toEqual({
      selectedIds: ["b"],
      anchorId: "b",
    });
  });
});

describe("modificadores", () => {
  it("ctrl y meta son aditivos; shift es rango", () => {
    expect(isAdditiveHistoryClick({ ctrlKey: true })).toBe(true);
    expect(isAdditiveHistoryClick({ metaKey: true })).toBe(true);
    expect(isAdditiveHistoryClick({ shiftKey: true })).toBe(false);
    expect(isRangeHistoryClick({ shiftKey: true })).toBe(true);
  });
});
