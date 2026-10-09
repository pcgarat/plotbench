"""Contrato de GET /api/messages/list y /api/messages/models (panel de mensajes)."""

from datetime import datetime, timedelta

from app.models import Conversation, IllustratedImage, Message


def _page(client, **params):
    r = client.get("/api/messages/list", params=params or None)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["items"], list)
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert "models" in body
    return body


def _conv(db, title="Conv", provider="ollama", model_id="llama3.2", kind=Conversation.KIND_CHAT):
    conv = Conversation(title=title, provider=provider, model_id=model_id, kind=kind)
    db.add(conv)
    db.commit()
    return conv


def _msg(db, conv, content, *, created_at=None, role="assistant", parent_id=None):
    msg = Message(
        conversation_id=conv.id,
        role=role,
        content=content,
        parent_id=parent_id,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    return msg


def test_list_messages_empty(client):
    body = _page(client)
    assert body["items"] == []
    assert body["total"] == 0
    assert body["models"] == []
    assert body["search_in"] is None


def test_list_messages_returns_title_date_and_metrics(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "Hola, mundo. Adiós.")

    body = _page(client)
    assert body["total"] == 1
    item = body["items"][0]
    assert item["title"] == "Hola mundo"
    assert item["conversation_id"] == conv.id
    assert item["created_at"]
    assert item["model_id"] == "llama3.2"
    assert item["provider"] == "ollama"
    assert item["content"] == "Hola, mundo. Adiós."
    assert item["length"] == len("Hola, mundo. Adiós.")
    assert item["photo_count"] == 0


def test_list_messages_persists_title_on_add(client, db_session):
    """El título se persiste en la fila (no se recalcula en cada petición)."""
    from app import crud

    conv = _conv(db_session)
    msg = crud.add_message(db_session, conv.id, "assistant", "El faro azul. Y más.")
    db_session.expire_all()
    stored = db_session.query(Message).filter(Message.id == msg.id).one()
    assert stored.title == "El faro azul"


def test_list_messages_excludes_non_assistant_and_trashed_and_generator(client, db_session):
    conv = _conv(db_session, title="Activa")
    _msg(db_session, conv, "respuesta viva")
    _msg(db_session, conv, "pregunta usuario", role="user", parent_id=None)
    trashed = _conv(db_session, title="Papelera")
    _msg(db_session, trashed, "respuesta en papelera")
    generator = _conv(db_session, title="txt2img", kind=Conversation.KIND_PROMPT_GENERATOR)
    _msg(db_session, generator, "prompt del generador")
    trashed.deleted_at = datetime.utcnow()
    db_session.commit()

    body = _page(client)
    titles = [it["title"] for it in body["items"]]
    assert body["total"] == 1
    assert "respuesta viva" in titles
    assert "pregunta" not in titles
    assert "respuesta en papelera" not in titles
    assert "prompt del generador" not in titles


def test_list_messages_search_title_only_default(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "El unicornio azul. Nada más.")
    _msg(db_session, conv, "El faro antiguo. Había un unicornio escondido.")

    body = _page(client, q="unicornio")
    assert body["search_in"] == "title"
    assert body["total"] == 1
    assert body["items"][0]["title"] == "El unicornio azul"


def test_list_messages_search_both_includes_body_hits(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "El unicornio azul. Nada más.")
    _msg(db_session, conv, "El faro antiguo. Había un unicornio escondido.")

    body = _page(client, q="unicornio", search_in="both")
    assert body["search_in"] == "both"
    assert body["total"] == 2


def test_list_messages_search_blank_is_unfiltered(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "uno")
    body = _page(client, q="   ")
    assert body["search_in"] is None
    assert body["total"] == 1


def test_list_messages_sort_by_title(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "Zeta final. x")
    _msg(db_session, conv, "Alfa inicio. x")
    _msg(db_session, conv, "Mono medio. x")

    body = _page(client, sort="title")
    assert [it["title"] for it in body["items"]] == ["Alfa inicio", "Mono medio", "Zeta final"]


def test_list_messages_sort_by_date_desc(client, db_session):
    conv = _conv(db_session)
    now = datetime.utcnow()
    _msg(db_session, conv, "viejo", created_at=now - timedelta(hours=2))
    _msg(db_session, conv, "nuevo", created_at=now)

    body = _page(client, sort="date")
    assert [it["title"] for it in body["items"]] == ["nuevo", "viejo"]


def test_list_messages_sort_by_date_asc(client, db_session):
    conv = _conv(db_session)
    now = datetime.utcnow()
    _msg(db_session, conv, "viejo", created_at=now - timedelta(hours=2))
    _msg(db_session, conv, "nuevo", created_at=now)

    body = _page(client, sort="date", direction="asc")
    assert [it["title"] for it in body["items"]] == ["viejo", "nuevo"]


def test_list_messages_sort_by_title_asc(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "Zeta final. x")
    _msg(db_session, conv, "Alfa inicio. x")
    _msg(db_session, conv, "Mono medio. x")

    body = _page(client, sort="title", direction="asc")
    assert [it["title"] for it in body["items"]] == ["Alfa inicio", "Mono medio", "Zeta final"]


def test_list_messages_sort_by_title_desc(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "Zeta final. x")
    _msg(db_session, conv, "Alfa inicio. x")
    _msg(db_session, conv, "Mono medio. x")

    body = _page(client, sort="title", direction="desc")
    assert [it["title"] for it in body["items"]] == ["Zeta final", "Mono medio", "Alfa inicio"]


def test_list_messages_sort_by_length_asc(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "corto")
    _msg(db_session, conv, "una respuesta bastante más larga que la anterior")

    body = _page(client, sort="length", direction="asc")
    assert body["items"][0]["length"] < body["items"][1]["length"]


def test_list_messages_invalid_direction_is_422(client):
    r = client.get("/api/messages/list", params={"sort": "date", "direction": "sideways"})
    assert r.status_code == 422


def test_list_messages_sort_by_length(client, db_session):
    conv = _conv(db_session)
    _msg(db_session, conv, "corto")
    _msg(db_session, conv, "una respuesta bastante más larga que la anterior")

    body = _page(client, sort="length")
    assert body["items"][0]["length"] > body["items"][1]["length"]


def test_list_messages_sort_by_photos(client, db_session):
    conv = _conv(db_session)
    no_photo = _msg(db_session, conv, "sin foto")
    one_photo = _msg(db_session, conv, "con una foto")
    many = _msg(db_session, conv, "con muchas fotos")
    for i in range(3):
        db_session.add(
            IllustratedImage(
                message_id=many.id,
                filename=f"many_{i}.jpg",
                mode="txt2img",
                params_json="{}",
            )
        )
    db_session.add(
        IllustratedImage(
            message_id=one_photo.id,
            filename="one.jpg",
            mode="txt2img",
            params_json="{}",
        )
    )
    db_session.commit()

    body = _page(client, sort="photos")
    ids = [it["id"] for it in body["items"]]
    assert ids[0] == many.id
    assert ids[1] == one_photo.id
    assert ids[2] == no_photo.id
    assert body["items"][0]["photo_count"] == 3


def test_list_messages_filter_by_model(client, db_session):
    a = _conv(db_session, provider="ollama", model_id="llama3.2")
    b = _conv(db_session, provider="openai", model_id="gpt-4o")
    _msg(db_session, a, "de llama")
    _msg(db_session, b, "de gpt")

    body = _page(client, model_id="llama3.2")
    assert body["total"] == 1
    assert body["items"][0]["title"] == "de llama"


def test_list_messages_exposes_generating_models_only(client, db_session):
    a = _conv(db_session, provider="ollama", model_id="llama3.2")
    b = _conv(db_session, provider="openai", model_id="gpt-4o")
    _conv(db_session, provider="ollama", model_id="sin-mensajes")
    _msg(db_session, a, "uno")
    _msg(db_session, a, "dos")
    _msg(db_session, b, "tres")

    body = _page(client, limit=1)  # models no debe depender de la página
    models = {(m["provider"], m["model_id"]): m["count"] for m in body["models"]}
    assert models == {("ollama", "llama3.2"): 2, ("openai", "gpt-4o"): 1}
    assert ("ollama", "sin-mensajes") not in models


def test_list_messages_models_endpoint(client, db_session):
    a = _conv(db_session, provider="ollama", model_id="llama3.2")
    _msg(db_session, a, "uno")
    r = client.get("/api/messages/models")
    assert r.status_code == 200
    assert r.json() == [{"provider": "ollama", "model_id": "llama3.2", "count": 1}]


def test_list_messages_models_stay_complete_when_filtering_by_model(client, db_session):
    """El selector de modelos debe seguir ofreciendo todos los generadores al filtrar."""
    a = _conv(db_session, provider="ollama", model_id="llama3.2")
    b = _conv(db_session, provider="openai", model_id="gpt-4o")
    _msg(db_session, a, "de llama")
    _msg(db_session, b, "de gpt")

    body = _page(client, model_id="llama3.2")
    assert body["total"] == 1
    models = {(m["provider"], m["model_id"]) for m in body["models"]}
    assert ("openai", "gpt-4o") in models
    assert ("ollama", "llama3.2") in models


def test_list_messages_pagination_slices(client, db_session):
    conv = _conv(db_session)
    now = datetime.utcnow()
    for i in range(5):
        _msg(db_session, conv, f"unica{i}", created_at=now + timedelta(minutes=i))

    first = _page(client, limit=2, offset=0)
    assert first["total"] == 5
    assert len(first["items"]) == 2
    second = _page(client, limit=2, offset=2)
    assert len(second["items"]) == 2
    assert {it["id"] for it in first["items"]}.isdisjoint({it["id"] for it in second["items"]})


def test_list_messages_invalid_sort_is_422(client):
    r = client.get("/api/messages/list", params={"sort": "activity"})
    assert r.status_code == 422
