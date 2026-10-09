"""Tests del dominio model_contract: tipos, thinking, overlays y contrato vacío."""

import json

from app.services.model_contract import overlays as overlays_mod
from app.services.model_contract.models import (
    ModelCapabilities,
    ModelContract,
    ThinkingCapability,
    empty_model_contract,
)
from app.services.model_contract.overlays import load_overlays, save_overlays
from app.services.model_contract.resolve import resolve_model_contract
from app.services.model_contract.history_quirks import apply_history_quirks
from app.services.model_contract.thinking import normalize_think_value


def _clear_overlay_cache(provider: str | None = None) -> None:
    if provider is not None:
        overlays_mod._cache.pop(provider, None)
    else:
        overlays_mod._cache.clear()


def test_empty_model_contract_es_null_object():
    """Sin overlay: thinking none, sin recetas ni quirks, params vacíos."""
    contract = empty_model_contract("ollama", "llama3.2")
    assert isinstance(contract, ModelContract)
    assert contract.provider == "ollama"
    assert contract.model == "llama3.2"
    assert contract.capabilities.thinking.kind == "none"
    assert contract.capabilities.vision is False
    assert contract.capabilities.tools is False
    assert contract.recipes == ()
    assert contract.quirks == ()
    assert contract.params == {}


def test_thinking_boolean_vs_levels():
    """boolean y levels son kinds distintos; none no tiene values."""
    none = ThinkingCapability(kind="none")
    boolean = ThinkingCapability(kind="boolean", values=("false", "true"), can_disable=True)
    levels = ThinkingCapability(
        kind="levels",
        values=("low", "medium", "high"),
        can_disable=False,
        true_maps_to="medium",
        default="medium",
    )
    assert none.kind == "none"
    assert boolean.kind == "boolean"
    assert levels.kind == "levels"
    assert levels.can_disable is False
    assert levels.true_maps_to == "medium"


def test_normalize_think_none_no_envia():
    """kind none: no hay valor de think que enviar."""
    thinking = ThinkingCapability(kind="none")
    assert normalize_think_value(thinking, True) is None
    assert normalize_think_value(thinking, False) is None
    assert normalize_think_value(thinking, "max") is None


def test_normalize_think_boolean():
    thinking = ThinkingCapability(kind="boolean", can_disable=True)
    assert normalize_think_value(thinking, False) is False
    assert normalize_think_value(thinking, "false") is False
    assert normalize_think_value(thinking, True) is True
    assert normalize_think_value(thinking, "true") is True


def test_normalize_think_gpt_oss_coerce_false_a_true_maps_to():
    """can_disable false: think false/true se coaccionan a true_maps_to."""
    thinking = ThinkingCapability(
        kind="levels",
        values=("low", "medium", "high"),
        can_disable=False,
        true_maps_to="medium",
        default="medium",
    )
    assert normalize_think_value(thinking, False) == "medium"
    assert normalize_think_value(thinking, "false") == "medium"
    assert normalize_think_value(thinking, True) == "medium"
    assert normalize_think_value(thinking, "high") == "high"
    assert normalize_think_value(thinking, "low") == "low"


def test_normalize_think_deepseek_permite_off_y_max():
    thinking = ThinkingCapability(
        kind="levels",
        values=("false", "true", "max"),
        can_disable=True,
        default="true",
    )
    assert normalize_think_value(thinking, False) is False
    assert normalize_think_value(thinking, "false") is False
    assert normalize_think_value(thinking, True) is True
    assert normalize_think_value(thinking, "max") == "max"


def test_normalize_think_none_usa_default():
    thinking = ThinkingCapability(kind="boolean", can_disable=True, default=False)
    assert normalize_think_value(thinking, None) is False


def test_empty_contract_capabilities_defaults():
    caps = ModelCapabilities()
    assert caps.thinking.kind == "none"
    assert caps.structured_output is False


# ----- overlays -----


def test_load_overlays_archivo_inexistente():
    _clear_overlay_cache("provider_inexistente_xyz")
    assert load_overlays("provider_inexistente_xyz") == {}


