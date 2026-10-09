import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from app.models import Conversation, IllustratedImage, ImageGenerationJob, Message, Rule
from app.services.conversation_title import derive_auto_title
from app.services.image_illustration.anchors import strip_illustration_artifacts
from app.services.conversation_tree import path_from_messages
from app.services.rules.models import RULE_SCOPES, SCOPE_CHAT
from app.services.workspace_profiles.snapshot import conversation_images_snapshot

# Sentinel para "no actualizar inject_instruction_every" en update_conversation
_INJECT_UNSET = object()
# Sentinel para "no actualizar instruction_override" (omitido en el body); None = borrar
INSTRUCTION_OVERRIDE_UNSET = object()
AUTO_TITLE_UNSET = object()
IMAGES_UNSET = object()


# ----- Rules (biblioteca) -----
def create_rule(
    db: Session,
    title: str = "",
    content: str = "",
    scope: str = SCOPE_CHAT,
    user_id: str | None = None,
) -> Rule:
    if scope not in RULE_SCOPES:
        raise ValueError(f"scope inválido: {scope}")
    rule = Rule(title=title, content=content, scope=scope, user_id=user_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_rule(db: Session, rule_id: str) -> Rule | None:
    return db.query(Rule).filter(Rule.id == rule_id).first()


def list_rules(db: Session, scope: str = SCOPE_CHAT, user_id: str | None = None) -> list[Rule]:
    q = db.query(Rule).filter(Rule.scope == scope)
    if user_id is not None:
        q = q.filter(or_(Rule.user_id.is_(None), Rule.user_id == user_id))
    return q.order_by(Rule.updated_at.desc()).all()


def update_rule(
    db: Session,
    rule_id: str,
    title: str | None = None,
    content: str | None = None,
    *,
    user_id: str | None = None,
) -> Rule | None:
    rule = get_rule(db, rule_id)
    if not rule:
        return None
    if user_id is not None and rule.user_id != user_id:
        return None
    if title is not None:
        rule.title = title
    if content is not None:
        rule.content = content
    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: str, *, user_id: str | None = None) -> bool:
    rule = get_rule(db, rule_id)
    if not rule:
        return False
    if user_id is not None and rule.user_id != user_id:
        return False
    db.delete(rule)
    db.commit()
    return True


def apply_auto_title(db: Session, conv: Conversation) -> bool:
    """Recalcula title desde el último mensaje visible. No hace commit."""
    if not getattr(conv, "auto_title", False):
        return False
    history = get_resolved_history(db, conv, None)
    if not history:
        history = get_messages(db, conv.id)
    if not history:
        return False
    derived = derive_auto_title(history[-1].content)
    if not derived or conv.title == derived:
        return False
    conv.title = derived
    return True


