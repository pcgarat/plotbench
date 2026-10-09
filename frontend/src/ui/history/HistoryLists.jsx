import { useEffect, useState } from "react";
import { historyStore, CONV_GROUP_LABELS, isMessagesHistoryMode } from "../../store/history.js";
import { sessionStore } from "../../store/session.js";
import { useStore } from "../../hooks/useStore.js";
import { getConversationGroup } from "../../lib/forest.js";
import { formatDateTime } from "../../lib/dates.js";
import { groupRootsByConversation, visibleHistoryNodeIds } from "../../lib/historyVisibleNodes.js";
import {
  loadMessageTreeRoots,
  toggleMessageTreeNode,
  restoreConversationFromTrash,
  permanentlyDeleteFromTrash,
  emptyTrash,
  onLeftHistorySortChange,
  onMessageHistorySearchInput,
  setLeftHistoryMode,
  applyHistoryNodeClick,
  applyHistoryNodeContextMenu,
  deleteSelectedHistoryNodes,
} from "../../app/historyActions.js";
import { newConversation, newPromptGeneratorConversation, openMessageTreeNode } from "../../app/sessionActions.js";
import { setLeftCollapsed } from "../layout/LayoutEffects.jsx";

function clampMenuPosition(x, y, width, height) {
  const left = Math.min(Math.max(8, x), Math.max(8, window.innerWidth - width - 8));
  const top = Math.min(Math.max(8, y), Math.max(8, window.innerHeight - height - 8));
  return { left, top };
}

