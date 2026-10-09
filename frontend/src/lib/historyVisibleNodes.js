import { getConversationGroup } from "./forest.js";

export function groupRootsByConversation(roots) {
  const byConv = new Map();
  (roots || []).forEach((n) => {
    const key = n.conversation_id;
    if (!byConv.has(key)) {
      byConv.set(key, {
        conversation_id: key,
        conversation_title: n.conversation_title || "Conversación",
        created_at: n.created_at,
        nodes: [],
      });
    }
    const g = byConv.get(key);
    g.nodes.push(n);
    if (n.created_at && (!g.created_at || n.created_at > g.created_at)) g.created_at = n.created_at;
  });
  return Array.from(byConv.values()).map((g) => {
    g.nodes.sort(
      (a, b) =>
        String(a.created_at || "").localeCompare(String(b.created_at || "")) ||
        String(a.id).localeCompare(String(b.id))
    );
    return g;
  });
}

function walkVisible(node, childrenByParent, expandedIds, out) {
  out.push(node.id);
  if (!expandedIds[node.id]) return;
  (childrenByParent[node.id] || []).forEach((child) => {
    walkVisible(child, childrenByParent, expandedIds, out);
  });
}

export function visibleHistoryNodeIds(roots, childrenByParent, expandedIds) {
  const groups = { hoy: [], ayer: [], semana: [], anteriores: [] };
  groupRootsByConversation(roots).forEach((g) => {
    groups[getConversationGroup(g.created_at)].push(g);
  });
  const order = ["hoy", "ayer", "semana", "anteriores"].filter((k) => groups[k].length);
  const expanded = expandedIds || {};
  const children = childrenByParent || {};
  const out = [];
  order.forEach((key) => {
    groups[key].forEach((g) => {
      g.nodes.forEach((n) => walkVisible(n, children, expanded, out));
    });
  });
  return out;
}