def create_conversation(
    db: Session,
    title: str = "Nueva conversación",
    model_id: str = "llama3.2",
    provider: str = "ollama",
    system_instruction_global: str | None = None,
    instruction_ids: list | None = None,
    inject_instruction_every: int | None = None,
    history_turns: int | None = 5,
    forked_from_conversation_id: str | None = None,
    forked_from_message_id: str | None = None,
    auto_title: bool = False,
    images: dict | None = None,
    kind: str = "chat",
    prompt_brief: dict | None = None,
    seed_prompt_generator_template: bool = True,
    user_id: str | None = None,
) -> Conversation:
    resolved_kind = kind if kind in ("chat", "prompt_generator") else "chat"
    resolved_title = title
    resolved_brief = prompt_brief
    if resolved_kind == "prompt_generator":
        from app.services.prompt_generator.brief import empty_brief

        if seed_prompt_generator_template:
            resolved_title = "txt2img"
        if resolved_brief is None:
            resolved_brief = empty_brief().to_dict()
    conv = Conversation(
        user_id=user_id,
        title=resolved_title,
        auto_title=bool(auto_title),
        model_id=model_id,
        provider=provider,
        system_instruction_global=system_instruction_global,
        instruction_ids=json.dumps(instruction_ids) if instruction_ids is not None else None,
        inject_instruction_every=inject_instruction_every if inject_instruction_every and inject_instruction_every > 0 else None,
        history_turns=history_turns if history_turns and history_turns > 0 else 5,
        forked_from_conversation_id=forked_from_conversation_id,
        forked_from_message_id=forked_from_message_id,
        images=json.dumps(conversation_images_snapshot(images)) if images is not None else None,
        kind=resolved_kind,
        prompt_brief=json.dumps(resolved_brief, ensure_ascii=False) if resolved_brief is not None else None,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    if resolved_kind == "prompt_generator" and seed_prompt_generator_template:
        from app.services.prompt_generator.system import INITIAL_ASSISTANT_TEMPLATE

        add_message(db, conv.id, "assistant", INITIAL_ASSISTANT_TEMPLATE)
        db.refresh(conv)
    return conv


def get_conversation(
    db: Session,
    conversation_id: str,
    *,
    include_deleted: bool = False,
    user_id: str | None = None,
) -> Conversation | None:
    q = db.query(Conversation).filter(Conversation.id == conversation_id)
    if not include_deleted:
        q = q.filter(Conversation.deleted_at.is_(None))
    if user_id is not None:
        q = q.filter(Conversation.user_id == user_id)
    return q.first()


CONVERSATION_SORT_ACTIVITY = "activity"
CONVERSATION_SORT_CREATED_AT = "created_at"
CONVERSATION_SORT_VALUES = (CONVERSATION_SORT_ACTIVITY, CONVERSATION_SORT_CREATED_AT)
MESSAGE_HISTORY_SORT_MESSAGE = "message"
MESSAGE_HISTORY_SORT_IMAGE = "image"
MESSAGE_HISTORY_SORT_VALUES = (MESSAGE_HISTORY_SORT_MESSAGE, MESSAGE_HISTORY_SORT_IMAGE)


def normalize_conversation_sort(sort: str | None) -> str:
    if sort == CONVERSATION_SORT_CREATED_AT:
        return CONVERSATION_SORT_CREATED_AT
    return CONVERSATION_SORT_ACTIVITY


def normalize_message_history_sort(sort: str | None) -> str:
    if sort == MESSAGE_HISTORY_SORT_IMAGE:
        return MESSAGE_HISTORY_SORT_IMAGE
    return MESSAGE_HISTORY_SORT_MESSAGE


def list_conversations(
    db: Session,
    sort: str | None = None,
    *,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> list[Conversation]:
    q = db.query(Conversation).filter(Conversation.deleted_at.is_(None))
    if user_id is not None:
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    if normalize_conversation_sort(sort) == CONVERSATION_SORT_CREATED_AT:
        return q.order_by(Conversation.created_at.desc()).all()
    return q.order_by(
        func.coalesce(Conversation.last_message_at, Conversation.updated_at).desc()
    ).all()


def list_deleted_conversations(
    db: Session, *, user_id: str | None = None, include_unowned: bool = False
) -> list[Conversation]:
    """Conversaciones en papelera (soft-deleted), más recientes primero."""
    q = db.query(Conversation).filter(Conversation.deleted_at.isnot(None))
    if user_id is not None:
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    return q.order_by(Conversation.deleted_at.desc()).all()


MESSAGE_HISTORY_PREVIEW_LEN = 80
MESSAGE_HISTORY_LIMIT_DEFAULT = 50
MESSAGE_HISTORY_LIMIT_MAX = 100


def clamp_message_history_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return MESSAGE_HISTORY_LIMIT_DEFAULT
    return min(int(limit), MESSAGE_HISTORY_LIMIT_MAX)


def clamp_message_history_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return int(offset)


def message_title_text(content: str) -> str:
    cleaned = strip_illustration_artifacts(content or "")
    first_line = cleaned.splitlines()[0] if cleaned else ""
    return " ".join(first_line.split())


def message_content_preview(content: str, max_len: int = MESSAGE_HISTORY_PREVIEW_LEN) -> str:
    first_line = message_title_text(content)
    if len(first_line) <= max_len:
        return first_line
    return first_line[:max_len].rstrip()


def _normalize_message_history_query(q: str | None) -> str:
    return " ".join((q or "").split()).strip()


def _unique_assistant_history_rows(
    rows: list[tuple],
) -> list[tuple[Message, str, datetime | None]]:
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    unique: list[tuple[Message, str, datetime | None]] = []
    for row in rows:
        msg = row[0]
        if not msg or msg.id in seen_ids:
            continue
        key = strip_illustration_artifacts(msg.content or "")
        if key in seen_keys:
            continue
        seen_ids.add(msg.id)
        seen_keys.add(key)
        if len(row) == 3:
            unique.append((msg, row[1], row[2]))
        else:
            unique.append((msg, row[1], None))
    return unique


def _filter_assistant_history_search(
    rows: list[tuple[Message, str, datetime | None]],
    q: str,
) -> tuple[list[tuple[Message, str, datetime | None]], str]:
    needle = q.casefold()
    title_hits = [
        row for row in rows if needle in message_title_text(row[0].content).casefold()
    ]
    if title_hits:
        return title_hits, "title"
    body_hits = [
        row
        for row in rows
        if needle in strip_illustration_artifacts(row[0].content or "").casefold()
    ]
    return body_hits, "content"


def _assistant_history_owner_filters(*, user_id: str | None = None, include_unowned: bool = False):
    filters = [
        Message.role == "assistant",
        Conversation.deleted_at.is_(None),
        Conversation.kind != Conversation.KIND_PROMPT_GENERATOR,
    ]
    if user_id is not None:
        if include_unowned:
            filters.append(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            filters.append(Conversation.user_id == user_id)
    return tuple(filters)


def _query_assistant_history_rows(
    db: Session,
    sort: str | None = None,
    *,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> list[tuple]:
    owner_filters = _assistant_history_owner_filters(
        user_id=user_id, include_unowned=include_unowned
    )
    if normalize_message_history_sort(sort) == MESSAGE_HISTORY_SORT_IMAGE:
        latest_image = (
            db.query(
                IllustratedImage.message_id.label("message_id"),
                func.max(IllustratedImage.created_at).label("latest_image_at"),
            )
            .group_by(IllustratedImage.message_id)
            .subquery()
        )
        return (
            db.query(Message, Conversation.title, latest_image.c.latest_image_at)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .outerjoin(latest_image, latest_image.c.message_id == Message.id)
            .filter(*owner_filters)
            .order_by(
                latest_image.c.latest_image_at.is_(None),
                latest_image.c.latest_image_at.desc(),
                Message.created_at.desc(),
            )
            .all()
        )
    return (
        db.query(Message, Conversation.title)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(*owner_filters)
        .order_by(Message.created_at.desc())
        .all()
    )


@dataclass(frozen=True)
class MessageHistoryPage:
    rows: list[tuple[Message, str, datetime | None]]
    total: int
    limit: int
    offset: int
    search_in: str | None


def list_assistant_messages(
    db: Session,
    limit: int | None = None,
    offset: int | None = None,
    sort: str | None = None,
    q: str | None = None,
    *,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> MessageHistoryPage:
    """Respuestas assistant únicas (texto sin artefactos de ilustración), paginadas."""
    capped = clamp_message_history_limit(limit)
    off = clamp_message_history_offset(offset)
    rows = _unique_assistant_history_rows(
        _query_assistant_history_rows(
            db, sort=sort, user_id=user_id, include_unowned=include_unowned
        )
    )
    search_in = None
    needle = _normalize_message_history_query(q)
    if needle:
        rows, search_in = _filter_assistant_history_search(rows, needle)
    total = len(rows)
    return MessageHistoryPage(
        rows=rows[off : off + capped],
        total=total,
        limit=capped,
        offset=off,
        search_in=search_in,
    )


def update_conversation(
    db: Session,
    conversation_id: str,
    title: str | None = None,
    model_id: str | None = None,
    provider: str | None = None,
    system_instruction_global: str | None = None,
    instruction_ids: list | None = None,
    inject_instruction_every: int | None = _INJECT_UNSET,
    model_params: dict | None = None,
    history_turns: int | None = None,
    instruction_override: str | None = INSTRUCTION_OVERRIDE_UNSET,
    active_leaf_message_id: str | None = None,
    auto_title: bool | object = AUTO_TITLE_UNSET,
    images: dict | None | object = IMAGES_UNSET,
) -> Conversation | None:
    conv = get_conversation(db, conversation_id)
    if not conv:
        return None
    updated_at_before = conv.updated_at
    if auto_title is not AUTO_TITLE_UNSET:
        conv.auto_title = bool(auto_title)
    if title is not None and not conv.auto_title:
        conv.title = title
    if model_id is not None:
        conv.model_id = model_id
    if provider is not None:
        conv.provider = provider
    if system_instruction_global is not None:
        conv.system_instruction_global = system_instruction_global
    if instruction_ids is not None:
        conv.instruction_ids = json.dumps(instruction_ids) if instruction_ids else None
    if inject_instruction_every is not _INJECT_UNSET:
        conv.inject_instruction_every = inject_instruction_every if (inject_instruction_every and inject_instruction_every > 0) else None
    if model_params is not None:
        conv.model_params = json.dumps(model_params) if model_params else None
    if history_turns is not None:
        conv.history_turns = history_turns if history_turns >= 0 else None
    if instruction_override is not INSTRUCTION_OVERRIDE_UNSET:
        conv.instruction_override = instruction_override.strip() if instruction_override and instruction_override.strip() else None
    if active_leaf_message_id is not None:
        leaf = get_message(db, conversation_id, active_leaf_message_id)
        if not leaf:
            return None
        conv.active_leaf_message_id = active_leaf_message_id
    if images is not IMAGES_UNSET:
        conv.images = json.dumps(conversation_images_snapshot(images)) if images is not None else None
    if conv.auto_title:
        apply_auto_title(db, conv)
    # No actualizar updated_at si solo cambió instruction_override (al hacer click en otra conversación no debe reordenar la lista)
    affects_order = any([
        title is not None and not conv.auto_title, model_id is not None, provider is not None,
        system_instruction_global is not None, instruction_ids is not None,
        inject_instruction_every is not _INJECT_UNSET, model_params is not None, history_turns is not None,
        images is not IMAGES_UNSET,
    ])
    if affects_order:
        conv.updated_at = datetime.utcnow()
    else:
        conv.updated_at = updated_at_before
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, conversation_id: str) -> bool:
    """Soft-delete: marca deleted_at. Los mensajes y metadatos se conservan."""
    conv = get_conversation(db, conversation_id)
    if not conv:
        return False
    conv.deleted_at = datetime.utcnow()
    db.commit()
    return True


def restore_conversation(db: Session, conversation_id: str) -> Conversation | None:
    """Saca una conversación de la papelera."""
    conv = get_conversation(db, conversation_id, include_deleted=True)
    if not conv or conv.deleted_at is None:
        return None
    conv.deleted_at = None
    db.commit()
    db.refresh(conv)
    return conv


def hard_delete_conversation(db: Session, conversation_id: str) -> bool:
    """Borrado definitivo solo desde papelera: fila, mensajes e imágenes asociadas."""
    from app.services.image_illustration.content_ops import extract_illustrated_filenames
    from app.services.image_illustration.orphan_files import delete_unreferenced_illustrated_files

    conv = get_conversation(db, conversation_id, include_deleted=True)
    if not conv or conv.deleted_at is None:
        return False
    filenames: list[str] = []
    for msg in list(conv.messages or []):
        filenames.extend(extract_illustrated_filenames(msg.content or ""))
        for img in list(getattr(msg, "illustrated_images", None) or []):
            if img.filename:
                filenames.append(img.filename)
    db.query(Conversation).filter(
        Conversation.forked_from_conversation_id == conversation_id
    ).update(
        {
            Conversation.forked_from_conversation_id: None,
            Conversation.forked_from_message_id: None,
        },
        synchronize_session=False,
    )
    db.delete(conv)
    db.commit()
    if filenames:
        delete_unreferenced_illustrated_files(db, filenames)
    return True


def purge_deleted_conversations(
    db: Session, *, user_id: str | None = None, include_unowned: bool = False
) -> list[str]:
    """Hard-delete de toda la papelera. Devuelve los ids eliminados."""
    ids = [
        c.id
        for c in list_deleted_conversations(
            db, user_id=user_id, include_unowned=include_unowned
        )
    ]
    deleted: list[str] = []
    for conversation_id in ids:
        if hard_delete_conversation(db, conversation_id):
            deleted.append(conversation_id)
    return deleted


def get_messages(db: Session, conversation_id: str) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )


def get_path_to_message(db: Session, conversation_id: str, message_id: str | None) -> list[Message]:
    """Camino raíz → message_id (inclusive) dentro de la conversación."""
    return path_from_messages(get_messages(db, conversation_id), message_id)


def get_inherited_prefix(db: Session, conv: Conversation, _seen: set[str] | None = None) -> list[Message]:
    """Mensajes del origen hasta el ancla (recursivo si el origen también es variante)."""
    origin_id = getattr(conv, "forked_from_conversation_id", None)
    anchor_id = getattr(conv, "forked_from_message_id", None)
    if not origin_id or not anchor_id:
        return []
    seen = set(_seen or ())
    if origin_id in seen or len(seen) > 32:
        return []
    seen.add(origin_id)
    origin = get_conversation(db, origin_id, include_deleted=True)
    if not origin:
        return []
    return get_resolved_history(db, origin, anchor_id, _seen=seen)


def get_resolved_history(
    db: Session,
    conv: Conversation,
    parent_id: str | None,
    _seen: set[str] | None = None,
) -> list[Message]:
    """Prefijo heredado + camino propio hasta parent_id (o la hoja activa si parent_id es None)."""
    prefix = get_inherited_prefix(db, conv, _seen=_seen)
    own = get_messages(db, conv.id)
    target = parent_id if parent_id is not None else getattr(conv, "active_leaf_message_id", None)
    if target:
        own_path = path_from_messages(own, target)
        if own_path:
            return prefix + own_path
        for i, msg in enumerate(prefix):
            if msg.id == target:
                return prefix[: i + 1]
        return prefix
    return prefix


def get_visible_message(db: Session, view_conversation_id: str, message_id: str) -> Message | None:
    """Mensaje propio o del prefijo heredado; None si no es visible en esa vista."""
    view = get_conversation(db, view_conversation_id)
    if not view:
        return None
    return _visible_message_in(db, view, message_id)


def _visible_message_in(db: Session, view: Conversation, message_id: str) -> Message | None:
    own = get_message(db, view.id, message_id)
    if own:
        return own
    for msg in get_inherited_prefix(db, view):
        if msg.id == message_id:
            return msg
    return None


def resolve_fork_anchor(db: Session, view_conv: Conversation, message_id: str) -> tuple[str, str] | None:
    """(conversation_id dueña del mensaje, message_id) para colgar el historial."""
    msg = _visible_message_in(db, view_conv, message_id)
    if not msg:
        return None
    return msg.conversation_id, message_id


def fork_conversation(db: Session, view_conversation_id: str, message_id: str) -> Conversation | None:
    """Conversación nueva, sin copiar mensajes; el historial se resuelve desde el ancla."""
    view = get_conversation(db, view_conversation_id)
    if not view:
        return None
    anchor = resolve_fork_anchor(db, view, message_id)
    if not anchor:
        return None
    owner_id, anchor_id = anchor
    instruction_ids = None
    if view.instruction_ids:
        try:
            parsed = json.loads(view.instruction_ids)
            if isinstance(parsed, list):
                instruction_ids = [str(x) for x in parsed if x]
        except (TypeError, ValueError):
            instruction_ids = None
    fork_brief = None
    raw_brief = getattr(view, "prompt_brief", None)
    if raw_brief:
        try:
            parsed_brief = json.loads(raw_brief) if isinstance(raw_brief, str) else raw_brief
            if isinstance(parsed_brief, dict):
                fork_brief = parsed_brief
        except (TypeError, ValueError, json.JSONDecodeError):
            fork_brief = None
    child = create_conversation(
        db,
        title=view.title or "Nueva conversación",
        model_id=view.model_id,
        provider=view.provider or "ollama",
        system_instruction_global=view.system_instruction_global,
        instruction_ids=instruction_ids,
        history_turns=view.history_turns if view.history_turns is not None else 5,
        forked_from_conversation_id=owner_id,
        forked_from_message_id=anchor_id,
        auto_title=bool(getattr(view, "auto_title", False)),
        kind=getattr(view, "kind", None) or "chat",
        prompt_brief=fork_brief,
        seed_prompt_generator_template=False,
        user_id=getattr(view, "user_id", None),
    )
    child.model_params = view.model_params
    child.images = view.images
    child.instruction_override = view.instruction_override
    child.last_message_at = datetime.utcnow()
    apply_auto_title(db, child)
    db.commit()
    db.refresh(child)
    return child


def get_message(db: Session, conversation_id: str, message_id: str) -> Message | None:
    """Obtiene un mensaje por id dentro de una conversación."""
    return (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.id == message_id,
        )
        .first()
    )


def update_message_content(db: Session, conversation_id: str, message_id: str, content: str) -> Message | None:
    """Actualiza el content de un mensaje (p. ej. tras ilustrar)."""
    msg = get_message(db, conversation_id, message_id)
    if not msg:
        return None
    msg.content = content
    db.commit()
    db.refresh(msg)
    return msg


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    instruction_override: str | None = None,
    debug_request_json: str | None = None,
    debug_response_raw: str | None = None,
    parent_id: str | None = None,
) -> Message:
    conv = get_conversation(db, conversation_id)
    resolved_parent = parent_id if parent_id is not None else (
        getattr(conv, "active_leaf_message_id", None) if conv else None
    )
    if resolved_parent and not get_message(db, conversation_id, resolved_parent):
        resolved_parent = None
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        instruction_override=instruction_override,
        debug_request_json=debug_request_json,
        debug_response_raw=debug_response_raw,
        parent_id=resolved_parent,
    )
    db.add(msg)
    db.flush()
    if conv:
        conv.last_message_at = datetime.utcnow()
        conv.active_leaf_message_id = msg.id
        apply_auto_title(db, conv)
    db.commit()
    db.refresh(msg)
    return msg


