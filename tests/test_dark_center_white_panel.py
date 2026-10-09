"""En dark, el panel central de conversación es blanco con tokens light."""
from pathlib import Path
import re

STYLE_CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "styles" / "style.css"


def test_dark_center_column_is_white_with_light_tokens():
    css = STYLE_CSS.read_text(encoding="utf-8")
    matches = list(
        re.finditer(
            r'\[data-theme="dark"\] \.column-center(?:\s*>\s*\.chat-column|,\s*\[data-theme="dark"\] \.column-center\.chat-area\.main-pane)?\s*\{',
            css,
        )
    )
    assert matches, "Falta bloque de column-center en dark"
    # Usar el último bloque amplio (tokens scoped)
    last = None
    for m in matches:
        start = m.end()
        depth = 1
        i = start
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        body = css[start : i - 1]
        if "--bg-message-user" in body or "color-scheme: light" in body:
            last = body
    assert last is not None, "Falta el bloque de tokens light en column-center dark"
    assert "color-scheme: light" in last
    assert "#ffffff" in last
    assert "--text-primary: #1a1a1a" in last
    assert "--bg-message-user: #c5daf0" in last
    assert "--bg-message-assistant: #e4ebf3" in last
    assert "--accent: #0078d4" in last


def test_dark_center_messages_use_win11_steel_mica():
    css = STYLE_CSS.read_text(encoding="utf-8")
    user_idx = css.index('[data-theme="dark"] .column-center .message-bubble.user')
    user_block = css[user_idx : user_idx + 350]
    assert "background: #c5daf0" in user_block
    asst_idx = css.index('[data-theme="dark"] .column-center .message-bubble.assistant')
    asst_block = css[asst_idx : asst_idx + 350]
    assert "background: #e4ebf3" in asst_block
    assert "#f3f3f3" not in asst_block.split("}")[0]

def test_dark_center_header_and_composer_follow_light_surface():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "[data-theme=\"dark\"] .column-center .chat-panel-header" in css
    header_idx = css.index('[data-theme="dark"] .column-center .chat-panel-header')
    header_block = css[header_idx : header_idx + 400]
    # Isla flotante: la cabecera va sobre la superficie clara, sin banda propia.
    assert "--chat-header-bg: transparent" in header_block
    assert "background: transparent" in header_block
    assert "[data-theme=\"dark\"] .column-center .composer-panel" in css
    assert "[data-theme=\"dark\"] .column-center .message-bubble.user" in css
    assert "[data-theme=\"dark\"] .column-center #btn-send.composer-send-btn" in css


def test_chat_panel_header_uses_surface_not_accent_wash():
    css = STYLE_CSS.read_text(encoding="utf-8")
    start = css.index(".chat-panel-header {")
    body = css[start : start + 500]
    assert "--chat-header-bg: var(--layer-alt)" in body
    assert "color-mix(in srgb, var(--accent)" not in body.split("}")[0]