def test_save_overlays_preserva_formato_compacto_de_entradas_intactas(tmp_path):
    """Al añadir un modelo no debe expandir arrays/objetos cortos de los demás."""
    existing = """{
  "modelo-a": {
    "capabilities": {
      "vision": false,
      "tools": true,
      "thinking": {
        "kind": "levels",
        "values": ["low", "high"],
        "can_disable": false,
        "default": "high"
      }
    },
    "params": {
      "temperature": { "default": 0.3 },
      "num_ctx": { "default": 32768, "max": 131072 }
    },
    "recipes": [
      { "id": "fast", "label": "Rápido", "params": { "think": "low", "temperature": 0.3 } }
    ],
    "quirks": []
  }
}
"""
    path = tmp_path / "ollama.json"
    path.write_text(existing, encoding="utf-8")
    data = json.loads(existing)
    data["modelo-b"] = {
        "capabilities": {
            "vision": False,
            "tools": True,
            "thinking": {"kind": "boolean", "can_disable": True, "default": True},
        },
        "params": {"num_ctx": {"max": 262144}},
        "recipes": [],
        "quirks": [],
    }
    save_overlays("ollama", data, path=path)
    text = path.read_text(encoding="utf-8")
    assert '"values": ["low", "high"]' in text
    assert '"temperature": { "default": 0.3 }' in text
    assert '{ "id": "fast", "label": "Rápido", "params": { "think": "low", "temperature": 0.3 } }' in text
    assert '"modelo-b"' in text
    assert json.loads(text)["modelo-b"]["params"]["num_ctx"]["max"] == 262144


def test_save_overlays_no_reescribe_entrada_igual(tmp_path):
    path = tmp_path / "ollama.json"
    existing = '{\n  "solo": { "quirks": [] }\n}\n'
    path.write_text(existing, encoding="utf-8")
    data = {"solo": {"quirks": []}, "nuevo": {"recipes": [], "quirks": []}}
    save_overlays("ollama", data, path=path)
    text = path.read_text(encoding="utf-8")
    assert '  "solo": { "quirks": [] }' in text
    assert json.loads(text)["nuevo"] == {"recipes": [], "quirks": []}


def test_save_overlays_preserva_estilo_expanded(tmp_path):
    existing = """{
  "modelo-a": {
    "capabilities": {
      "thinking": {
        "kind": "levels",
        "values": [
          "low",
          "high"
        ],
        "default": "high"
      }
    },
    "recipes": [],
    "quirks": []
  }
}
"""
    path = tmp_path / "openai.json"
    path.write_text(existing, encoding="utf-8")
    data = json.loads(existing)
    data["modelo-b"] = {"recipes": [], "quirks": []}
    save_overlays("openai", data, path=path)
    text = path.read_text(encoding="utf-8")
    assert '"values": [\n          "low",\n          "high"\n        ]' in text
    assert json.loads(text)["modelo-b"] == {"recipes": [], "quirks": []}


def test_load_overlays_json_invalido(tmp_path):
    _clear_overlay_cache("broken")
    (tmp_path / "broken.json").write_text("{ no json", encoding="utf-8")
    original = overlays_mod._OVERLAYS_DIR
    overlays_mod._OVERLAYS_DIR = tmp_path
    try:
        assert load_overlays("broken") == {}
    finally:
        overlays_mod._OVERLAYS_DIR = original
        _clear_overlay_cache("broken")


def test_load_overlays_ollama_cubre_cloud_instalados():
    _clear_overlay_cache("ollama")
    data = load_overlays("ollama")
    expected = {
        "gpt-oss:120b-cloud",
        "deepseek-v4-flash:cloud",
        "gemma4:31b-cloud",
        "glm-5.3-flash:cloud",
        "glm-5.3:cloud",
        "glm-5.2:cloud",
        "kimi-k2.6:cloud",
        "kimi-k3:cloud",
        "mistral-large-3:675b-cloud",
    }
    assert expected <= set(data)


def test_overlay_glm_53_flash_thinking_siempre_on_low_high_max():
    overlay = load_overlays("ollama")["glm-5.3-flash:cloud"]
    thinking = overlay["capabilities"]["thinking"]
    assert overlay["capabilities"]["vision"] is True
    assert thinking["can_disable"] is False
    assert thinking["true_maps_to"] == "high"
    assert list(thinking["values"]) == ["low", "high", "max"]
    assert thinking["default"] == "high"
    recipes = {r["id"]: r for r in overlay["recipes"]}
    assert recipes["fast"]["params"]["think"] == "low"
    assert recipes["hard"]["params"]["think"] == "max"


