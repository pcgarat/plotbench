import { useEffect, useState } from "react";
import {
  historyStore,
  CONV_GROUP_LABELS,
  CONV_SORT_OPTIONS,
  MESSAGE_SEARCH_IN_OPTIONS,
  MESSAGE_SORT_OPTIONS,
  MESSAGE_SORT_DIRECTION_ASC,
  defaultMessageSortDirection,
  MESSAGE_PAGE_SIZE_OPTIONS,
  MESSAGE_MODEL_NONE,
  LEFT_HISTORY_MODE_MESSAGES,
  LEFT_HISTORY_MODE_CONVERSATIONS,
} from "../../store/history.js";
import { sessionStore } from "../../store/session.js";
import { useStore } from "../../hooks/useStore.js";
import { getConversationGroup } from "../../lib/forest.js";
import { formatDateTime } from "../../lib/dates.js";
import { groupRootsByConversation, visibleHistoryNodeIds } from "../../lib/historyVisibleNodes.js";
import {
  MESSAGE_DEFAULT_PAGE_SIZE,
  clampPage,
  pageRange,
  totalPages,
} from "../../lib/messagePagination.js";
import {
  loadMessageTreeRoots,
  toggleMessageTreeNode,
  restoreConversationFromTrash,
  permanentlyDeleteFromTrash,
  emptyTrash,
  onLeftHistorySortChange,
  onMessageSortDirectionToggle,
  onMessageHistorySearchInput,
  onMessageSearchInChange,
  onMessageModelFilterChange,
  onMessageShowDeletedToggle,
  setLeftHistoryMode,
  applyHistoryNodeClick,
  applyHistoryNodeContextMenu,
  deleteSelectedHistoryNodes,
  goToMessagePage,
  goToFirstMessagePage,
  goToPrevMessagePage,
  goToNextMessagePage,
  goToLastMessagePage,
  setMessagePageSize,
} from "../../app/historyActions.js";
import {
  newConversation,
  newPromptGeneratorConversation,
  openMessageTreeNode,
  openIsolatedMessage,
} from "../../app/sessionActions.js";
import { setLeftCollapsed } from "../layout/LayoutEffects.jsx";

function clampMenuPosition(x, y, width, height) {
  const left = Math.min(Math.max(8, x), Math.max(8, window.innerWidth - width - 8));
  const top = Math.min(Math.max(8, y), Math.max(8, window.innerHeight - height - 8));
  return { left, top };
}

/** Conmutador de vista del panel: mensajes (respuestas) o conversaciones (árbol). */
export function HistoryModeSwitch() {
  const mode = useStore(historyStore, (s) => s.mode);
  const isMessages = mode !== LEFT_HISTORY_MODE_CONVERSATIONS;
  return (
    <div className="left-history-mode" id="left-history-mode" role="tablist" aria-label="Vista del historial">
      <button
        type="button"
        role="tab"
        id="btn-history-mode-messages"
        className={`left-history-mode-btn${isMessages ? " is-active" : ""}`}
        aria-selected={isMessages ? "true" : "false"}
        onClick={() => setLeftHistoryMode(LEFT_HISTORY_MODE_MESSAGES)}
      >
        Mensajes
      </button>
      <button
        type="button"
        role="tab"
        id="btn-history-mode-conversations"
        className={`left-history-mode-btn${!isMessages ? " is-active" : ""}`}
        aria-selected={!isMessages ? "true" : "false"}
        onClick={() => setLeftHistoryMode(LEFT_HISTORY_MODE_CONVERSATIONS)}
      >
        Conversaciones
      </button>
    </div>
  );
}

