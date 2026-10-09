"""Texto base de la interfaz: escala global; los tamaños de sección son relativos."""
from tests.frontend_source import frontend_markup, frontend_source

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = ROOT / "frontend" / "src" / "styles" / "style.css"

PX_FONT_SIZE = re.compile(r"font-size:\s*[^;]*\d+(?:\.\d+)?px")
PX_TYPE_TOKEN = re.compile(
    r"--rp-(?:title|caption|label|body|hint):\s*calc\(\s*\d+(?:\.\d+)?px"
)


def _interfaz() -> str:
    html = frontend_markup()
    return html.split('data-accordion-section="prefs-interfaz"')[1].split("sidebar-footer")[0]


def test_base_font_control_is_first_interfaz_row():
    interfaz = _interfaz()
    assert 'id="pref-font-base-decrease"' in interfaz
    assert 'id="pref-font-base-increase"' in interfaz
    assert 'id="pref-font-base-value"' in interfaz
    assert "Texto base" in interfaz
    base = interfaz.index('id="pref-font-base-value"')
    conv = interfaz.index('id="pref-font-value"')
    left = interfaz.index('id="pref-font-left-value"')
    right = interfaz.index('id="pref-font-right-value"')
    images = interfaz.index('id="pref-image-value"')
    assert base < conv < left < right < images


def test_section_font_hints_are_relative_to_base():
    interfaz = _interfaz()
    assert "respecto al tamaño base" in interfaz
    conv_hint_pos = interfaz.index("respecto al tamaño base")
    assert interfaz.index("Texto de la conversación") < conv_hint_pos


def test_head_script_applies_base_font_scale_before_paint():
    head = frontend_markup().split("</head>")[0]
    assert "uiBaseFontScale" in head
    assert "--ui-base-font-scale" in head
    assert "baseFs <= 5" in head
    assert "leftFs <= 5" in head
    assert "rightFs <= 5" in head


def test_js_defines_base_font_scale_as_independent_multiplier():
    js = frontend_source()
    assert "uiBaseFontScale" in js
    assert "--ui-base-font-scale" in js
    assert "initUiBaseFontScale" in js
    assert "setUiBaseFontScale" in js
    assert "pref-font-base-decrease" in js
    assert "pref-font-base-increase" in js
    assert "pref-font-base-value" in js
    assert "UI_BASE_FONT_SCALE_MIN = 0.05" in js
    assert "UI_BASE_FONT_SCALE_MAX = 5" in js
    assert "UI_BASE_FONT_SCALE_STEP = 0.05" in js
    assert "UI_BASE_FONT_SCALE_DEFAULT = 1" in js
    assert "SIDEBAR_FONT_SCALE_MAX = 5" in js
    assert "SIDEBAR_FONT_SCALE_MIN = 0.05" in js
    assert "FONT_SIZE_MAX = 5" in js
    assert "IMAGE_SIZE_MAX = 1" in js
    assert "IMAGE_SIZE_MIN = 0.05" in js
    assert "IMAGE_SIZE_STEP = 0.05" in js


def test_css_html_font_size_uses_base_scale_variable():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "--ui-base-font-scale: 1;" in css
    html_rule = css.split("html {")[1].split("}")[0]
    assert "calc(100% * var(--ui-base-font-scale, 1))" in html_rule


def test_font_sizes_use_rem_so_html_scale_reaches_the_whole_ui():
    css = STYLE_CSS.read_text(encoding="utf-8")
    leftover = PX_FONT_SIZE.findall(css)
    assert leftover == [], leftover
    leftover_tokens = PX_TYPE_TOKEN.findall(css)
    assert leftover_tokens == [], leftover_tokens
    assert "calc(0.6875rem * var(--sidebar-left-font-scale, 1))" in css
    assert "calc(0.8125rem * var(--sidebar-right-font-scale, 1))" in css


def test_conversation_image_size_stays_independent_of_base_font():
    js = frontend_source()
    start = js.index("function applyConversationImageSize")
    fn = js[start : js.index("function ", start + 1)]
    assert "--ui-base-font-scale" not in fn
    assert "--chat-image-max-width" in fn


def test_index_serves_base_font_control(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="pref-font-base-value"' in frontend_markup()
    assert "Texto base" in frontend_markup()
