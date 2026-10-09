"""Contrato del panel izquierdo: modos mensajes/conversaciones y orden persistido."""
from pathlib import Path

from tests.frontend_source import frontend_file, frontend_markup, frontend_source

ROOT = Path(__file__).resolve().parents[1]
APP_JSX = ROOT / "frontend" / "src" / "App.jsx"


def _column_left_app() -> str:
    html = APP_JSX.read_text(encoding="utf-8")
    start = html.index('id="column-left"')
    return html[start : html.index("</aside>", start)]


def test_left_panel_has_mode_switch_and_messages_list():
    left = _column_left_app()
    assert "<ConversationsList" in left
    assert 'id="btn-new-chat"' in left
    lists = frontend_file("ui/history/HistoryLists.jsx")
    assert "HistoryModeSwitch" in lists
    assert "MessagesList" in lists
    assert "ConversationsTreeList" in lists


def test_sort_options_exist_for_both_modes():
    js = frontend_file("store/history.js")
    assert "CONV_SORT_OPTIONS" in js
    assert "MESSAGE_SORT_OPTIONS" in js
    assert '{ value: "activity"' in js
    assert '{ value: "created_at"' in js
    assert '{ value: "date"' in js
    assert '{ value: "photos"' in js


def test_message_sort_direction_is_exposed():
    js = frontend_file("store/history.js")
    assert "MESSAGE_SORT_DIRECTION_ASC" in js
    assert "LEFT_HISTORY_SORT_DIRECTION_KEY" in js
    assert "persistMessageSortDirection" in js
    assert "readStoredMessageSortDirection" in js
    actions = frontend_file("app/historyActions.js")
    assert "onMessageSortDirectionToggle" in actions
    assert 'params.set("direction"' in actions
    lists = frontend_file("ui/history/HistoryLists.jsx")
    assert 'id="message-sort-direction"' in lists


def test_left_history_mode_defaults_to_messages():
    store = frontend_file("store/history.js")
    assert "LEFT_HISTORY_MODE_MESSAGES" in store
    assert "isMessagesHistoryMode" in store
    assert "isConversationsHistoryMode" in store
    assert "isTreeHistoryMode" in store


def test_load_conversations_helper_still_uses_conversation_sort():
    load_conv = frontend_file("app/historyActions.js").split("export async function loadConversations")[1].split(
        "export async function loadDeleted"
    )[0]
    api = frontend_file("api/conversations.js")
    assert "/conversations?sort=" in api
    assert "readStoredConversationSort" in load_conv


def test_message_tree_roots_client_exists():
    api = frontend_file("api/messageTree.js")
    assert "listMessageTreeRoots" in api
    assert "listMessageTreeChildren" in api
    assert frontend_markup()  # SPA servida


def test_left_history_sort_is_react_not_dom_sync():
    sync = frontend_file("ui/layout/StoreDomSync.jsx")
    assert "left-history-sort" not in sync
    assert frontend_source("ui/history/HistoryLists.jsx")