/** Búsqueda, ámbito, orden y filtro por modelo del listado de mensajes. */
export function MessageListControls() {
  const searchIn = useStore(historyStore, (s) => s.messageSearchIn);
  const sort = useStore(historyStore, (s) => s.messageSort);
  const direction = useStore(
    historyStore,
    (s) => s.messageSortDirection || defaultMessageSortDirection(s.messageSort || "date")
  );
  const query = useStore(historyStore, (s) => s.messageListQuery);
  const modelFilter = useStore(historyStore, (s) => s.messageModelFilter);
  const models = useStore(historyStore, (s) => s.messageModels);
  const hasMissingModels = useStore(historyStore, (s) => s.hasMissingModels);
  const showDeleted = useStore(historyStore, (s) => s.messageShowDeleted);
  const ascending = direction === MESSAGE_SORT_DIRECTION_ASC;
  return (
    <div className="message-list-controls" id="message-list-controls">
      <input
        type="search"
        id="message-history-search"
        className="message-history-search"
        placeholder="Buscar mensajes"
        aria-label="Buscar mensajes"
        autoComplete="off"
        value={query}
        onChange={(e) => onMessageHistorySearchInput(e.target.value)}
      />
      <div className="message-list-filter-row">
        <select
          id="message-search-in"
          className="left-history-sort-select"
          aria-label="Ámbito de búsqueda"
          value={searchIn}
          onChange={(e) => onMessageSearchInChange(e.target.value)}
        >
          {MESSAGE_SEARCH_IN_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <div className="message-sort-order-group">
          <select
            id="left-history-sort-select"
            className="left-history-sort-select"
            aria-label="Ordenar mensajes"
            value={sort}
            onChange={(e) => onLeftHistorySortChange(e.target.value)}
          >
            {MESSAGE_SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            id="message-sort-direction"
            className="message-sort-direction"
            title={ascending ? "Orden ascendente" : "Orden descendente"}
            aria-label={ascending ? "Orden ascendente" : "Orden descendente"}
            aria-pressed={ascending ? "true" : "false"}
            onClick={() => onMessageSortDirectionToggle()}
          >
            {ascending ? "↑" : "↓"}
          </button>
        </div>
      </div>
      <select
        id="message-model-filter"
        className="left-history-sort-select"
        aria-label="Filtrar por modelo"
        value={modelFilter}
        onChange={(e) => onMessageModelFilterChange(e.target.value)}
      >
        <option value="">Todos los modelos</option>
        {hasMissingModels ? <option value={MESSAGE_MODEL_NONE}>Sin modelo</option> : null}
        {models.map((m) => (
          <option key={`${m.provider}:${m.model_id}`} value={m.model_id}>
            {m.model_id} · {m.count}
          </option>
        ))}
      </select>
      <label className="message-show-deleted" htmlFor="message-include-deleted">
        <input
          type="checkbox"
          id="message-include-deleted"
          checked={!!showDeleted}
          onChange={(e) => onMessageShowDeletedToggle(e.target.checked)}
        />
        <span>Mensajes eliminados</span>
      </label>
    </div>
  );
}

function MessageListRow({ item, active }) {
  const when = formatDateTime(item.created_at);
  const photos = item.photo_count || 0;
  const meta = `${item.title || "(sin título)"} · ${when}`;
  const canOpen = !!item.conversation_id;
  return (
    <div
      className={`conversation-item message-list-item${active ? " active" : ""}${
        item.deleted ? " is-deleted" : ""
      }${item.orphan || !canOpen ? " is-orphan" : ""}`}
      data-id={item.id}
      data-conversation-id={item.conversation_id || ""}
      title={meta}
      onClick={canOpen ? () => openIsolatedMessage(item.conversation_id, item.id) : undefined}
    >
      <div className="conv-row">
        <span className="conv-title">{item.title || "(sin título)"}</span>
      </div>
      <div className="message-list-meta">
        {item.deleted ? (
          <span className="message-deleted-badge" title="Conversación en la papelera">
            eliminado
          </span>
        ) : null}
        {item.orphan || !canOpen ? (
          <span className="message-orphan-badge" title="Su conversación ya no existe">
            origen desconocido
          </span>
        ) : null}
        <time className="message-history-created" dateTime={item.created_at || ""}>
          {when}
        </time>
        <span className="message-list-stats">
          {item.length} car. · {photos} foto{photos === 1 ? "" : "s"}
          {item.model_id ? ` · ${item.model_id}` : " · Sin modelo"}
        </span>
      </div>
    </div>
  );
}

/** Listado de mensajes (respuestas del agente) con paginación completa. */
export function MessagesList() {
  const items = useStore(historyStore, (s) => s.messageListItems);
  const total = useStore(historyStore, (s) => s.messageListTotal);
  const page = useStore(historyStore, (s) => s.messagePage || 1);
  const pageSize = useStore(historyStore, (s) => s.messagePageSize || MESSAGE_DEFAULT_PAGE_SIZE);
  const isEmptyQuery = useStore(historyStore, (s) => !!String(s.messageListQuery || "").trim());
  const error = useStore(historyStore, (s) => s.messageListError);
  const viewOnlyId = useStore(sessionStore, (s) => s.messageViewOnlyMessageId);
  const focusId = useStore(sessionStore, (s) => s.focusMessageId || s.consultaAssistantId);
  const activeId = viewOnlyId || focusId;
  const pages = totalPages(total, pageSize);
  const current = clampPage(page, pages);
  const range = pageRange(current, pageSize, total);
  const [pageInput, setPageInput] = useState(String(current));

  useEffect(() => {
    setPageInput(String(current));
  }, [current]);

  function submitPageInput(e) {
    e.preventDefault();
    const wanted = parseInt(pageInput, 10);
    if (Number.isNaN(wanted)) {
      setPageInput(String(current));
      return;
    }
    goToMessagePage(clampPage(wanted, pages));
  }

  return (
    <>
      <div className="conversations-list" id="messages-list">
        {!items.length ? (
          error ? (
            <p className="conv-group-label message-list-error" role="alert">
              {error}
            </p>
          ) : (
            <p className="conv-group-label">{isEmptyQuery ? "Sin resultados." : "No hay mensajes todavía."}</p>
          )
        ) : null}
        {items.map((m) => (
          <MessageListRow key={m.id} item={m} active={m.id === activeId} />
        ))}
      </div>
      <div className="message-history-pager" id="message-list-pager" hidden={total === 0}>
        <div className="message-history-page-row">
          <select
            id="message-page-size"
            className="left-history-sort-select message-page-size-select"
            aria-label="Elementos por página"
            value={pageSize}
            onChange={(e) => setMessagePageSize(Number(e.target.value))}
          >
            {MESSAGE_PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n} / pág.
              </option>
            ))}
          </select>
          <span className="message-history-page-meta" id="message-page-meta">
            {range.from}–{range.to} de {total}
          </span>
        </div>
        <div className="message-history-page-nav">
          <button
            type="button"
            id="message-page-first"
            className="btn btn-secondary btn-small message-page-btn"
            title="Primera página"
            aria-label="Primera página"
            disabled={current <= 1}
            onClick={() => goToFirstMessagePage()}
          >
            «
          </button>
          <button
            type="button"
            id="message-page-prev"
            className="btn btn-secondary btn-small message-page-btn"
            title="Página anterior"
            aria-label="Página anterior"
            disabled={current <= 1}
            onClick={() => goToPrevMessagePage()}
          >
            ‹
          </button>
          <form className="message-page-jump" onSubmit={submitPageInput}>
            <input
              type="number"
              id="message-page-input"
              className="message-page-input"
              min="1"
              max={pages}
              aria-label="Ir a la página"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onBlur={submitPageInput}
            />
            <span className="message-page-total">/ {pages}</span>
          </form>
          <button
            type="button"
            id="message-page-next"
            className="btn btn-secondary btn-small message-page-btn"
            title="Página siguiente"
            aria-label="Página siguiente"
            disabled={current >= pages}
            onClick={() => goToNextMessagePage()}
          >
            ›
          </button>
          <button
            type="button"
            id="message-page-last"
            className="btn btn-secondary btn-small message-page-btn"
            title="Última página"
            aria-label="Última página"
            disabled={current >= pages}
            onClick={() => goToLastMessagePage()}
          >
            »
          </button>
        </div>
      </div>
    </>
  );
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