def touch_conversation(db: Session, conversation_id: str) -> None:
    conv = get_conversation(db, conversation_id)
    if conv:
        conv.updated_at = datetime.utcnow()
        db.commit()


def mark_conversations_deleted(db: Session, conversation_ids: list[str]) -> list[str]:
    """Soft-delete en lote. No hace commit. Devuelve los ids que estaban activos."""
    if not conversation_ids:
        return []
    now = datetime.utcnow()
    touched: list[str] = []
    seen: set[str] = set()
    for conversation_id in conversation_ids:
        if not conversation_id or conversation_id in seen:
            continue
        seen.add(conversation_id)
        conv = get_conversation(db, conversation_id)
        if not conv:
            continue
        conv.deleted_at = now
        touched.append(conversation_id)
    return touched


def delete_messages_hard(db: Session, conversation_id: str, message_ids: set[str] | list[str]) -> list[str]:
    """Borra esos mensajes (sin reparentar el subárbol). No hace commit."""
    wanted = [mid for mid in message_ids if mid]
    if not wanted:
        return []
    existing = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.id.in_(wanted))
        .all()
    )
    found = [m.id for m in existing]
    if not found:
        return []
    conv = get_conversation(db, conversation_id)
    next_leaf = None
    if conv and getattr(conv, "active_leaf_message_id", None) in set(found):
        next_leaf = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id, ~Message.id.in_(found))
            .order_by(Message.created_at.desc())
            .first()
        )
    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.parent_id.in_(found),
    ).update({Message.parent_id: None}, synchronize_session=False)
    db.query(Message).filter(Message.id.in_(found)).update(
        {Message.parent_id: None}, synchronize_session=False
    )
    db.query(Message).filter(Message.id.in_(found)).delete(synchronize_session=False)
    if conv and getattr(conv, "active_leaf_message_id", None) in set(found):
        conv.active_leaf_message_id = next_leaf.id if next_leaf else None
        apply_auto_title(db, conv)
    db.flush()
    return found


