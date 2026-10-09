"""Hechos fiables de un modelo, independientes del proveedor (port).

El generador de overlays solo debe auto-escribir datos verificables. Este puerto
abstrae *de dónde* salen esos hechos: Ollama los obtiene de `/api/show`; NaN, de
su catálogo curado, porque su API no expone un endpoint de detalle por modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.model_contract.show_live import live_caps_from_show


@dataclass(frozen=True)
class ModelFacts:
    """Subconjunto de capacidades que se puede persistir sin revisión humana."""

    vision: bool = False
    tools: bool = False
    thinking_flag: bool = False
    context_length: int | None = None


def facts_from_show(show: dict[str, Any] | None) -> ModelFacts:
    """Hechos a partir de una respuesta tipo Ollama `/api/show` (o equivalente)."""
    live = live_caps_from_show(show or {})
    return ModelFacts(
        vision=bool(live.get("vision")),
        tools=bool(live.get("tools")),
        thinking_flag=bool(live.get("thinking_flag")),
        context_length=live.get("context_length"),
    )


def facts_from_catalog(entry: dict[str, Any] | None) -> ModelFacts:
    """Hechos desde una entrada de catálogo curado del proveedor.

    A diferencia de `facts_from_show`, no hay flags: el catálogo declara los
    booleanos explícitamente. El contexto se toma de `context_length`.
    """
    data = entry if isinstance(entry, dict) else {}
    raw_ctx = data.get("context_length")
    try:
        context_length = int(raw_ctx) if raw_ctx is not None else None
    except (TypeError, ValueError):
        context_length = None
    return ModelFacts(
        vision=bool(data.get("vision", False)),
        tools=bool(data.get("tools", False)),
        thinking_flag=bool(data.get("thinking_flag", False)),
        context_length=context_length,
    )
