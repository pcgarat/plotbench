"""API del árbol unificado de respuestas (roots + children)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.ownership import require_owned_conversation
from app.rag import delete_message_document
from app.schemas import (
    HistoryDeleteRequest,
    HistoryDeleteResponse,
    MessageTreeListResponse,
    MessageTreeNode,
)
from app.services import history_delete as history_delete_svc
from app.services import message_tree as mt

router = APIRouter(prefix="/api", tags=["message-tree"])


def _to_schema(node: mt.MessageTreeNodeData) -> MessageTreeNode:
    return MessageTreeNode(
        id=node.id,
        conversation_id=node.conversation_id,
        conversation_title=node.conversation_title,
        content_preview=node.content_preview,
        created_at=node.created_at,
        parent_message_id=node.parent_message_id,
        is_fork_edge=node.is_fork_edge,
        has_children=node.has_children,
        sibling_index=node.sibling_index,
        sibling_count=node.sibling_count,
        active_leaf_message_id=None,
    )


@router.get("/message-tree/roots", response_model=MessageTreeListResponse)
def list_message_tree_roots(
    user: CurrentUser,
    limit: int = Query(default=mt.ROOT_LIMIT_DEFAULT, ge=1, le=mt.ROOT_LIMIT_MAX),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    page = mt.list_root_nodes(
        db,
        limit=limit,
        offset=offset,
        user_id=user.id,
        include_unowned=bool(user.is_admin),
    )
    return MessageTreeListResponse(
        items=[_to_schema(n) for n in page.nodes],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/message-tree/delete", response_model=HistoryDeleteResponse)
def delete_history_nodes(
    body: HistoryDeleteRequest, user: CurrentUser, db: Session = Depends(get_db)
):
    ids = [mid for mid in (body.message_ids or []) if isinstance(mid, str) and mid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="Indica al menos un mensaje")
    result = history_delete_svc.delete_history_nodes(
        db,
        ids,
        user_id=user.id,
        include_unowned=bool(user.is_admin),
    )
    for conversation_id, message_id in result.deleted_message_refs:
        delete_message_document(conversation_id, message_id)
    return HistoryDeleteResponse(
        trashed_conversation_ids=result.trashed_conversation_ids,
        deleted_message_ids=result.deleted_message_ids,
    )


@router.get("/message-tree/{message_id}/children", response_model=list[MessageTreeNode])
def list_message_tree_children(
    message_id: str, user: CurrentUser, db: Session = Depends(get_db)
):
    include_unowned = bool(user.is_admin)
    msg = mt.get_message_any_active(
        db, message_id, user_id=user.id, include_unowned=include_unowned
    )
    if msg is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    require_owned_conversation(db, msg.conversation_id, user)
    return [
        _to_schema(n)
        for n in mt.list_child_nodes(
            db, message_id, user_id=user.id, include_unowned=include_unowned
        )
    ]
