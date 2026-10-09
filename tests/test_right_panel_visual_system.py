"""Contrato visual del panel derecho: una sola gramática de instrumentos."""
from tests.frontend_source import frontend_markup, frontend_source

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "frontend" / "src" / "styles" / "style.css"


def _html() -> str:
    return frontend_markup()


def _right_html() -> str:
    html = _html()
    start = html.index('id="column-right"')
    end = html.index('id="app-status-bar"')
    return html[start:end]


def _css() -> str:
    return STYLE.read_text(encoding="utf-8")


def test_right_panel_defines_instrument_tokens():
    css = _css()
    block = css.split("Panel derecho: sistema de instrumentos")[-1].split(".column-right {")[1].split("}")[0]
    for token in (
        "--rp-space-1",
        "--rp-space-2",
        "--rp-space-3",
        "--rp-control-h",
        "--rp-title",
        "--rp-caption",
        "--rp-label",
        "--rp-hint",
        "--rp-pad-x",
    ):
        assert token in block, f"Falta token {token} en .column-right"


def test_right_panel_field_and_group_classes_exist():
    css = _css()
    assert ".column-right .panel-field-group" in css
    assert ".column-right .sidebar-option" in css
    assert ".column-right .pref-row.fluent-toggle-row" in css
    assert ".column-right .accordion-header" in css
    assert ".column-right .panel-section-title" in css


def test_right_panel_inputs_and_selects_use_translucent_background():
    css = _css()
    mix = "color-mix(in srgb, var(--bg-input, var(--input, var(--layer-alt))) 70%, transparent)"
    param_block = css.split(".column-right .param-control,")[1].split(".column-right select,")[0]
    assert mix in param_block
    assert "border-radius: var(--radius-md)" in param_block
    generic = css.split(
        ".column-right select,\n.column-right input:not([type=\"checkbox\"]):not([type=\"radio\"]),"
    )[1].split("}")[0]
    assert mix in generic
    assert "border-radius: var(--radius-md)" in generic
    assert "--radius-sm: 6px" in css
    assert "--radius-md: 10px" in css
    select_arrow = css.split(".column-right select.param-control,")[1].split("}")[0]
    assert "appearance: none" in select_arrow
    assert "stroke='%23c8c8c8'" in select_arrow
    assert "background-position: right 12px center" in select_arrow
    assert "padding-right: 32px" in select_arrow


def test_all_right_accordion_headers_have_title_and_caption():
    right = _right_html()
    headers = re.findall(
        r'<button type="button" class="accordion-header"[^>]*>[\s\S]*?</button>',
        right,
    )
    assert len(headers) >= 10
    for header in headers:
        assert "accordion-title" in header
        assert "accordion-caption" in header


def test_images_booleans_use_fluent_switch_rows():
    right = _right_html()
    images = right.split('id="tab-imagenes"')[1].split('id="tab-preferencias"')[0]
    for control_id in (
        "images-enabled",
        "images-use-chat-config",
        "images-visual-consistency",
        "images-reactor-enabled",
        "images-reactor-female-enabled",
        "images-reactor-male-enabled",
    ):
        chunk_start = images.index(f'id="{control_id}"')
        chunk = images[max(0, chunk_start - 400) : chunk_start + 120]
        assert "fluent-switch-input" in chunk, f"{control_id} debe ser fluent switch"
        assert "pref-row" in chunk, f"{control_id} debe ir en fila de instrumento"
    assert re.search(r'<input type="checkbox"(?![^>]*fluent-switch-input)', images) is None


def test_images_stacked_fields_use_param_option():
    right = _right_html()
    images = right.split('id="tab-imagenes"')[1].split('id="tab-preferencias"')[0]
    for control_id in (
        "images-prompt-provider",
        "images-prompt-model",
        "images-per-response",
        "images-forge-steps",
        "images-reactor-model",
        "images-scene-selection-strategy",
    ):
        around = images.split(f'id="{control_id}"')[0][-280:]
        assert "param-option" in around, f"{control_id} debe usar sidebar-option param-option"


def test_reactor_is_grouped_into_named_field_groups():
    right = _right_html()
    reactor = right.split('id="accordion-images-reactor"')[1].split('id="tab-preferencias"')[0]
    assert "panel-field-group" in reactor
    assert "reactor-group-gender" in reactor
    assert "reactor-group-source" in reactor
    assert "reactor-group-finish" in reactor


def test_right_panel_copy_is_sentence_case_spanish():
    right = _right_html()
    assert "-- Elegir regla --" not in right
    js = frontend_source()
    assert "-- Elegir regla --" not in js
    assert 'title="Aplicar perfil"' in right
    assert 'title="Aplicar perfil"' in right
    assert 'aria-label="Aplicar perfil"' in right
    assert 'title="Guardar"' in right
    assert 'title="Guardar como"' in right
    assert 'title="Eliminar perfil"' in right
    assert "Provider LLM prompts" not in right
    assert "Stop sequences" not in right
    assert "Proveedor de prompts" in right
    assert "Secuencias de parada" in right


def test_planner_rules_reuse_rules_section_pattern():
    right = _right_html()
    rules = right.split('data-accordion-section="images-planner-rules"')[1].split(
        'data-accordion-section="images-limits"'
    )[0]
    assert "accordion-title" in rules
    assert "accordion-caption" in rules
    assert "rules-add-existing" in rules
    assert "rules-create-block" in rules
    assert "panel-section-title" not in rules


def test_right_panel_accordion_scrolls_instead_of_clipping_open_sections():
    """Varias secciones is-open no pueden compartir flex:1 con overflow hidden."""
    css = _css()
    block = css.split("Panel derecho: sistema de instrumentos")[-1]
    list_rule = re.search(
        r"\.column-right \.sidebar-tab-panel\s*>\s*\.accordion-list\s*\{([^}]+)\}",
        block,
    )
    assert list_rule, "Falta override de .accordion-list en el panel derecho"
    assert "overflow-y: auto" in list_rule.group(1)
    open_rule = re.search(
        r"\.column-right \.sidebar-tab-panel\s*>\s*\.accordion-list\s*>\s*\.accordion-section\.is-open\s*\{([^}]+)\}",
        block,
    )
    assert open_rule, "Falta override de sección abierta"
    body = open_rule.group(1)
    assert "flex: 0 0 auto" in body
    assert "overflow: visible" in body
    assert ".accordion-section.is-open > .accordion-content" in block
    assert (
        ".column-right .sidebar-tab-panel > .accordion-list > .accordion-section > .accordion-content"
        not in block
    )


def test_accordion_init_keeps_one_open_section_per_list():
    js = frontend_source()
    init = js.split("function initAccordionState")[1].split("function initSidebarAccordion")[0]
    assert "getSiblingAccordionSections" in init
    assert "setAccordionSectionOpen(s, false)" in init or "setAccordionSectionOpen(section, false)" in init