def delete_message(db: Session, conversation_id: str, message_id: str) -> bool:
    """Elimina un mensaje y reparenta sus hijos al padre del borrado."""
    msg = get_message(db, conversation_id, message_id)
    if not msg:
        return False
    conv = get_conversation(db, conversation_id)
    parent_id = msg.parent_id
    children = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.parent_id == message_id)
        .all()
    )
    for child in children:
        child.parent_id = parent_id
    if conv and getattr(conv, "active_leaf_message_id", None) == message_id:
        conv.active_leaf_message_id = parent_id
    db.delete(msg)
    if conv:
        apply_auto_title(db, conv)
    db.commit()
    return True


def delete_last_message(db: Session, conversation_id: str) -> bool:
    """Elimina la hoja activa (el mensaje actual del intento). False si no hay mensajes."""
    conv = get_conversation(db, conversation_id)
    leaf_id = getattr(conv, "active_leaf_message_id", None) if conv else None
    if leaf_id:
        return delete_message(db, conversation_id, leaf_id)
    msgs = get_messages(db, conversation_id)
    if not msgs:
        return False
    return delete_message(db, conversation_id, msgs[-1].id)


def clear_conversation_messages(db: Session, conversation_id: str) -> int:
    """Elimina todos los mensajes de una conversación. Devuelve el número de mensajes eliminados."""
    conv = get_conversation(db, conversation_id)
    count = db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    if conv:
        conv.active_leaf_message_id = None
    db.commit()
    return count