def test_overlay_glm_52_effort_high_max():
    overlay = load_overlays("ollama")["glm-5.2:cloud"]
    thinking = overlay["capabilities"]["thinking"]
    assert overlay["capabilities"]["vision"] is False
    assert thinking["can_disable"] is False
    assert list(thinking["values"]) == ["high", "max"]
    assert thinking["default"] == "high"
    recipes = {r["id"]: r for r in overlay["recipes"]}
    assert recipes["chat"]["params"]["think"] == "high"
    assert recipes["hard"]["params"]["think"] == "max"


def test_overlay_kimi_k3_thinking_siempre_on_default_max():
    overlay = load_overlays("ollama")["kimi-k3:cloud"]
    thinking = overlay["capabilities"]["thinking"]
    assert overlay["capabilities"]["vision"] is True
    assert thinking["can_disable"] is False
    assert list(thinking["values"]) == ["low", "high", "max"]
    assert thinking["default"] == "max"
    recipes = {r["id"]: r for r in overlay["recipes"]}
    assert recipes["research"]["params"]["think"] == "max"


def test_load_overlays_openai_cubre_flagships():
    _clear_overlay_cache("openai")
    data = load_overlays("openai")
    expected = {
        "gpt-6-astra",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
        "gpt-5.2",
        "gpt-4.1",
        "gpt-4o",
        "o3",
    }
    assert expected <= set(data)
    sol = data["gpt-5.6-sol"]
    assert sol["capabilities"]["vision"] is True
    assert sol["capabilities"]["thinking"]["can_disable"] is True
    assert sol["capabilities"]["thinking"]["default"] == "medium"
    assert sol["params"]["think"]["api_key"] == "reasoning_effort"
    astra = data["gpt-6-astra"]
    assert astra["capabilities"]["thinking"]["can_disable"] is False
    assert "none" not in astra["capabilities"]["thinking"]["values"]
    pro = data["gpt-5.4-pro"]
    assert pro["capabilities"]["thinking"]["can_disable"] is False
    assert list(pro["capabilities"]["thinking"]["values"]) == ["medium", "high", "xhigh"]
    assert pro["capabilities"]["thinking"]["default"] == "medium"
    assert data["gpt-4o"]["capabilities"]["thinking"]["kind"] == "none"


def test_load_overlays_mancer_cubre_catalogo_conocido():
    _clear_overlay_cache("mancer")
    data = load_overlays("mancer")
    expected = {
        "mythomax",
        "mytholite",
        "weaver",
        "remm-slerp",
        "magnum-72b-v4",
        "glm-4.7",
        "danspe-v1-3-0-12b",
        "danspe-v1-3-0-24b",
    }
    assert expected <= set(data)
    assert data["glm-4.7"]["capabilities"]["tools"] is True
    assert data["mythomax"]["capabilities"]["tools"] is False
    assert data["mythomax"]["capabilities"]["thinking"]["kind"] == "none"


def test_load_overlays_abliteration_cubre_tres_modelos():
    _clear_overlay_cache("abliteration")
    data = load_overlays("abliteration")
    assert {
        "abliterated-model",
        "abliterated-model-large",
        "abliterated-model-large-v2",
    } <= set(data)
    base = data["abliterated-model"]
    assert base["capabilities"]["vision"] is True
    assert base["capabilities"]["thinking"]["can_disable"] is True
    assert base["params"]["think"]["api_key"] == "reasoning_effort"
    large_v2 = data["abliterated-model-large-v2"]
    assert large_v2["capabilities"]["vision"] is False
    assert large_v2["capabilities"]["thinking"]["can_disable"] is False
    assert large_v2["capabilities"]["thinking"]["default"] == "max"


def test_resolve_openai_think_usa_reasoning_effort():
    contract = resolve_model_contract("openai", "gpt-5.6-sol")
    assert contract.params["think"]["api_key"] == "reasoning_effort"
    assert contract.capabilities.thinking.kind == "levels"
    assert contract.capabilities.vision is True
    assert "none" in contract.capabilities.thinking.values