/** Árbol de conversaciones/respuestas agrupado por fecha, con papelera. */
export function ConversationsTreeList() {
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

/** Selector de orden del árbol de conversaciones. */
function ConversationSortSelect() {
  const sort = useStore(historyStore, (s) => s.conversationSort);
  return (
    <div className="conversation-sort-wrap">
      <select
        id="conversation-sort-select"
        className="left-history-sort-select"
        aria-label="Ordenar conversaciones"
        value={sort}
        onChange={(e) => onLeftHistorySortChange(e.target.value)}
      >
        {CONV_SORT_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Panel izquierdo de historial: conmutador + listado de mensajes o árbol de conversaciones. */
export function ConversationsList() {
  const mode = useStore(historyStore, (s) => s.mode);
  const isMessages = mode !== LEFT_HISTORY_MODE_CONVERSATIONS;
  return (
    <>
      <HistoryModeSwitch />
      {isMessages ? (
        <>
          <MessageListControls />
          <MessagesList />
        </>
      ) : (
        <>
          <ConversationSortSelect />
          <ConversationsTreeList />
        </>
      )}
    </>
  );
}

export {
  setLeftHistoryMode,
  newConversation,
  newPromptGeneratorConversation,
  onMessageHistorySearchInput,
  onMessageSortDirectionToggle,
  setLeftCollapsed,
  onLeftHistorySortChange,
};