def save_illustrated_image_meta(
    db: Session,
    *,
    message_id: str,
    filename: str,
    scene_id: str | None,
    mode: str,
    params: dict,
    prompt_model: str | None = None,
    prompt_provider: str | None = None,
    use_chat_config: bool | None = None,
) -> IllustratedImage:
    """Upsert por filename: params Forge + LLM del planificador (columnas y params_json)."""
    model = (prompt_model or "").strip() or None
    provider = (prompt_provider or "").strip() or None
    stored = dict(params or {})
    if model:
        stored["prompt_llm_model"] = model
    if provider:
        stored["prompt_llm_provider"] = provider
    if use_chat_config is not None:
        stored["use_chat_config"] = bool(use_chat_config)
    row = (
        db.query(IllustratedImage)
        .filter(IllustratedImage.filename == filename)
        .first()
    )
    payload = json.dumps(stored, ensure_ascii=False, default=str)
    if row:
        row.message_id = message_id
        row.scene_id = scene_id
        row.mode = mode or row.mode
        row.params_json = payload
        row.prompt_model = model
        row.prompt_provider = provider
    else:
        row = IllustratedImage(
            message_id=message_id,
            filename=filename,
            scene_id=scene_id,
            mode=mode or "txt2img",
            params_json=payload,
            prompt_model=model,
            prompt_provider=provider,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_illustrated_image_meta(db: Session, filename: str) -> IllustratedImage | None:
    if not filename:
        return None
    return (
        db.query(IllustratedImage)
        .filter(IllustratedImage.filename == filename)
        .first()
    )


def get_latest_prompt_llm_for_message(
    db: Session, message_id: str
) -> tuple[str | None, str | None]:
    """Provider y modelo LLM del prompt más reciente del mensaje, si existen."""
    if not message_id:
        return None, None
    row = (
        db.query(IllustratedImage)
        .filter(IllustratedImage.message_id == message_id)
        .filter(IllustratedImage.prompt_model.isnot(None))
        .filter(IllustratedImage.prompt_model != "")
        .order_by(IllustratedImage.created_at.desc())
        .first()
    )
    if not row:
        return None, None
    return row.prompt_provider, row.prompt_model


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def gallery_visible_message_ids(db: Session, conversation_id: str) -> list[str]:
    """Mensajes visibles en esa vista: prefijo heredado (forks) + camino propio."""
    conv = get_conversation(db, conversation_id)
    if not conv:
        return []
    return [m.id for m in get_resolved_history(db, conv, None)]


def _illustrated_gallery_base_query(
    db: Session,
    *,
    require_active_owner: bool = True,
    user_id: str | None = None,
    include_unowned: bool = False,
):
    q = (
        db.query(IllustratedImage, Message, Conversation)
        .join(Message, IllustratedImage.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
    )
    if require_active_owner:
        q = q.filter(Conversation.deleted_at.is_(None))
    if user_id is not None:
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    return q


def _apply_illustrated_gallery_filters(
    q,
    *,
    db: Session,
    prompt_provider: str | None,
    prompt_model: str | None,
    forge_model: str | None,
    steps: int | None,
    width: int | None,
    height: int | None,
    seed: int | None,
    mode: str | None,
    prompt_q: str | None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    batch_ids: list[str] | None = None,
):
    if conversation_id:
        scoped_ids = gallery_visible_message_ids(db, conversation_id)
        if not scoped_ids:
            q = q.filter(false())
        else:
            q = q.filter(IllustratedImage.message_id.in_(scoped_ids))
    if message_id:
        q = q.filter(IllustratedImage.message_id == message_id)
    if batch_ids:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.batch_id").in_(batch_ids)
        )
    if prompt_provider is not None:
        if prompt_provider == "":
            q = q.filter(
                or_(
                    IllustratedImage.prompt_provider.is_(None),
                    IllustratedImage.prompt_provider == "",
                )
            )
        else:
            q = q.filter(IllustratedImage.prompt_provider == prompt_provider)
    if prompt_model is not None:
        if prompt_model == "":
            q = q.filter(
                or_(
                    IllustratedImage.prompt_model.is_(None),
                    IllustratedImage.prompt_model == "",
                )
            )
        else:
            q = q.filter(IllustratedImage.prompt_model == prompt_model)
    if forge_model:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.model") == forge_model
        )
    if steps is not None:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.steps") == steps
        )
    if width is not None:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.width") == width
        )
    if height is not None:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.height") == height
        )
    if seed is not None:
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.seed") == seed
        )
    if mode:
        q = q.filter(IllustratedImage.mode == mode)
    if prompt_q:
        like = f"%{_escape_like(prompt_q.strip())}%"
        q = q.filter(
            func.json_extract(IllustratedImage.params_json, "$.prompt").like(
                like, escape="\\"
            )
        )
    return q