def test_resolve_abliteration_large_v2_no_se_apaga():
    contract = resolve_model_contract("abliteration", "abliterated-model-large-v2")
    assert contract.capabilities.thinking.can_disable is False
    assert contract.capabilities.vision is False
    assert contract.params["think"]["api_key"] == "reasoning_effort"


def test_resolve_mistral_sin_thinking_con_recetas():
    contract = resolve_model_contract("ollama", "mistral-large-3:675b-cloud")
    assert contract.capabilities.thinking.kind == "none"
    assert contract.capabilities.vision is True
    assert "think" not in contract.params
    assert contract.params["num_ctx"]["max"] == 262144
    assert contract.params["temperature"]["default"] == 0.3
    assert {r.id for r in contract.recipes} >= {"enterprise", "docs"}


def test_resolve_gemma_sampling_oficial():
    contract = resolve_model_contract("ollama", "gemma4:31b-cloud")
    assert contract.capabilities.vision is True
    assert contract.capabilities.thinking.kind == "levels"
    assert contract.params["temperature"]["default"] == 1.0
    assert contract.params["top_p"]["default"] == 0.95
    assert contract.params["top_k"]["default"] == 64
    assert "omit_prior_thinking" in contract.quirks


def test_overlay_gpt_oss_es_sparse_y_thinking_no_off():
    overlay = load_overlays("ollama")["gpt-oss:120b-cloud"]
    thinking = overlay["capabilities"]["thinking"]
    assert thinking["can_disable"] is False
    assert thinking["true_maps_to"] == "medium"
    assert list(thinking["values"]) == ["low", "medium", "high"]
    assert overlay["params"]["num_ctx"]["max"] == 131072
    assert overlay["params"]["num_ctx"]["default"] != overlay["params"]["num_ctx"]["max"]
    assert "api_key" not in overlay["params"].get("temperature", {})
    assert "top_k" not in overlay["params"]
    recipes = {r["id"]: r for r in overlay["recipes"]}
    assert "fast" in recipes and "hard" in recipes


def test_overlay_deepseek_es_sparse_con_max_y_disable():
    overlay = load_overlays("ollama")["deepseek-v4-flash:cloud"]
    thinking = overlay["capabilities"]["thinking"]
    assert thinking["can_disable"] is True
    assert "max" in thinking["values"]
    assert overlay["params"]["num_ctx"]["max"] == 1048576
    assert overlay["params"]["num_ctx"]["default"] == 32768
    recipes = {r["id"]: r for r in overlay["recipes"]}
    assert recipes["fast"]["params"]["think"] is False
    assert recipes["hard"]["params"]["think"] == "max"
    assert "coding" in recipes


# ----- resolve / merge -----


def test_resolve_sin_overlay_es_null_object_con_params_de_proveedor():
    contract = resolve_model_contract("ollama", "modelo-sin-overlay-xyz")
    assert contract.capabilities.thinking.kind == "none"
    assert contract.recipes == ()
    assert "think" not in contract.params
    assert contract.params["temperature"]["api_key"] == "options.temperature"
    assert contract.params["num_ctx"]["max"] == 131072


def test_resolve_show_thinking_sin_overlay_es_boolean_no_inventa_niveles():
    show = {"capabilities": ["completion", "thinking", "vision", "tools"]}
    contract = resolve_model_contract("ollama", "otro-modelo", show=show)
    assert contract.capabilities.thinking.kind == "boolean"
    assert contract.capabilities.thinking.values == ()
    assert contract.capabilities.vision is True
    assert contract.capabilities.tools is True
    assert "think" in contract.params
    assert contract.params["think"]["api_key"] == "think"
    assert contract.params["think"]["type"] == "boolean"


def test_resolve_show_none_no_lanza():
    contract = resolve_model_contract("ollama", "modelo-sin-overlay-xyz", show=None)
    assert contract.capabilities.thinking.kind == "none"


def test_resolve_show_invalido_no_lanza():
    contract = resolve_model_contract("ollama", "modelo-sin-overlay-xyz", show=["no-dict"])
    assert contract.capabilities.thinking.kind == "none"


