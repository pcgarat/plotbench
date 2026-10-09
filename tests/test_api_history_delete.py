"""API POST /api/message-tree/delete."""
from app import crud


def test_api_delete_root_conversation_goes_to_trash(client, db_session):
    origin = crud.create_conversation(db_session, title="Raiz", model_id="m")
    crud.add_message(db_session, origin.id, "user", "p1")
    a1 = crud.add_message(db_session, origin.id, "assistant", "r1")

    r = client.post("/api/message-tree/delete", json={"message_ids": [a1.id]})
    assert r.status_code == 200
    body = r.json()
    assert origin.id in body["trashed_conversation_ids"]
    assert body["deleted_message_ids"] == []
    assert client.get("/api/message-tree/roots").json()["total"] == 0
    deleted = client.get("/api/conversations/deleted").json()
    assert any(c["id"] == origin.id for c in deleted)


def test_api_delete_fork_keeps_origin(client, db_session):
    origin = crud.create_conversation(db_session, title="Origen", model_id="m")
    crud.add_message(db_session, origin.id, "user", "p1")
    a1 = crud.add_message(db_session, origin.id, "assistant", "r1")
    child = crud.fork_conversation(db_session, origin.id, a1.id)
    crud.add_message(db_session, child.id, "user", "fq1")
    fa1 = crud.add_message(db_session, child.id, "assistant", "fr1")
    crud.add_message(db_session, child.id, "user", "fq2")
    fa2 = crud.add_message(db_session, child.id, "assistant", "fr2")
    origin_id, a1_id, fa1_id, fa2_id = origin.id, a1.id, fa1.id, fa2.id

    r = client.post("/api/message-tree/delete", json={"message_ids": [fa2_id]})
    assert r.status_code == 200
    body = r.json()
    assert origin_id not in body["trashed_conversation_ids"]
    assert fa2_id in body["deleted_message_ids"]

    roots = client.get("/api/message-tree/roots").json()
    assert any(it["id"] == a1_id for it in roots["items"])
    kids = client.get(f"/api/message-tree/{a1_id}/children").json()
    assert [k["id"] for k in kids] == [fa1_id]


def test_api_delete_empty_list_is_400(client):
    r = client.post("/api/message-tree/delete", json={"message_ids": []})
    assert r.status_code == 400
