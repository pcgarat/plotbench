"""Stub fiable desde hechos del modelo y merge aditivo con preserve de curado."""

from __future__ import annotations

import copy
from typing import Any

from app.services.model_contract.facts import ModelFacts, facts_from_show


def stub_from_facts(facts: ModelFacts) -> dict[str, Any]:
    """Stub con solo campos fiables. Sin recipes/quirks/levels inventados."""
    caps: dict[str, Any] = {
        "vision": bool(facts.vision),
        "tools": bool(facts.tools),
    }
    if facts.thinking_flag:
        caps["thinking"] = {"kind": "boolean", "can_disable": True, "default": True}
    else:
        caps["thinking"] = {"kind": "none"}
    params: dict[str, Any] = {}
    if facts.context_length:
        params["num_ctx"] = {"max": facts.context_length}
    return {
        "capabilities": caps,
        "params": params,
        "recipes": [],
        "quirks": [],
    }


def stub_from_show(model_id: str, show: dict[str, Any]) -> dict[str, Any]:
    """Compatibilidad: stub a partir de una respuesta tipo `/api/show`."""
    _ = model_id
    return stub_from_facts(facts_from_show(show))


def merge_overlay(existing: dict[str, Any] | None, stub: dict[str, Any]) -> dict[str, Any]:
    """
    Merge aditivo: rellena huecos fiables; no pisa recipes/quirks ni thinking levels.

    - Sin existing → stub.
    - Con existing → vision/tools/num_ctx.max solo si ausentes; thinking solo si ausente;
      thinking.kind == levels siempre se conserva.
    """
    if not existing:
        return copy.deepcopy(stub)

    out = copy.deepcopy(existing)
    stub_caps = stub.get("capabilities") if isinstance(stub.get("capabilities"), dict) else {}
    out_caps = out.get("capabilities")
    if not isinstance(out_caps, dict):
        out_caps = {}
        out["capabilities"] = out_caps

    for key in ("vision", "tools"):
        if key not in out_caps and key in stub_caps:
            out_caps[key] = stub_caps[key]

    stub_thinking = stub_caps.get("thinking")
    existing_thinking = out_caps.get("thinking")
    if isinstance(stub_thinking, dict):
        if not isinstance(existing_thinking, dict):
            out_caps["thinking"] = copy.deepcopy(stub_thinking)
        elif str(existing_thinking.get("kind") or "") == "levels":
            pass
        # boolean/none ya curados: no sobrescribir

    stub_params = stub.get("params") if isinstance(stub.get("params"), dict) else {}
    stub_num_ctx = stub_params.get("num_ctx") if isinstance(stub_params.get("num_ctx"), dict) else {}
    if "max" in stub_num_ctx:
        out_params = out.get("params")
        if not isinstance(out_params, dict):
            out_params = {}
            out["params"] = out_params
        existing_num_ctx = out_params.get("num_ctx")
        if not isinstance(existing_num_ctx, dict):
            out_params["num_ctx"] = {"max": stub_num_ctx["max"]}
        elif "max" not in existing_num_ctx:
            merged_ctx = dict(existing_num_ctx)
            merged_ctx["max"] = stub_num_ctx["max"]
            out_params["num_ctx"] = merged_ctx

    if "recipes" not in out:
        out["recipes"] = copy.deepcopy(stub.get("recipes", []))
    if "quirks" not in out:
        out["quirks"] = copy.deepcopy(stub.get("quirks", []))

    return out