def test_resolve_gpt_oss_antagonista():
    contract = resolve_model_contract("ollama", "gpt-oss:120b-cloud")
    th = contract.capabilities.thinking
    assert th.kind == "levels"
    assert th.can_disable is False
    assert th.true_maps_to == "medium"
    assert th.values == ("low", "medium", "high")
    assert contract.capabilities.vision is False
    assert contract.params["num_ctx"]["max"] == 131072
    assert contract.params["num_ctx"]["default"] == 32768
    assert contract.params["temperature"]["api_key"] == "options.temperature"
    assert contract.params["temperature"]["default"] == 0.4
    assert contract.params["think"]["api_key"] == "think"
    recipes = {r.id: r for r in contract.recipes}
    assert recipes["fast"].params["think"] == "low"
    assert recipes["hard"].params["think"] == "high"


def test_resolve_deepseek_antagonista():
    contract = resolve_model_contract("ollama", "deepseek-v4-flash:cloud")
    th = contract.capabilities.thinking
    assert th.kind == "levels"
    assert th.can_disable is True
    assert "max" in th.values
    assert contract.capabilities.vision is False
    assert contract.params["num_ctx"]["max"] == 1048576
    assert contract.params["num_ctx"]["default"] == 32768
    assert contract.params["temperature"]["api_key"] == "options.temperature"
    assert contract.params["think"]["api_key"] == "think"
    recipes = {r.id: r for r in contract.recipes}
    assert recipes["fast"].params["think"] is False
    assert recipes["hard"].params["think"] == "max"


def test_resolve_overlay_gana_sobre_show_en_thinking():
    """Show no inventa niveles si el overlay ya define thinking."""
    show = {"capabilities": ["thinking", "vision"]}
    contract = resolve_model_contract("ollama", "gpt-oss:120b-cloud", show=show)
    assert contract.capabilities.thinking.kind == "levels"
    assert contract.capabilities.thinking.can_disable is False
    assert contract.capabilities.vision is False


def test_resolve_live_context_rellena_max_si_overlay_no_lo_trae():
    show = {
        "capabilities": ["completion"],
        "model_info": {"llama.context_length": 8192},
    }
    contract = resolve_model_contract("ollama", "modelo-sin-overlay-xyz", show=show)
    assert contract.params["num_ctx"]["max"] == 8192


def _history_with_thought() -> list[dict]:
    return [
        {"role": "system", "content": "Sé breve.\n<think>no toques el system</think>"},
        {"role": "user", "content": "¿2+2?"},
        {
            "role": "assistant",
            "content": "<think>sumo 2 y 2</think>\n\n4",
            "thinking": "sumo 2 y 2",
        },
        {"role": "user", "content": "¿y 3+3?"},
    ]


def test_omit_prior_thinking_no_aplica_sin_quirk():
    """Sin omit_prior_thinking el historial se reenvía tal cual (incl. thought)."""
    original = _history_with_thought()
    out = apply_history_quirks(original, ())
    assert out == original
    assert out[2]["thinking"] == "sumo 2 y 2"
    assert "<think>" in out[2]["content"]


def test_omit_prior_thinking_quita_campo_thinking_y_bloques_en_assistant():
    """Gemma: no reenviar thought de turnos previos (campo API + tags en content)."""
    out = apply_history_quirks(_history_with_thought(), ("omit_prior_thinking",))
    assistant = out[2]
    assert "thinking" not in assistant
    assert "thought" not in assistant
    assert assistant["content"] == "4"
    assert "<think>" not in assistant["content"]


def test_omit_prior_thinking_respeta_system_y_user():
    """El quirk solo limpia turnos assistant; system/user no se reescriben."""
    out = apply_history_quirks(_history_with_thought(), ("omit_prior_thinking",))
    assert out[0]["content"] == "Sé breve.\n<think>no toques el system</think>"
    assert out[1]["content"] == "¿2+2?"
    assert out[3]["content"] == "¿y 3+3?"


def test_omit_prior_thinking_no_muta_entrada():
    original = _history_with_thought()
    snapshot = [dict(m) for m in original]
    apply_history_quirks(original, ("omit_prior_thinking",))
    assert original == snapshot


