"""Ejecución de un turno del entrevistador prompt generator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app import crud
from app.providers import get_provider
from app.provider_params import build_extra_body
from app.services.prompt_generator.brief import PromptBrief, detect_force, empty_brief
from app.services.prompt_generator.parse import parse_agent_response
from app.services.prompt_generator.system import build_system_prompt

PROMPT_FENCE_START = "```txt2img-prompt"
PROMPT_FENCE_END = "```"

CompleteFn = Callable[..., str]


def format_assistant_content(assistant_text: str, phase: str, prompt: str | None) -> str:
    text = (assistant_text or "").strip()
    if phase == "prompt" and prompt:
        return f"{text}\n\n{PROMPT_FENCE_START}\n{prompt.strip()}\n{PROMPT_FENCE_END}"
    return text


def _load_brief(conv) -> PromptBrief:
    raw = getattr(conv, "prompt_brief", None)
    if not raw:
        return empty_brief()
    if isinstance(raw, dict):
        return PromptBrief.from_dict(raw)
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return empty_brief()
    return PromptBrief.from_dict(data if isinstance(data, dict) else None)


def _history_messages(db: Session, conversation_id: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in crud.get_messages(db, conversation_id):
        role = msg.role if msg.role in ("user", "assistant") else "assistant"
        out.append({"role": role, "content": msg.content})
    return out


def _provider_complete(conv, model_params_override: dict | None = None) -> CompleteFn:
    provider = get_provider(conv.provider)
    model_params = None
    if isinstance(model_params_override, dict) and model_params_override:
        model_params = model_params_override
    else:
        raw_params = getattr(conv, "model_params", None)
        if raw_params:
            try:
                model_params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
            except (TypeError, json.JSONDecodeError):
                model_params = None
    extra_default = (
        build_extra_body(conv.provider, model_params, model_id=conv.model_id)
        if model_params
        else None
    )

    def _fn(model: str, messages: list[dict], extra_body: dict | None = None) -> str:
        return provider.chat(
            model,
            messages,
            extra_body=extra_body if extra_body is not None else extra_default,
        )

    return _fn


@dataclass
class TurnResult:
    assistant_text: str
    phase: str
    prompt: Optional[str]
    brief: dict[str, Any]
    user_message: Any | None
    assistant_message: Any


def run_turn(
    db: Session,
    conversation_id: str,
    *,
    message: str | None = None,
    force: bool = False,
    model_params: dict | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    complete_fn: CompleteFn | None = None,
) -> TurnResult:
    conv = crud.get_conversation(db, conversation_id)
    if not conv:
        raise LookupError("Conversación no encontrada")
    kind = getattr(conv, "kind", None) or "chat"
    if kind != "prompt_generator":
        raise PermissionError("La conversación no es prompt_generator")

    # Selección viva de la UI: si llega, se aplica y se persiste para que lo mostrado sea lo usado.
    updates = {}
    if provider and provider != conv.provider:
        updates["provider"] = provider
    if model_id and model_id != conv.model_id:
        updates["model_id"] = model_id
    if updates:
        crud.update_conversation(db, conversation_id, **updates)
        conv = crud.get_conversation(db, conversation_id)

    user_text = (message or "").strip()
    forced = bool(force) or detect_force(user_text)
    brief = _load_brief(conv)

    llm_user = user_text
    if forced:
        force_note = (
            "[FORZAR GENERACIÓN] Debes responder con phase=\"prompt\" y un prompt "
            "completo usando el brief actual (rellena huecos mínimos si hace falta)."
        )
        llm_user = f"{user_text}\n\n{force_note}".strip() if user_text else force_note

    system = (
        build_system_prompt()
        + "\n\nBrief actual (JSON):\n"
        + json.dumps(brief.to_dict(), ensure_ascii=False, indent=2)
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(_history_messages(db, conversation_id))
    if llm_user:
        messages.append({"role": "user", "content": llm_user})

    fn = complete_fn or _provider_complete(conv, model_params_override=model_params)
    raw = fn(conv.model_id, messages, extra_body=None)
    try:
        parsed = parse_agent_response(raw)
    except ValueError:
        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    "Tu respuesta anterior no era JSON válido. "
                    "Responde SOLO con el objeto JSON del contrato."
                ),
            }
        ]
        raw = fn(conv.model_id, retry_messages, extra_body=None)
        parsed = parse_agent_response(raw)

    if forced and parsed.phase != "prompt":
        retry_force = messages + [
            {
                "role": "user",
                "content": (
                    '[FORZAR] phase debe ser "prompt" y "prompt" no vacío. '
                    "Responde solo JSON."
                ),
            }
        ]
        raw = fn(conv.model_id, retry_force, extra_body=None)
        parsed = parse_agent_response(raw)

    brief = brief.merge(parsed.brief_patch)
    brief.force_generate = forced
    if parsed.phase == "prompt" and parsed.prompt:
        brief.latest_prompt = parsed.prompt

    user_msg = None
    parent_id = getattr(conv, "active_leaf_message_id", None)
    if user_text:
        user_msg = crud.add_message(
            db,
            conversation_id,
            role="user",
            content=user_text,
            parent_id=parent_id,
        )
        parent_id = user_msg.id

    content = format_assistant_content(parsed.assistant_text, parsed.phase, parsed.prompt)
    assistant_msg = crud.add_message(
        db,
        conversation_id,
        role="assistant",
        content=content,
        parent_id=parent_id,
        debug_response_raw=raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False),
    )

    conv = crud.get_conversation(db, conversation_id)
    conv.prompt_brief = json.dumps(brief.to_dict(), ensure_ascii=False)
    conv.updated_at = datetime.utcnow()
    db.add(conv)
    db.commit()
    crud.touch_conversation(db, conversation_id)

    return TurnResult(
        assistant_text=parsed.assistant_text,
        phase=parsed.phase,
        prompt=parsed.prompt,
        brief=brief.to_dict(),
        user_message=user_msg,
        assistant_message=assistant_msg,
    )
