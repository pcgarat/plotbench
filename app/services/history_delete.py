"""Borrado del historial lateral: conversación raíz o rama propia de un fork."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import crud
from app.models import Conversation, Message
from app.services.conversation_tree import children_grouped
from app.services.image_illustration.content_ops import extract_illustrated_filenames
from app.services.image_illustration.orphan_files import delete_unreferenced_illustrated_files
from app.services.message_tree import _active_chat_conv_filter, _owner_filter, get_message_any_active


@dataclass
class HistoryDeleteResult:
    trashed_conversation_ids: list[str] = field(default_factory=list)
    deleted_message_ids: list[str] = field(default_factory=list)
    deleted_message_refs: list[tuple[str, str]] = field(default_factory=list)


def subtree_message_ids(messages: list[Message], root_id: str) -> set[str]:
    by_id = {m.id: m for m in messages if getattr(m, "id", None)}
    root = by_id.get(root_id)
    if root is None:
        return set()
    groups = children_grouped(messages)
    out: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.id in out:
            continue
        out.add(node.id)
        stack.extend(groups.get(node.id, []))
    return out


def fork_branch_message_ids(messages: list[Message], start_id: str) -> set[str]:
    """Subárbol desde el nodo y el user padre si se queda sin hijos en la misma conversación."""
    ids = subtree_message_ids(messages, start_id)
    by_id = {m.id: m for m in messages if getattr(m, "id", None)}
    start = by_id.get(start_id)
    if start is None:
        return ids
    parent = by_id.get(getattr(start, "parent_id", None))
    if parent is None or parent.role != "user":
        return ids
    leftover = [
        child
        for child in children_grouped(messages).get(parent.id, [])
        if child.id not in ids
    ]
    if not leftover:
        ids.add(parent.id)
    return ids


def _descendant_fork_ids(
    db: Session,
    conversation_ids: list[str],
    *,
    user_id: str | None,
    include_unowned: bool,
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    frontier = [cid for cid in conversation_ids if cid]
    while frontier:
        kids = (
            db.query(Conversation)
            .filter(
                Conversation.forked_from_conversation_id.in_(frontier),
                *_active_chat_conv_filter(),
                *_owner_filter(user_id=user_id, include_unowned=include_unowned),
            )
            .all()
        )
        frontier = []
        for kid in kids:
            if kid.id in seen:
                continue
            seen.add(kid.id)
            found.append(kid.id)
            frontier.append(kid.id)
    return found


def _forks_anchored_at(
    db: Session,
    message_ids: set[str],
    *,
    user_id: str | None,
    include_unowned: bool,
) -> list[Conversation]:
    if not message_ids:
        return []
    return (
        db.query(Conversation)
        .filter(
            Conversation.forked_from_message_id.in_(list(message_ids)),
            *_active_chat_conv_filter(),
            *_owner_filter(user_id=user_id, include_unowned=include_unowned),
        )
        .all()
    )


def _unique(ids: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in ids:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def delete_history_nodes(
    db: Session,
    message_ids: list[str],
    *,
    user_id: str | None = None,
    include_unowned: bool = False,
) -> HistoryDeleteResult:
    owner_kw = {"user_id": user_id, "include_unowned": include_unowned}
    resolved: list[Message] = []
    seen_msg: set[str] = set()
    for mid in message_ids or []:
        if not mid or mid in seen_msg:
            continue
        seen_msg.add(mid)
        msg = get_message_any_active(db, mid, **owner_kw)
        if msg:
            resolved.append(msg)

    root_conv_ids: list[str] = []
    fork_msgs: list[tuple[Conversation, Message]] = []
    seen_root: set[str] = set()
    for msg in resolved:
        conv = crud.get_conversation(db, msg.conversation_id)
        if conv is None:
            continue
        if getattr(conv, "forked_from_conversation_id", None):
            fork_msgs.append((conv, msg))
            continue
        if conv.id not in seen_root:
            seen_root.add(conv.id)
            root_conv_ids.append(conv.id)

    to_trash = list(root_conv_ids)
    to_trash.extend(_descendant_fork_ids(db, root_conv_ids, **owner_kw))

    deleted_message_ids: list[str] = []
    deleted_refs: list[tuple[str, str]] = []
    filenames: list[str] = []
    trashed_set = set(to_trash)

    by_fork: dict[str, list[Message]] = {}
    for conv, msg in fork_msgs:
        if conv.id in trashed_set:
            continue
        by_fork.setdefault(conv.id, []).append(msg)

    for conv_id, nodes in by_fork.items():
        conv = crud.get_conversation(db, conv_id)
        if conv is None:
            continue
        own = crud.get_messages(db, conv_id)
        branch: set[str] = set()
        for node in nodes:
            branch |= fork_branch_message_ids(own, node.id)
        if not branch:
            continue

        anchored = _forks_anchored_at(db, branch, **owner_kw)
        fork_ids = [c.id for c in anchored]
        fork_ids.extend(_descendant_fork_ids(db, fork_ids, **owner_kw))
        for fid in fork_ids:
            if fid not in trashed_set:
                to_trash.append(fid)
                trashed_set.add(fid)

        own_ids = {m.id for m in own}
        if own_ids and own_ids <= branch:
            if conv_id not in trashed_set:
                to_trash.append(conv_id)
                trashed_set.add(conv_id)
            continue

        for msg in own:
            if msg.id in branch:
                filenames.extend(extract_illustrated_filenames(msg.content or ""))
        removed = crud.delete_messages_hard(db, conv_id, branch)
        deleted_message_ids.extend(removed)
        deleted_refs.extend((conv_id, mid) for mid in removed)

        leftover = crud.get_messages(db, conv_id)
        if not leftover and conv_id not in trashed_set:
            to_trash.append(conv_id)
            trashed_set.add(conv_id)

    trashed = crud.mark_conversations_deleted(db, _unique(to_trash))
    db.commit()
    if filenames:
        delete_unreferenced_illustrated_files(db, filenames)
    return HistoryDeleteResult(
        trashed_conversation_ids=trashed,
        deleted_message_ids=deleted_message_ids,
        deleted_message_refs=deleted_refs,
    )
