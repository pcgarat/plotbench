"""Historial izquierdo unificado: árbol de respuestas (nodos assistant)."""
from pathlib import Path

from tests.frontend_source import frontend_file, frontend_markup

STYLE_CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "styles" / "style.css"
APP_JSX = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.jsx"


def _css() -> str:
    return STYLE_CSS.read_text(encoding="utf-8")


def _rule_body(css: str, selector: str) -> str:
    marker = f"{selector} {{"
    assert marker in css, f"Falta selector {selector}"
    return css.split(marker, 1)[1].split("}", 1)[0]


def test_message_tree_row_shows_preview_and_datetime():
    lists = frontend_file("ui/history/HistoryLists.jsx")
    assert "message-tree-item" in lists
    assert "message-history-created" in lists
    assert "formatDateTime" in lists
    assert "openMessageTreeNode" in lists
    assert "content_preview" in lists


def test_message_tree_created_line_styles_exist():
    css = _css()
    meta = _rule_body(css, ".column-left .message-tree-item .message-history-created")
    assert "display: block" in meta
    assert "font-variant-numeric: tabular-nums" in meta
    assert "font-size" in meta


def test_message_tree_api_client_and_actions_exist():
    api = frontend_file("api/messageTree.js")
    actions = frontend_file("app/historyActions.js")
    assert "/message-tree/roots" in api
    assert "/message-tree/" in api
    assert "loadMessageTreeRoots" in actions
    assert "loadMessageTreeChildren" in actions
    assert "toggleMessageTreeNode" in actions
    assert "refreshMessageTreePreservingExpansion" in actions


def test_left_panel_exposes_messages_and_conversations_modes():
    lists = frontend_file("ui/history/HistoryLists.jsx")
    assert "btn-history-mode-messages" in lists
    assert "btn-history-mode-conversations" in lists
    assert "openIsolatedMessage" in lists
    assert "message-list-item" in lists


def test_messages_list_controls_and_pager():
    lists = frontend_file("ui/history/HistoryLists.jsx")
    assert 'id="message-history-search"' in lists
    assert 'id="message-search-in"' in lists
    assert 'id="left-history-sort-select"' in lists
    assert 'id="message-sort-direction"' in lists
    assert 'id="message-model-filter"' in lists
    assert "loadMessageList({ append: true })" in lists
    assert "Cargar más" in lists


def test_opening_isolated_message_shows_only_that_message():
    session = frontend_file("app/sessionActions.js")
    assert "export async function openIsolatedMessage" in session
    open_fn = session.split("export async function openIsolatedMessage")[1].split(
        "export async function openConversationAtIllustration"
    )[0]
    assert "messageViewOnly: true" in open_fn
    assert "messageViewOnlyMessageId: messageId" in open_fn


def test_continued_chat_leaves_isolated_view():
    session = frontend_file("app/sessionActions.js")
    send = frontend_file("app/sendMessage.js")
    assert "export function clearIsolatedMessageView" in session
    assert "clearIsolatedMessageView()" in session
    apply_fn = send.split("function applyTreeToStore")[1].split("export function setComposerPrimaryActionState")[0]
    assert "messageViewOnly: false" in apply_fn


def test_messages_list_actions_cover_search_scope_and_model_filter():
    actions = frontend_file("app/historyActions.js")
    assert "export async function loadMessageList" in actions
    assert "export function onMessageSearchInChange" in actions
    assert "export function onMessageModelFilterChange" in actions
    api = frontend_file("api/conversations.js")
    assert "/messages/list" in api
    assert "/messages/models" in api


def test_flat_messages_toggle_removed_from_sidebar():
    app = APP_JSX.read_text(encoding="utf-8")
    left = app[app.index('id="column-left"') : app.index("</aside>")]
    assert 'id="btn-history-messages"' not in left
    assert 'id="message-history-search-wrap"' not in left
    assert "<ConversationsList" in left


def test_message_tree_load_more_roots():
    lists = frontend_file("ui/history/HistoryLists.jsx")
    actions = frontend_file("app/historyActions.js")
    assert "loadMessageTreeRoots({ append: true })" in lists
    assert "Cargar más" in lists
    load_fn = actions.split("export async function loadMessageTreeRoots")[1].split(
        "export async function loadMessageTreeChildren"
    )[0]
    assert "append" in load_fn
    assert "offset" in load_fn


def test_opening_tree_node_keeps_composer_path():
    session = frontend_file("app/sessionActions.js")
    assert "export async function openMessageTreeNode" in session
    open_fn = session.split("export async function openMessageTreeNode")[1].split(
        "export async function openConversationAtIllustration"
    )[0]
    assert "openConversationAtMessage" in open_fn
    assert "composerCollapsed: false" in open_fn
    assert "latestLeafInSubtree" in session


def test_refresh_left_history_respects_active_mode():
    actions = frontend_file("app/historyActions.js")
    refresh = actions.split("export async function refreshLeftHistory")[1].split(
        "export async function setLeftHistoryMode"
    )[0]
    assert "isMessagesHistoryMode" in refresh
    assert "loadMessageList" in refresh
    assert "refreshMessageTreePreservingExpansion" in refresh