def list_illustrated_images(
    db: Session,
    *,
    prompt_provider: str | None = None,
    prompt_model: str | None = None,
    forge_model: str | None = None,
    steps: int | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    mode: str | None = None,
    prompt_q: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    batch_ids: list[str] | None = None,
    limit: int = 24,
    offset: int = 0,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> tuple[list[tuple[IllustratedImage, Message, Conversation]], int]:
    """Galería: imágenes de conversaciones activas, más recientes primero."""
    q = _apply_illustrated_gallery_filters(
        _illustrated_gallery_base_query(
            db,
            require_active_owner=not bool(conversation_id),
            user_id=user_id,
            include_unowned=include_unowned,
        ),
        db=db,
        prompt_provider=prompt_provider,
        prompt_model=prompt_model,
        forge_model=forge_model,
        steps=steps,
        width=width,
        height=height,
        seed=seed,
        mode=mode,
        prompt_q=prompt_q,
        conversation_id=conversation_id,
        message_id=message_id,
        batch_ids=batch_ids,
    )
    total = q.count()
    rows = (
        q.order_by(IllustratedImage.created_at.desc(), IllustratedImage.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows, total


def list_illustrated_image_filenames(
    db: Session,
    *,
    prompt_provider: str | None = None,
    prompt_model: str | None = None,
    forge_model: str | None = None,
    steps: int | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    mode: str | None = None,
    prompt_q: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    batch_ids: list[str] | None = None,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> list[str]:
    """Filenames que pasan los mismos filtros que la galería, sin paginar."""
    q = _apply_illustrated_gallery_filters(
        _illustrated_gallery_base_query(
            db,
            require_active_owner=not bool(conversation_id),
            user_id=user_id,
            include_unowned=include_unowned,
        ),
        db=db,
        prompt_provider=prompt_provider,
        prompt_model=prompt_model,
        forge_model=forge_model,
        steps=steps,
        width=width,
        height=height,
        seed=seed,
        mode=mode,
        prompt_q=prompt_q,
        conversation_id=conversation_id,
        message_id=message_id,
        batch_ids=batch_ids,
    )
    return [
        filename
        for (filename,) in q.order_by(
            IllustratedImage.created_at.desc(), IllustratedImage.id.desc()
        )
        .with_entities(IllustratedImage.filename)
        .all()
    ]


def illustrated_image_facets(
    db: Session,
    *,
    conversation_id: str | None = None,
    message_id: str | None = None,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> dict:
    """Valores distintos para los filtros cerrados de la galería."""
    q = db.query(IllustratedImage).join(Message, IllustratedImage.message_id == Message.id).join(
        Conversation, Message.conversation_id == Conversation.id
    )
    if not conversation_id:
        q = q.filter(Conversation.deleted_at.is_(None))
    if user_id is not None:
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    q = _apply_illustrated_gallery_filters(
        q,
        db=db,
        prompt_provider=None,
        prompt_model=None,
        forge_model=None,
        steps=None,
        width=None,
        height=None,
        seed=None,
        mode=None,
        prompt_q=None,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    rows = q.all()
    providers: set[str] = set()
    models: set[str] = set()
    forge_models: set[str] = set()
    steps_vals: set[int] = set()
    seeds_vals: set[int] = set()
    sizes: set[str] = set()
    modes: set[str] = set()
    batches: dict[str, dict] = {}
    missing_llm = False
    for row in rows:
        if (row.prompt_provider or "").strip():
            providers.add(row.prompt_provider.strip())
        if (row.prompt_model or "").strip():
            models.add(row.prompt_model.strip())
        else:
            missing_llm = True
        if (row.mode or "").strip():
            modes.add(row.mode.strip())
        try:
            params = json.loads(row.params_json or "{}")
        except json.JSONDecodeError:
            params = {}
        if not isinstance(params, dict):
            continue
        forge = str(params.get("model") or "").strip()
        if forge:
            forge_models.add(forge)
        if params.get("steps") is not None:
            try:
                steps_vals.add(int(params["steps"]))
            except (TypeError, ValueError):
                pass
        if params.get("seed") is not None:
            try:
                seeds_vals.add(int(params["seed"]))
            except (TypeError, ValueError):
                pass
        w, h = params.get("width"), params.get("height")
        if w is not None and h is not None:
            try:
                sizes.add(f"{int(w)}x{int(h)}")
            except (TypeError, ValueError):
                pass
        batch = str(params.get("batch_id") or "").strip()
        if batch:
            entry = batches.get(batch)
            created = row.created_at.isoformat() if row.created_at else None
            if entry is None:
                batches[batch] = {
                    "batch_id": batch,
                    "image_count": 1,
                    "created_at": created,
                }
            else:
                entry["image_count"] = int(entry["image_count"]) + 1
                if created and (not entry.get("created_at") or created > entry["created_at"]):
                    entry["created_at"] = created
    batch_list = sorted(
        batches.values(),
        key=lambda b: (b.get("created_at") or "", b["batch_id"]),
        reverse=True,
    )
    return {
        "prompt_providers": sorted(providers),
        "prompt_models": sorted(models),
        "forge_models": sorted(forge_models),
        "steps": sorted(steps_vals),
        "seeds": sorted(seeds_vals),
        "sizes": sorted(sizes, key=lambda s: [int(p) for p in s.split("x")]),
        "modes": sorted(modes),
        "batches": batch_list,
        "has_missing_prompt_llm": missing_llm,
    }


def _message_excerpt(content: str, limit: int = 88) -> str:
    text = re.sub(r"<[^>]+>", " ", content or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def list_illustrated_message_summaries(db: Session, conversation_id: str) -> list[dict]:
    """Mensajes visibles (propios o heredados) de una conversación activa con al menos una imagen."""
    conv = get_conversation(db, conversation_id)
    if not conv:
        return []
    history = get_resolved_history(db, conv, None)
    if not history:
        return []
    ids = [m.id for m in history]
    counts = (
        db.query(IllustratedImage.message_id, func.count(IllustratedImage.id))
        .filter(IllustratedImage.message_id.in_(ids))
        .group_by(IllustratedImage.message_id)
        .all()
    )
    if not counts:
        return []
    by_id = {mid: n for mid, n in counts}
    return [
        {
            "message_id": msg.id,
            "role": msg.role,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "excerpt": _message_excerpt(msg.content or ""),
            "image_count": int(by_id.get(msg.id) or 0),
        }
        for msg in history
        if msg.id in by_id
    ]


def delete_illustrated_images_by_filenames(db: Session, filenames: list[str]) -> int:
    if not filenames:
        return 0
    count = (
        db.query(IllustratedImage)
        .filter(IllustratedImage.filename.in_(filenames))
        .delete(synchronize_session=False)
    )
    db.commit()
    return count


_FIRST_SENTENCE_RE = re.compile(r"[\n\r]+|[.!?…]+(?:\s|$)")


def _message_first_sentence(content: str, limit: int = 120) -> str:
    """Primera frase o línea del mensaje, sin markup HTML."""
    text = re.sub(r"<[^>]+>", " ", content or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    match = _FIRST_SENTENCE_RE.search(text)
    sentence = text[: match.start()].strip() if match else text
    if not sentence:
        sentence = text
    if len(sentence) > limit:
        return sentence[: limit - 1] + "…"
    return sentence


def create_image_generation_job(
    db: Session,
    *,
    conversation_id: str,
    message_id: str,
    scene_id: str,
    forge_prompt: str,
    forge_mode: str,
    forge_body: dict,
    rules: dict | None = None,
    prompt_model: str | None = None,
    prompt_provider: str | None = None,
    batch_id: str | None = None,
    retries_remaining: int = 0,
) -> ImageGenerationJob:
    job = ImageGenerationJob(
        conversation_id=conversation_id,
        message_id=message_id,
        scene_id=scene_id,
        batch_id=batch_id,
        status="pending",
        forge_prompt=forge_prompt or "",
        forge_mode=forge_mode or "txt2img",
        forge_body_json=json.dumps(forge_body or {}, ensure_ascii=False),
        rules_json=json.dumps(rules or {}, ensure_ascii=False),
        prompt_model=prompt_model,
        prompt_provider=prompt_provider,
        retries_remaining=max(0, int(retries_remaining)),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_image_generation_job(db: Session, job_id: str) -> ImageGenerationJob | None:
    return db.query(ImageGenerationJob).filter(ImageGenerationJob.id == job_id).first()


def claim_next_image_generation_job(db: Session) -> ImageGenerationJob | None:
    job = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.status == "pending")
        .order_by(ImageGenerationJob.created_at.asc(), ImageGenerationJob.id.asc())
        .first()
    )
    if not job:
        return None
    job.status = "generating"
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def reset_stuck_image_generation_jobs(db: Session) -> int:
    count = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.status == "generating")
        .update(
            {
                ImageGenerationJob.status: "pending",
                ImageGenerationJob.started_at: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return int(count or 0)


def complete_image_generation_job(
    db: Session,
    job_id: str,
    *,
    result_filename: str,
) -> ImageGenerationJob | None:
    job = db.query(ImageGenerationJob).filter(ImageGenerationJob.id == job_id).first()
    if not job:
        return None
    job.status = "completed"
    job.result_filename = result_filename
    job.completed_at = datetime.utcnow()
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def fail_image_generation_job(
    db: Session,
    job_id: str,
    *,
    error_message: str,
    retry: bool = False,
) -> ImageGenerationJob | None:
    job = db.query(ImageGenerationJob).filter(ImageGenerationJob.id == job_id).first()
    if not job:
        return None
    if retry and job.retries_remaining > 0:
        job.retries_remaining -= 1
        job.status = "pending"
        job.started_at = None
        job.error_message = (error_message or "")[:2000]
    else:
        job.status = "failed"
        job.error_message = (error_message or "")[:2000]
        job.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def count_active_image_generation_jobs(
    db: Session, *, user_id: str | None = None, include_unowned: bool = False
) -> int:
    q = db.query(ImageGenerationJob).filter(ImageGenerationJob.status.in_(("pending", "generating")))
    if user_id is not None:
        q = q.join(Conversation, Conversation.id == ImageGenerationJob.conversation_id)
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    return q.count()


def summarize_active_image_generation_batches(
    db: Session, *, user_id: str | None = None, include_unowned: bool = False
) -> list[dict]:
    """Progreso completed/total por batch_id con jobs aún pendientes o en curso."""
    active_q = db.query(ImageGenerationJob.batch_id).filter(
        ImageGenerationJob.batch_id.isnot(None),
        ImageGenerationJob.batch_id != "",
        ImageGenerationJob.status.in_(("pending", "generating")),
    )
    if user_id is not None:
        active_q = active_q.join(
            Conversation, Conversation.id == ImageGenerationJob.conversation_id
        )
        if include_unowned:
            active_q = active_q.filter(
                or_(Conversation.user_id == user_id, Conversation.user_id.is_(None))
            )
        else:
            active_q = active_q.filter(Conversation.user_id == user_id)
    active_batch_ids = {row[0] for row in active_q.distinct().all() if row[0]}
    if not active_batch_ids:
        return []

    rows_q = db.query(ImageGenerationJob).filter(ImageGenerationJob.batch_id.in_(active_batch_ids))
    if user_id is not None:
        rows_q = rows_q.join(
            Conversation, Conversation.id == ImageGenerationJob.conversation_id
        )
        if include_unowned:
            rows_q = rows_q.filter(
                or_(Conversation.user_id == user_id, Conversation.user_id.is_(None))
            )
        else:
            rows_q = rows_q.filter(Conversation.user_id == user_id)
    rows = rows_q.all()
    by_batch: dict[str, dict] = {}
    for job in rows:
        bid = job.batch_id
        entry = by_batch.setdefault(
            bid,
            {
                "batch_id": bid,
                "completed": 0,
                "total": 0,
                "created_at": job.created_at,
            },
        )
        entry["total"] += 1
        if job.status == "completed":
            entry["completed"] += 1
        if job.created_at and (
            entry["created_at"] is None or job.created_at < entry["created_at"]
        ):
            entry["created_at"] = job.created_at

    result = []
    for entry in by_batch.values():
        created = entry["created_at"]
        result.append(
            {
                "batch_id": entry["batch_id"],
                "completed": entry["completed"],
                "total": entry["total"],
                "created_at": created.isoformat() if created else None,
            }
        )
    result.sort(key=lambda item: item["created_at"] or "")
    return result


def list_active_image_generation_job_ids(
    db: Session, *, user_id: str | None = None, include_unowned: bool = False
) -> list[str]:
    q = db.query(ImageGenerationJob.id).filter(
        ImageGenerationJob.status.in_(("pending", "generating"))
    )
    if user_id is not None:
        q = q.join(Conversation, Conversation.id == ImageGenerationJob.conversation_id)
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    rows = q.all()
    return [row[0] for row in rows]


def list_all_message_contents(db: Session) -> list[str]:
    return [row[0] or "" for row in db.query(Message.content).all()]


def image_generation_job_exists(db: Session, job_id: str) -> bool:
    db.commit()
    db.expire_all()
    return (
        db.query(ImageGenerationJob.id)
        .filter(ImageGenerationJob.id == job_id)
        .first()
        is not None
    )


def complete_image_generation_job_if_generating(
    db: Session,
    job_id: str,
    *,
    result_filename: str,
) -> ImageGenerationJob | None:
    """Completa solo si el job sigue generating (otra sesión puede haberlo cancelado)."""
    db.commit()
    db.expire_all()
    job = (
        db.query(ImageGenerationJob)
        .filter(
            ImageGenerationJob.id == job_id,
            ImageGenerationJob.status == "generating",
        )
        .first()
    )
    if not job:
        return None
    return complete_image_generation_job(db, job_id, result_filename=result_filename)


def list_image_generation_jobs(
    db: Session,
    *,
    statuses: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> tuple[list[dict], int]:
    q = db.query(ImageGenerationJob)
    if user_id is not None:
        q = q.join(Conversation, Conversation.id == ImageGenerationJob.conversation_id)
        if include_unowned:
            q = q.filter(or_(Conversation.user_id == user_id, Conversation.user_id.is_(None)))
        else:
            q = q.filter(Conversation.user_id == user_id)
    if statuses:
        cleaned = [s.strip() for s in statuses if (s or "").strip()]
        if cleaned:
            q = q.filter(ImageGenerationJob.status.in_(cleaned))
    total = q.count()
    rows = (
        q.order_by(ImageGenerationJob.created_at.desc(), ImageGenerationJob.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    if not rows:
        return [], total

    conv_ids = {r.conversation_id for r in rows}
    msg_ids = {r.message_id for r in rows}
    convs = {
        c.id: c
        for c in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()
    }
    msgs = {
        m.id: m
        for m in db.query(Message).filter(Message.id.in_(msg_ids)).all()
    }

    items = []
    for job in rows:
        conv = convs.get(job.conversation_id)
        msg = msgs.get(job.message_id)
        rules = {}
        try:
            rules = json.loads(job.rules_json or "{}")
        except (TypeError, json.JSONDecodeError):
            rules = {}
        items.append(
            {
                "id": job.id,
                "status": job.status,
                "conversation_id": job.conversation_id,
                "conversation_title": (conv.title if conv else "") or "Conversación",
                "message_id": job.message_id,
                "message_excerpt": _message_first_sentence(msg.content if msg else ""),
                "scene_id": job.scene_id,
                "forge_prompt": job.forge_prompt or "",
                "prompt_model": job.prompt_model,
                "prompt_provider": job.prompt_provider,
                "batch_id": job.batch_id,
                "error_message": job.error_message,
                "result_filename": job.result_filename,
                "rules": rules,
                "forge_mode": job.forge_mode or "txt2img",
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        )
    return items, total