def test_omit_prior_thinking_strips_thought_tag_y_deja_respuesta():
    messages = [
        {
            "role": "assistant",
            "content": "<thought>razonamiento largo</thought>\nRespuesta útil.",
        }
    ]
    out = apply_history_quirks(messages, ("omit_prior_thinking",))
    assert out[0]["content"] == "Respuesta útil."


def test_omit_prior_thinking_ignora_quirks_ajenos():
    original = _history_with_thought()
    out = apply_history_quirks(original, ("image_before_text",))
    assert "<think>" in out[2]["content"]
    assert out[2]["thinking"] == "sumo 2 y 2"


# ----- overlays proveedor NaN (reasoning_effort) -----


def test_nan_overlay_glm_reasoning_effort_por_niveles():
    """glm5.3-flash expone reasoning_effort (low/medium/high/max) mapeado desde think."""
    _clear_overlay_cache("nan")
    contract = resolve_model_contract("nan", "glm5.3-flash")
    th = contract.capabilities.thinking
    assert th.kind == "levels"
    assert th.values == ("low", "medium", "high", "max")
    assert th.can_disable is False
    assert th.true_maps_to == "high"
    assert contract.params["think"]["api_key"] == "reasoning_effort"
    assert contract.params["think"]["default"] == "high"


def test_nan_overlay_deepseek_reasoning_no_ajustable():
    """deepseek-v4-flash decide su razonamiento: reasoning_effort no tiene efecto.

    El contrato lo declara `kind: none` para ocultar el control (no enviar un
    parámetro que la API acepta pero ignora) y sube el suelo de max_tokens a 16384:
    la API eleva a 16384 cualquier valor inferior para que quepa el trazo.
    """
    _clear_overlay_cache("nan")
    contract = resolve_model_contract("nan", "deepseek-v4-flash")
    assert contract.capabilities.thinking.kind == "none"
    assert "think" not in contract.params
    assert contract.params["max_tokens"]["min"] == 16384
    assert contract.capabilities.structured_output is True


def test_nan_overlay_qwen38_y_mimo_reasoning_no_ajustable():
    """qwen3.8-flash y mimo-v2.6-flash gestionan su profundidad: sin control de esfuerzo."""
    _clear_overlay_cache("nan")
    for model in ("qwen3.8-flash", "mimo-v2.6-flash"):
        contract = resolve_model_contract("nan", model)
        assert contract.capabilities.thinking.kind == "none"
        assert "think" not in contract.params


def test_nan_overlay_gemma4_permite_desactivar_reasoning():
    """gemma4 acepta none/minimal/... y permite desactivar el razonamiento."""
    _clear_overlay_cache("nan")
    contract = resolve_model_contract("nan", "gemma4")
    th = contract.capabilities.thinking
    assert th.can_disable is True
    assert "none" in th.values
    assert normalize_think_value(th, "none") == "none"
    assert contract.params["think"]["api_key"] == "reasoning_effort"


def test_nan_overlay_gemma4_y_qwen36_presupuesto_razonamiento_y_sampling():
    """El razonamiento cuenta en max_tokens y llega a 32768; sampling documentado.

    gemma4/qwen3.6 alcanzan un budget de razonamiento de 32768 tokens en `max`,
    así que el default de max_tokens debe cubrirlo. Docs NaN: temp=0.6, top_p=0.95.
    """
    _clear_overlay_cache("nan")
    for model in ("gemma4", "qwen3.6"):
        contract = resolve_model_contract("nan", model)
        assert contract.params["max_tokens"]["default"] >= 32768
        assert contract.params["temperature"]["default"] == 0.6
        assert contract.params["top_p"]["default"] == 0.95
        recipe_ids = {r.id for r in contract.recipes}
        assert {"fast", "hard"} <= recipe_ids


def test_nan_overlay_recetas_recortan_o_ajustan_esfuerzo():
    """Los modelos con niveles exponen recetas que fijan think."""
    _clear_overlay_cache("nan")
    contract = resolve_model_contract("nan", "glm5.3")
    by_id = {r.id: r for r in contract.recipes}
    assert by_id["fast"].params["think"] == "low"
    assert by_id["hard"].params["think"] == "max"
