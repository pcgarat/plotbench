"""Tests del generador de overlays (stub, merge, dry-run, path, multi-proveedor)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.model_contract.facts import ModelFacts, facts_from_catalog
from app.tools.overlay_generator.cli import (
    OverlayGeneratorError,
    main,
    process_one_model,
    run_batch,
)
from app.tools.overlay_generator.proposal import (
    proposal_filename,
    render_proposal_markdown,
    sanitize_model_id_for_path,
)
from app.tools.overlay_generator.stub import merge_overlay, stub_from_facts, stub_from_show


def _facts_thinking_ctx(**overrides) -> ModelFacts:
    base = ModelFacts(vision=True, tools=True, thinking_flag=True, context_length=131072)
    return ModelFacts(
        vision=overrides.get("vision", base.vision),
        tools=overrides.get("tools", base.tools),
        thinking_flag=overrides.get("thinking_flag", base.thinking_flag),
        context_length=overrides.get("context_length", base.context_length),
    )


def _show_thinking_ctx(**extra):
    base = {
        "capabilities": ["completion", "thinking", "vision", "tools"],
        "model_info": {"llama.context_length": 131072},
    }
    base.update(extra)
    return base


def test_stub_from_facts_solo_campos_fiables():
    stub = stub_from_facts(_facts_thinking_ctx())
    assert stub["capabilities"]["vision"] is True
    assert stub["capabilities"]["tools"] is True
    assert stub["capabilities"]["thinking"] == {
        "kind": "boolean",
        "can_disable": True,
        "default": True,
    }
    assert stub["params"]["num_ctx"]["max"] == 131072
    assert stub["recipes"] == []
    assert stub["quirks"] == []
    assert "structured_output" not in stub["capabilities"]
    assert "true_maps_to" not in stub["capabilities"]["thinking"]
    assert "temperature" not in stub["params"]


def test_stub_from_facts_sin_thinking_ni_ctx():
    stub = stub_from_facts(ModelFacts())
    assert stub["capabilities"]["thinking"] == {"kind": "none"}
    assert stub["capabilities"]["vision"] is False
    assert stub["capabilities"]["tools"] is False
    assert stub["params"] == {}


def test_stub_from_show_sigue_funcionando():
    """El helper de compatibilidad mantiene el comportamiento histórico."""
    stub = stub_from_show("foo:bar", _show_thinking_ctx())
    assert stub["capabilities"]["vision"] is True
    assert stub["params"]["num_ctx"]["max"] == 131072


def test_stub_from_show_ctx_por_arquitectura_prefijada():
    """Nemotron y otras familias exponen {arch}.context_length, no llama.context_length."""
    stub = stub_from_show(
        "nemotron-3-super:cloud",
        {
            "capabilities": ["completion", "thinking", "tools"],
            "model_info": {"nemotron_h_moe.context_length": 262144},
        },
    )
    assert stub["params"]["num_ctx"]["max"] == 262144
    assert stub["capabilities"]["thinking"]["kind"] == "boolean"


def test_stub_from_show_sin_thinking_ni_ctx():
    stub = stub_from_show("m", {"capabilities": ["completion"]})
    assert stub["capabilities"]["thinking"] == {"kind": "none"}
    assert stub["capabilities"]["vision"] is False
    assert stub["capabilities"]["tools"] is False
    assert stub["params"] == {}


def test_stub_tools_via_tool_use_flag():
    stub = stub_from_show("m", {"capabilities": ["tool_use"]})
    assert stub["capabilities"]["tools"] is True


def test_facts_from_catalog_declara_booleanos():
    """NaN no tiene show: los hechos salen del catálogo curado explicito."""
    facts = facts_from_catalog(
        {"vision": True, "tools": True, "thinking_flag": False, "context_length": 1_048_576}
    )
    assert facts.vision is True
    assert facts.tools is True
    assert facts.thinking_flag is False
    assert facts.context_length == 1_048_576
    assert facts_from_catalog(None) == ModelFacts()


def test_merge_sin_existing_devuelve_stub():
    stub = stub_from_facts(_facts_thinking_ctx())
    merged = merge_overlay(None, stub)
    assert merged == stub
    merged["recipes"].append({"id": "x"})
    assert stub["recipes"] == []


def test_merge_sobre_vacio_rellena_fiables():
    stub = stub_from_facts(_facts_thinking_ctx())
    merged = merge_overlay({}, stub)
    assert merged["capabilities"]["vision"] is True
    assert merged["capabilities"]["thinking"]["kind"] == "boolean"
    assert merged["params"]["num_ctx"]["max"] == 131072
    assert merged["recipes"] == []


def test_merge_preserve_recipes_quirks_levels():
    existing = {
        "capabilities": {
            "vision": False,
            "tools": True,
            "thinking": {
                "kind": "levels",
                "values": ["low", "medium", "high"],
                "can_disable": False,
                "true_maps_to": "medium",
                "default": "medium",
            },
        },
        "params": {"num_ctx": {"default": 32768, "max": 131072}, "temperature": {"default": 0.4}},
        "recipes": [{"id": "fast", "label": "Rápido", "params": {"think": "low"}}],
        "quirks": ["omit_prior_thinking"],
    }
    stub = stub_from_facts(
        ModelFacts(vision=True, tools=True, thinking_flag=True, context_length=999)
    )
    merged = merge_overlay(existing, stub)
    assert merged["recipes"] == existing["recipes"]
    assert merged["quirks"] == ["omit_prior_thinking"]
    assert merged["capabilities"]["thinking"]["kind"] == "levels"
    assert merged["capabilities"]["thinking"]["true_maps_to"] == "medium"
    assert merged["capabilities"]["vision"] is False
    assert merged["params"]["num_ctx"]["max"] == 131072
    assert merged["params"]["temperature"]["default"] == 0.4


def test_merge_rellena_solo_huecos_vision_y_num_ctx_max():
    existing = {
        "capabilities": {"thinking": {"kind": "none"}},
        "params": {"num_ctx": {"default": 4096}},
        "recipes": [],
        "quirks": [],
    }
    stub = stub_from_facts(_facts_thinking_ctx())
    merged = merge_overlay(existing, stub)
    assert merged["capabilities"]["vision"] is True
    assert merged["capabilities"]["tools"] is True
    assert merged["capabilities"]["thinking"]["kind"] == "none"
    assert merged["params"]["num_ctx"]["default"] == 4096
    assert merged["params"]["num_ctx"]["max"] == 131072


def test_sanitize_model_id_for_path():
    assert sanitize_model_id_for_path("gemma4:31b-cloud") == "gemma4-31b-cloud"
    assert sanitize_model_id_for_path("a/b:c") == "a-b-c"
    name = proposal_filename("gemma4:31b-cloud", when=date(2026, 9, 2))
    assert name == "gemma4-31b-cloud_2026-09-02.md"


def test_render_proposal_es_draft():
    stub = stub_from_facts(_facts_thinking_ctx())
    md = render_proposal_markdown("foo:bar", stub, wrote_overlay=False, when=date(2026, 9, 2))
    assert md.startswith("Última modificación: 2026-09-02")
    assert "DRAFT" in md
    assert "no copiar" in md.lower()
    assert "foo:bar" in md


def test_dry_run_no_escribe_archivos(tmp_path: Path):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"
    proposals.mkdir()

    result = process_one_model(
        "nuevo:modelo",
        provider="ollama",
        write=False,
        facts_fn=lambda _m: _facts_thinking_ctx(),
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    assert result["wrote_overlay"] is False
    assert result["wrote_proposal"] is False
    assert json.loads(overlay_file.read_text(encoding="utf-8")) == {}
    assert list(proposals.iterdir()) == []
    assert "nuevo-modelo" in result["proposal_path"]


def test_write_persiste_overlay_y_proposal(tmp_path: Path):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"

    result = process_one_model(
        "nuevo:modelo",
        provider="ollama",
        write=True,
        facts_fn=lambda _m: _facts_thinking_ctx(),
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    assert result["wrote_overlay"] is True
    data = json.loads(overlay_file.read_text(encoding="utf-8"))
    assert "nuevo:modelo" in data
    assert data["nuevo:modelo"]["capabilities"]["vision"] is True
    assert data["nuevo:modelo"]["recipes"] == []
    written = list(proposals.glob("*.md"))
    assert len(written) == 1
    assert "DRAFT" in written[0].read_text(encoding="utf-8")


def test_write_sobre_curado_no_borra_recipes(tmp_path: Path):
    curated = {
        "gemma4:31b-cloud": {
            "capabilities": {
                "vision": True,
                "tools": True,
                "thinking": {
                    "kind": "levels",
                    "values": ["false", "true", "low", "medium", "high", "max"],
                    "can_disable": True,
                    "default": True,
                },
            },
            "params": {"num_ctx": {"default": 32768, "max": 262144}},
            "recipes": [{"id": "chat", "label": "Chat", "params": {"think": True}}],
            "quirks": ["omit_prior_thinking", "image_before_text"],
        }
    }
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text(json.dumps(curated), encoding="utf-8")
    proposals = tmp_path / "proposals"

    process_one_model(
        "gemma4:31b-cloud",
        provider="ollama",
        write=True,
        facts_fn=lambda _m: _facts_thinking_ctx(),
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    data = json.loads(overlay_file.read_text(encoding="utf-8"))
    entry = data["gemma4:31b-cloud"]
    assert entry["recipes"][0]["id"] == "chat"
    assert entry["quirks"] == ["omit_prior_thinking", "image_before_text"]
    assert entry["capabilities"]["thinking"]["kind"] == "levels"


def test_write_proveedor_nan_usa_facts_del_catalogo(tmp_path: Path):
    """El generador soporta nan: escribe en el overlay del proveedor correcto."""
    overlay_file = tmp_path / "nan.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"

    def facts_fn(_model: str) -> ModelFacts:
        return facts_from_catalog(
            {"vision": True, "tools": True, "thinking_flag": False, "context_length": 262_144}
        )

    process_one_model(
        "gemma4",
        provider="nan",
        write=True,
        facts_fn=facts_fn,
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    data = json.loads(overlay_file.read_text(encoding="utf-8"))
    assert data["gemma4"]["capabilities"]["vision"] is True
    assert data["gemma4"]["params"]["num_ctx"]["max"] == 262_144
    proposal = next(proposals.glob("*.md")).read_text(encoding="utf-8")
    assert "config/model_overlays/nan.json" in proposal


def test_facts_falla_exit_sin_escritura(tmp_path: Path):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"
    proposals.mkdir()

    with pytest.raises(OverlayGeneratorError, match="hechos"):
        process_one_model(
            "missing",
            provider="ollama",
            write=True,
            facts_fn=lambda _m: None,
            overlay_file=overlay_file,
            proposals_dir=proposals,
        )
    assert json.loads(overlay_file.read_text(encoding="utf-8")) == {}
    assert list(proposals.iterdir()) == []


def test_batch_missing_dry_run(tmp_path: Path):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text(json.dumps({"ya:existe": {"recipes": []}}), encoding="utf-8")
    proposals = tmp_path / "proposals"
    proposals.mkdir()

    results = run_batch(
        provider="ollama",
        write=False,
        missing_only=True,
        facts_fn=lambda _m: _facts_thinking_ctx(),
        list_fn=lambda: ["ya:existe", "falta:uno"],
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    assert len(results) == 1
    assert results[0]["model_id"] == "falta:uno"
    assert json.loads(overlay_file.read_text(encoding="utf-8")) == {"ya:existe": {"recipes": []}}
    assert list(proposals.iterdir()) == []


def test_batch_best_effort_un_fallo(tmp_path: Path, capsys):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"

    def facts_fn(model_id: str):
        if model_id == "malo":
            return None
        return _facts_thinking_ctx()

    results = run_batch(
        provider="ollama",
        write=True,
        missing_only=False,
        facts_fn=facts_fn,
        list_fn=lambda: ["bueno", "malo"],
        overlay_file=overlay_file,
        proposals_dir=proposals,
    )
    data = json.loads(overlay_file.read_text(encoding="utf-8"))
    assert "bueno" in data
    assert "malo" not in data
    assert any(r.get("error") for r in results)
    err = capsys.readouterr().err
    assert "malo" in err


def test_main_requiere_modo():
    with pytest.raises(SystemExit) as exc:
        main(["--provider", "ollama"])
    assert exc.value.code == 2


def test_main_rechaza_proveedor_no_soportado():
    code = main(["--provider", "mancer", "--model", "x"])
    assert code == 2


def test_main_dry_run_mocked(tmp_path: Path, monkeypatch):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"
    proposals.mkdir()

    monkeypatch.setattr(
        "app.tools.overlay_generator.cli._default_facts",
        lambda _provider: (lambda _m: _facts_thinking_ctx()),
    )
    code = main(
        [
            "--provider",
            "ollama",
            "--model",
            "x:y",
            "--overlay-file",
            str(overlay_file),
            "--proposals-dir",
            str(proposals),
        ]
    )
    assert code == 0
    assert json.loads(overlay_file.read_text(encoding="utf-8")) == {}
    assert list(proposals.iterdir()) == []


def test_main_facts_falla_codigo_no_cero(tmp_path: Path, monkeypatch):
    overlay_file = tmp_path / "ollama.json"
    overlay_file.write_text("{}", encoding="utf-8")
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    monkeypatch.setattr(
        "app.tools.overlay_generator.cli._default_facts",
        lambda _provider: (lambda _m: None),
    )
    code = main(
        [
            "--model",
            "gone",
            "--write",
            "--overlay-file",
            str(overlay_file),
            "--proposals-dir",
            str(proposals),
        ]
    )
    assert code != 0
    assert json.loads(overlay_file.read_text(encoding="utf-8")) == {}
