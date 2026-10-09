export function nextHistorySelection({
  visibleIds,
  selectedIds,
  anchorId,
  clickedId,
  additive = false,
  range = false,
}) {
  const visible = Array.isArray(visibleIds) ? visibleIds : [];
  const selected = Array.isArray(selectedIds) ? selectedIds : [];
  if (!clickedId) {
    return { selectedIds: selected, anchorId: anchorId || null };
  }
  if (range && anchorId && visible.includes(anchorId) && visible.includes(clickedId)) {
    const from = visible.indexOf(anchorId);
    const to = visible.indexOf(clickedId);
    const start = Math.min(from, to);
    const end = Math.max(from, to);
    return { selectedIds: visible.slice(start, end + 1), anchorId };
  }
  if (additive) {
    const set = new Set(selected);
    if (set.has(clickedId)) set.delete(clickedId);
    else set.add(clickedId);
    return {
      selectedIds: visible.filter((id) => set.has(id)).concat(selected.filter((id) => !visible.includes(id) && set.has(id))),
      anchorId: clickedId,
    };
  }
  return { selectedIds: [clickedId], anchorId: clickedId };
}

export function selectionForContextMenu(selectedIds, clickedId) {
  const selected = Array.isArray(selectedIds) ? selectedIds : [];
  if (!clickedId) return { selectedIds: selected };
  if (selected.includes(clickedId)) return { selectedIds: selected };
  return { selectedIds: [clickedId], anchorId: clickedId };
}

export function isAdditiveHistoryClick(event) {
  return !!(event && (event.ctrlKey || event.metaKey));
}

export function isRangeHistoryClick(event) {
  return !!(event && event.shiftKey);
}