function MessageTreeNodeRow({ node, depth, visibleIds, selectedIds }) {
  const expanded = useStore(historyStore, (s) => !!(s.treeExpandedIds || {})[node.id]);
  const childrenMap = useStore(historyStore, (s) => s.treeChildrenByParent || {});
  const selectedId = useStore(historyStore, (s) => s.treeSelectedMessageId);
  const focusId = useStore(sessionStore, (s) => s.focusMessageId || s.consultaAssistantId);
  const activeId = selectedId || focusId;
  const kids = childrenMap[node.id] || [];
  const when = formatDateTime(node.created_at);
  const preview = node.content_preview || "(sin texto)";
  const title = node.conversation_title || "Conversación";
  const selected = (selectedIds || []).includes(node.id);

  function handleClick(e) {
    if (e.target.closest(".message-tree-expand")) return;
    const next = applyHistoryNodeClick(node.id, e, visibleIds);
    if (next.shouldOpen) {
      openMessageTreeNode(node.conversation_id, node.id);
    }
  }

  function handleContextMenu(e) {
    e.preventDefault();
    e.stopPropagation();
    applyHistoryNodeContextMenu(node.id);
    const menuEvent = new CustomEvent("history-context-menu", {
      detail: { x: e.clientX, y: e.clientY },
    });
    document.dispatchEvent(menuEvent);
  }

  return (
    <>
      <div
        className={`conversation-item message-tree-item${node.id === activeId ? " active" : ""}${
          node.is_fork_edge ? " conversation-item-fork message-tree-item-fork" : ""
        }${selected ? " is-selected" : ""}`}
        data-id={node.id}
        data-conversation-id={node.conversation_id}
        data-depth={depth}
        aria-selected={selected ? "true" : "false"}
        title={`${title} · ${when}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      >
        <div className="conv-row">
          {node.has_children ? (
            <button
              type="button"
              className="message-tree-expand"
              aria-expanded={expanded ? "true" : "false"}
              aria-label={expanded ? "Colapsar" : "Expandir"}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleMessageTreeNode(node.id);
              }}
            >
              {expanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="message-tree-expand message-tree-expand-spacer" aria-hidden="true" />
          )}
          <button type="button" className="message-tree-open">
            <span className="conv-title">
              {node.is_fork_edge ? <span className="conv-kind-badge" title="Fork">fork</span> : null}
              {node.is_fork_edge ? " " : null}
              {preview}
            </span>
          </button>
        </div>
        <time className="conv-meta message-history-created" dateTime={node.created_at || ""}>
          {when}
        </time>
      </div>
      {expanded
        ? kids.map((ch) => (
            <MessageTreeNodeRow
              key={ch.id}
              node={ch}
              depth={depth + 1}
              visibleIds={visibleIds}
              selectedIds={selectedIds}
            />
          ))
        : null}
    </>
  );
}

function HistoryContextMenu() {
  const [menu, setMenu] = useState(null);
  const selectedCount = useStore(historyStore, (s) => (s.treeMultiSelectedIds || []).length);

  useEffect(() => {
    const open = (e) => {
      setMenu({ x: e.detail.x, y: e.detail.y });
    };
    document.addEventListener("history-context-menu", open);
    return () => document.removeEventListener("history-context-menu", open);
  }, []);

  useEffect(() => {
    if (!menu) return;
    const close = (e) => {
      if (e.target.closest && e.target.closest("#history-context-menu")) return;
      setMenu(null);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setMenu(null);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  if (!menu || !selectedCount) return null;
  const pos = clampMenuPosition(menu.x, menu.y, 180, 44);
  return (
    <div
      id="history-context-menu"
      className="history-context-menu"
      role="menu"
      style={{ left: pos.left, top: pos.top }}
    >
      <button
        type="button"
        className="msg-context-item"
        role="menuitem"
        onClick={async () => {
          setMenu(null);
          await deleteSelectedHistoryNodes();
        }}
      >
        Eliminar
      </button>
    </div>
  );
}

export function ConversationsList() {
  const roots = useStore(historyStore, (s) => s.treeRoots);
  const total = useStore(historyStore, (s) => s.treeRootsTotal);
  const deleted = useStore(historyStore, (s) => s.deletedConversations);
  const childrenMap = useStore(historyStore, (s) => s.treeChildrenByParent || {});
  const expandedIds = useStore(historyStore, (s) => s.treeExpandedIds || {});
  const selectedIds = useStore(historyStore, (s) => s.treeMultiSelectedIds || []);
  const visibleIds = visibleHistoryNodeIds(roots, childrenMap, expandedIds);

  const groups = { hoy: [], ayer: [], semana: [], anteriores: [] };
  groupRootsByConversation(roots).forEach((g) => {
    groups[getConversationGroup(g.created_at)].push(g);
  });
  const order = ["hoy", "ayer", "semana", "anteriores"].filter((k) => groups[k].length);

  return (
    <>
      <div className="conversations-list" id="conversations-list">
        {!roots.length ? <p className="conv-group-label">No hay respuestas todavía.</p> : null}
        {order.map((key) => (
          <div key={key}>
            <div className="conv-group-label" aria-hidden="true">
              {CONV_GROUP_LABELS[key]}
            </div>
            {groups[key].map((g) => (
              <div key={g.conversation_id} className="message-tree-conv-group">
                <div className="message-tree-conv-title" title={g.conversation_title}>
                  {g.conversation_title}
                </div>
                {g.nodes.map((n) => (
                  <MessageTreeNodeRow
                    key={n.id}
                    node={n}
                    depth={0}
                    visibleIds={visibleIds}
                    selectedIds={selectedIds}
                  />
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
      {roots.length < total ? (
        <div className="message-history-pager" id="message-tree-pager">
          <span className="message-history-page-meta">
            {roots.length} / {total}
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-small message-history-load-more"
            onClick={() => loadMessageTreeRoots({ append: true })}
          >
            Cargar más
          </button>
        </div>
      ) : null}
      <div className="conversations-trash" id="conversations-trash" hidden={!deleted.length}>
        <div className="conversations-trash-header">
          <div className="conv-group-label" id="conversations-trash-label">
            Papelera
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            id="conversations-trash-empty"
            onClick={() => emptyTrash()}
          >
            Vaciar
          </button>
        </div>
        <div className="conversations-trash-list" id="conversations-trash-list">
          {deleted.map((c) => (
            <div key={c.id} className="conversation-item" data-id={c.id}>
              <div className="conv-row">
                <span className="conv-title">{c.title}</span>
                <button type="button" className="btn btn-secondary btn-small" onClick={() => restoreConversationFromTrash(c.id)}>
                  Restaurar
                </button>
                <button type="button" className="btn btn-secondary btn-small" onClick={() => permanentlyDeleteFromTrash(c.id)}>
                  Eliminar
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
      <HistoryContextMenu />
    </>
  );
}

export function HistorySortSelect() {
  return null;
}

export { setLeftHistoryMode, newConversation, newPromptGeneratorConversation, onMessageHistorySearchInput, setLeftCollapsed, onLeftHistorySortChange };

// compat: modo mensajes ya no se usa como vista
void isMessagesHistoryMode;
