"""Tests de los endpoints de conversaciones y mensajes."""
import pytest
from unittest.mock import patch, MagicMock

from app.routers.api_conversations import _build_llm_messages


def _mock_conv(system_instruction_global="Instrucciones", history_turns=None, model_id="llama3.2", provider="ollama"):
    """Convierte objeto con system_instruction_global y opcional history_turns (pares en el prompt)."""
    c = MagicMock()
    c.system_instruction_global = system_instruction_global
    c.history_turns = history_turns
    c.model_id = model_id
    c.provider = provider
    return c


def _mock_msg(role: str, content: str):
    """Objeto mensaje con role y content."""
    m = MagicMock()
    m.role = role
    m.content = content
    return m


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_estructura_basica(mock_settings):
    """Estructura: system, historial (si hay), user con prompt actual."""
    conv = _mock_conv("Global.", history_turns=10)
    existing = []
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "Hola", None, db, rag_context=None)
    assert len(msgs) >= 1
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Hola"
    assert msgs[0]["role"] == "system"
    assert "Global." in msgs[0]["content"]


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_no_envia_html_de_ilustracion(mock_settings):
    """El historial no debe incluir imgs de ilustración: el LLM las copia y rompe las fotos."""
    conv = _mock_conv("Global.", history_turns=2)
    existing = [
        _mock_msg("user", "M1"),
        _mock_msg(
            "assistant",
            'Había un faro.\n<img src="/api/illustrated-images/aaa_s1.jpg" class="chat-illustration" />\nEl mar.',
        ),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "M2", None, db, rag_context=None)
    assistant = next(m for m in msgs if m["role"] == "assistant")
    assert "<img" not in assistant["content"]
    assert "illustrated-images" not in assistant["content"]
    assert "Había un faro." in assistant["content"]
    assert "El mar." in assistant["content"]


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_incluye_historial_orden_cronologico(mock_settings):
    """El historial va de más antiguo a más nuevo antes del prompt actual."""
    conv = _mock_conv("Global.", history_turns=2)
    existing = [
        _mock_msg("user", "M1"),
        _mock_msg("assistant", "R1"),
        _mock_msg("user", "M2"),
        _mock_msg("assistant", "R2"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "M3", None, db, rag_context=None)
    # system, user, assistant, user, assistant, user (actual)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "M1"
    assert msgs[2]["role"] == "assistant" and msgs[2]["content"] == "R1"
    assert msgs[3]["role"] == "user" and msgs[3]["content"] == "M2"
    assert msgs[4]["role"] == "assistant" and msgs[4]["content"] == "R2"
    assert msgs[5]["role"] == "user" and msgs[5]["content"] == "M3"


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_limita_ultimos_n_pares(mock_settings):
    """Solo se envían los últimos N pares (N=2 => 4 mensajes de historial)."""
    conv = _mock_conv("Global.", history_turns=2)
    existing = [
        _mock_msg("user", "M1"),
        _mock_msg("assistant", "R1"),
        _mock_msg("user", "M2"),
        _mock_msg("assistant", "R2"),
        _mock_msg("user", "M3"),
        _mock_msg("assistant", "R3"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "M4", None, db, rag_context=None)
    # system + 4 historial (M2,R2,M3,R3) + 1 actual = 6 mensajes + system
    hist = [m for m in msgs if m["role"] in ("user", "assistant")]
    assert len(hist) == 5  # 4 historial + 1 actual
    assert hist[0]["content"] == "M2"
    assert hist[1]["content"] == "R2"
    assert hist[2]["content"] == "M3"
    assert hist[3]["content"] == "R3"
    assert hist[4]["content"] == "M4"


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_sin_historial_cuando_turns_0(mock_settings):
    """Si history_turns=0, no se envía historial."""
    conv = _mock_conv("Global.", history_turns=0)
    existing = [
        _mock_msg("user", "M1"),
        _mock_msg("assistant", "R1"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "M2", None, db, rag_context=None)
    assert len(msgs) == 2  # system + user actual
    assert msgs[-1]["content"] == "M2"


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_menos_de_n_pares_envia_todos(mock_settings):
    """Si hay menos mensajes que N pares, se envían todos."""
    conv = _mock_conv("Global.", history_turns=10)
    existing = [
        _mock_msg("user", "M1"),
        _mock_msg("assistant", "R1"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "M2", None, db, rag_context=None)
    hist = [m for m in msgs if m["role"] in ("user", "assistant")]
    assert len(hist) == 3  # M1, R1, M2
    assert hist[0]["content"] == "M1"
    assert hist[1]["content"] == "R1"
    assert hist[2]["content"] == "M2"


def test_create_conversation(client):
    r = client.post(
        "/api/conversations",
        json={
            "title": "Mi chat",
            "model_id": "llama3.2",
            "system_instruction_global": "Responde breve.",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Mi chat"
    assert data["model_id"] == "llama3.2"
    assert data["system_instruction_global"] == "Responde breve."
    assert "id" in data
    assert data["messages"] == []


def test_create_conversation_defaults(client):
    r = client.post("/api/conversations", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Nueva conversación"
    assert data["model_id"] == "llama3.2"
    assert data["system_instruction_global"] is None
    assert data["auto_title"] is False


def test_list_conversations_empty(client):
    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == []


def test_list_conversations_after_create(client):
    client.post("/api/conversations", json={"title": "A", "model_id": "m1"})
    client.post("/api/conversations", json={"title": "B", "model_id": "m2"})
    r = client.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    titles = [c["title"] for c in data]
    assert "A" in titles and "B" in titles
    assert all("created_at" in c for c in data)


def test_list_conversations_sort_created_at_ignores_later_activity(client, db_session):
    from datetime import datetime, timedelta

    from app.models import Conversation

    now = datetime.utcnow()
    older = Conversation(
        title="Antigua",
        model_id="m",
        created_at=now - timedelta(days=5),
        updated_at=now,
        last_message_at=now,
    )
    newer = Conversation(
        title="Nueva",
        model_id="m",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(days=2),
        last_message_at=now - timedelta(days=2),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    by_activity = client.get("/api/conversations").json()
    assert [c["title"] for c in by_activity] == ["Antigua", "Nueva"]

    by_created = client.get("/api/conversations", params={"sort": "created_at"}).json()
    assert [c["title"] for c in by_created] == ["Nueva", "Antigua"]
    assert by_created[0]["created_at"] > by_created[1]["created_at"]


def test_list_conversations_invalid_sort_is_422(client):
    r = client.get("/api/conversations", params={"sort": "image"})
    assert r.status_code == 422


def test_get_conversation_404(client):
    r = client.get("/api/conversations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert "no encontrada" in r.json()["detail"].lower()


def test_get_conversation_ok(client):
    create = client.post("/api/conversations", json={"title": "Test", "model_id": "m"})
    cid = create.json()["id"]
    r = client.get(f"/api/conversations/{cid}")
    assert r.status_code == 200
    assert r.json()["title"] == "Test"
    assert r.json()["messages"] == []
    assert "model_params" in r.json()
    assert r.json()["model_params"] is None


def test_update_conversation_ok(client):
    create = client.post("/api/conversations", json={"title": "Antes", "model_id": "m1"})
    cid = create.json()["id"]
    r = client.put(
        f"/api/conversations/{cid}",
        json={"title": "Después", "model_id": "m2", "system_instruction_global": "Sé breve."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Después"
    assert data["model_id"] == "m2"
    assert data["system_instruction_global"] == "Sé breve."


def test_update_and_get_conversation_model_params(client):
    create = client.post("/api/conversations", json={"title": "Params", "model_id": "m"})
    cid = create.json()["id"]
    params = {"temperature": 0.7, "num_ctx": 4096}
    r = client.put(f"/api/conversations/{cid}", json={"model_params": params})
    assert r.status_code == 200
    assert r.json()["model_params"] == params
    get_r = client.get(f"/api/conversations/{cid}")
    assert get_r.status_code == 200
    assert get_r.json()["model_params"] == params


def test_conversation_images_persist_across_get(client):
    """PUT images en la conversación y GET tras 'recarga' lo devuelve (como el resto de ajustes)."""
    create = client.post("/api/conversations", json={"title": "Imágenes", "model_id": "m"})
    cid = create.json()["id"]
    assert create.json().get("images") is None
    payload = {
        "enabled": True,
        "use_chat_config": False,
        "images_per_response": 4,
        "batch_size": 8,
        "retries": 2,
        "prompt": "cinematic still",
        "prompt_system_instructions": [{"title": "Estilo", "content": "luz dura"}],
        "prompt_provider": "ollama",
        "prompt_model": "llama3.2",
        "prompt_model_params": {"think": False, "temperature": 0.5, "num_ctx": 16384},
        "steps": 28,
        "width": 768,
        "height": 1024,
        "seed": -1,
        "debug": True,
    }
    r = client.put(f"/api/conversations/{cid}", json={"images": payload})
    assert r.status_code == 200
    images = r.json()["images"]
    assert images["enabled"] is True
    assert images["prompt"] == "cinematic still"
    assert images["images_per_response"] == 4
    assert images["steps"] == 28
    assert images["width"] == 768
    assert images["prompt_model"] == "llama3.2"
    assert images["prompt_model_params"]["temperature"] == 0.5
    assert images["prompt_model_params"]["think"] is False
    assert images.get("prompt_system_instructions") in (None, [])
    assert images["visual_consistency"] is True
    assert "debug" not in images
    get_r = client.get(f"/api/conversations/{cid}")
    assert get_r.status_code == 200
    assert get_r.json()["images"]["enabled"] is True
    assert get_r.json()["images"]["prompt"] == "cinematic still"
    assert get_r.json()["images"]["seed"] == -1
    other = client.put(f"/api/conversations/{cid}", json={"title": "Sigue con imágenes"})
    assert other.status_code == 200
    assert other.json()["title"] == "Sigue con imágenes"
    assert other.json()["images"]["prompt"] == "cinematic still"


def test_conversation_images_drop_planner_rules(client):
    """Las reglas del planificador son globales: no se persisten en la conversación."""
    create = client.post("/api/conversations", json={"title": "Reglas globales", "model_id": "m"})
    cid = create.json()["id"]
    r = client.put(
        f"/api/conversations/{cid}",
        json={
            "images": {
                "enabled": True,
                "prompt": "film still",
                "prompt_system_instructions": [
                    {"title": "Estilo", "content": "luz dura", "rule_id": "pr1"}
                ],
            }
        },
    )
    assert r.status_code == 200
    images = r.json()["images"]
    assert images["prompt"] == "film still"
    assert images.get("prompt_system_instructions") in (None, [])
    got = client.get(f"/api/conversations/{cid}")
    assert got.json()["images"].get("prompt_system_instructions") in (None, [])


def test_conversation_history_turns(client):
    """GET incluye history_turns; PUT con history_turns persiste y GET lo devuelve."""
    create = client.post("/api/conversations", json={"title": "Turns", "model_id": "m"})
    cid = create.json()["id"]
    get_r = client.get(f"/api/conversations/{cid}")
    assert get_r.status_code == 200
    assert "history_turns" in get_r.json()
    r = client.put(f"/api/conversations/{cid}", json={"history_turns": 3})
    assert r.status_code == 200
    assert r.json().get("history_turns") == 3
    get_r = client.get(f"/api/conversations/{cid}")
    assert get_r.json().get("history_turns") == 3


def test_conversation_system_instructions(client):
    """Crear y actualizar conversación con system_instructions (lista de reglas con título y contenido)."""
    create = client.post(
        "/api/conversations",
        json={
            "title": "Reglas",
            "model_id": "m",
            "system_instructions": [
                {"title": "R1", "content": "Regla A"},
                {"title": "R2", "content": "Regla B"},
            ],
        },
    )
    assert create.status_code == 200
    data = create.json()
    instructions = data.get("system_instructions") or []
    assert len(instructions) == 2
    assert instructions[0]["title"] == "R1" and instructions[0]["content"] == "Regla A"
    assert instructions[1]["title"] == "R2" and instructions[1]["content"] == "Regla B"
    cid = data["id"]
    r = client.put(
        f"/api/conversations/{cid}",
        json={"system_instructions": [{"title": "Solo", "content": "Solo una"}]},
    )
    assert r.status_code == 200
    put_instructions = r.json().get("system_instructions") or []
    assert len(put_instructions) == 1 and put_instructions[0]["title"] == "Solo" and put_instructions[0]["content"] == "Solo una"
    get_r = client.get(f"/api/conversations/{cid}")
    get_instructions = get_r.json().get("system_instructions") or []
    assert len(get_instructions) == 1 and get_instructions[0]["title"] == "Solo" and get_instructions[0]["content"] == "Solo una"


def test_conversation_system_instructions_clear(client):
    """PUT con system_instructions: [] vacía la lista y persiste (GET tras recarga devuelve vacío)."""
    create = client.post(
        "/api/conversations",
        json={
            "title": "Vaciar reglas",
            "model_id": "m",
            "system_instructions": [{"title": "Una", "content": "Contenido"}],
        },
    )
    assert create.status_code == 200
    cid = create.json()["id"]
    assert len(create.json().get("system_instructions") or []) == 1
    r = client.put(f"/api/conversations/{cid}", json={"system_instructions": []})
    assert r.status_code == 200
    assert (r.json().get("system_instructions") or []) == []
    get_r = client.get(f"/api/conversations/{cid}")
    get_instructions = get_r.json().get("system_instructions") or []
    assert get_instructions == [], "Al recargar, system_instructions debe seguir vacío"


def test_update_conversation_404(client):
    r = client.put(
        "/api/conversations/00000000-0000-0000-0000-000000000000",
        json={"title": "X"},
    )
    assert r.status_code == 404


def test_delete_conversation_ok(client):
    create = client.post("/api/conversations", json={"title": "Borrar", "model_id": "m"})
    cid = create.json()["id"]
    r = client.delete(f"/api/conversations/{cid}")
    assert r.status_code == 204
    get_r = client.get(f"/api/conversations/{cid}")
    assert get_r.status_code == 404


def test_delete_conversation_404(client):
    r = client.delete("/api/conversations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@patch("app.routers.api_conversations.get_provider")
def test_clear_conversation_messages(mock_get_provider, client):
    """Limpiar historial borra mensajes pero mantiene la conversación y sus instrucciones."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta."
    mock_get_provider.return_value = mock_provider
    create = client.post(
        "/api/conversations",
        json={"title": "Conv", "model_id": "m", "system_instruction_global": "Mis instrucciones."},
    )
    cid = create.json()["id"]
    # Enviar un mensaje
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Hola"})
    # Verificar que hay mensajes
    conv = client.get(f"/api/conversations/{cid}").json()
    assert len(conv["messages"]) == 2
    # Limpiar historial
    r = client.delete(f"/api/conversations/{cid}/messages")
    assert r.status_code == 204
    # Verificar que no hay mensajes pero sí conversación con instrucciones
    conv = client.get(f"/api/conversations/{cid}").json()
    assert len(conv["messages"]) == 0
    assert conv["system_instruction_global"] == "Mis instrucciones."
    assert conv["title"] == "Conv"


def test_clear_conversation_messages_404(client):
    r = client.delete("/api/conversations/00000000-0000-0000-0000-000000000000/messages")
    assert r.status_code == 404


@patch("app.routers.api_conversations.get_provider")
@patch("app.routers.api_conversations.rag.delete_message_document")
def test_delete_last_message_204(mock_rag_delete, mock_get_provider, client):
    """DELETE last mensaje devuelve 204 y elimina el último mensaje."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta"
    mock_get_provider.return_value = mock_provider
    create = client.post("/api/conversations", json={"title": "Conv", "model_id": "m"})
    cid = create.json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Uno"})
    r = client.delete(f"/api/conversations/{cid}/messages/last")
    assert r.status_code == 204
    conv = client.get(f"/api/conversations/{cid}").json()
    # Solo queda el mensaje user; el último (assistant) fue eliminado
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "Uno"


def test_delete_last_message_404(client):
    """DELETE last cuando no hay mensajes devuelve 404."""
    create = client.post("/api/conversations", json={"title": "Conv", "model_id": "m"})
    cid = create.json()["id"]
    r = client.delete(f"/api/conversations/{cid}/messages/last")
    assert r.status_code == 404
    assert "no hay mensajes" in r.json()["detail"].lower()


@patch("app.routers.api_conversations.get_provider")
@patch("app.routers.api_conversations.rag.delete_message_document")
def test_delete_message_by_id_204(mock_rag_delete, mock_get_provider, client):
    """DELETE message por id devuelve 204 y elimina ese mensaje."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta"
    mock_get_provider.return_value = mock_provider
    create = client.post("/api/conversations", json={"title": "Conv", "model_id": "m"})
    cid = create.json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Uno"})
    conv = client.get(f"/api/conversations/{cid}").json()
    msg_id = conv["messages"][0]["id"]
    r = client.delete(f"/api/conversations/{cid}/messages/{msg_id}")
    assert r.status_code == 204
    conv2 = client.get(f"/api/conversations/{cid}").json()
    # Queda solo el mensaje assistant
    assert len(conv2["messages"]) == 1
    assert conv2["messages"][0]["role"] == "assistant"
    mock_rag_delete.assert_called_once_with(cid, msg_id)


def test_delete_message_by_id_404(client):
    """DELETE message con id inexistente devuelve 404."""
    create = client.post("/api/conversations", json={"title": "Conv", "model_id": "m"})
    cid = create.json()["id"]
    r = client.delete(f"/api/conversations/{cid}/messages/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert "mensaje" in r.json()["detail"].lower()


@patch("app.routers.api_conversations.rag.delete_message_document")
def test_delete_message_removes_embedded_photo_files(mock_rag_delete, client, db_session, tmp_path, monkeypatch):
    """Al borrar un mensaje se eliminan del disco las fotos incrustadas si nadie más las referencia."""
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("s1", b"\x89PNG\r\n\x1a\n")
    conv = crud.create_conversation(db_session, title="Fotos", model_id="m")
    content = f'Texto\n<img src="/api/illustrated-images/{name}" class="chat-illustration" />'
    msg = crud.add_message(db_session, conv.id, "assistant", content)
    crud.save_illustrated_image_meta(
        db_session,
        message_id=msg.id,
        filename=name,
        scene_id="s1",
        mode="txt2img",
        params={"prompt": "x"},
    )

    r = client.delete(f"/api/conversations/{conv.id}/messages/{msg.id}")
    assert r.status_code == 204
    assert storage.resolve_illustrated_path(name) is None
    assert crud.get_illustrated_image_meta(db_session, name) is None
    mock_rag_delete.assert_called_once_with(conv.id, msg.id)


@patch("app.routers.api_conversations.rag.delete_message_document")
def test_delete_message_keeps_photo_if_still_referenced(mock_rag_delete, client, db_session, tmp_path, monkeypatch):
    """No borra el fichero si otro mensaje sigue incrustando la misma foto."""
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("shared", b"\x89PNG\r\n\x1a\n")
    img = f'<img src="/api/illustrated-images/{name}" class="chat-illustration" />'
    conv = crud.create_conversation(db_session, title="Share", model_id="m")
    msg_a = crud.add_message(db_session, conv.id, "assistant", f"A\n{img}")
    crud.add_message(db_session, conv.id, "assistant", f"B\n{img}")

    r = client.delete(f"/api/conversations/{conv.id}/messages/{msg_a.id}")
    assert r.status_code == 204
    assert storage.resolve_illustrated_path(name) is not None
    mock_rag_delete.assert_called_once()


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_incluye_rag_context(mock_settings):
    """Si hay rag_context se incluye en el system message."""
    conv = _mock_conv("Global.", history_turns=10)
    db = MagicMock()
    msgs, _ = _build_llm_messages(
        conv, [], "Hola", None, db, system_instruction_global=None, rag_context="Contexto RAG aquí."
    )
    assert msgs[0]["role"] == "system"
    assert "Contexto relevante del historial" in msgs[0]["content"]
    assert "Contexto RAG aquí." in msgs[0]["content"]
    assert "Global." in msgs[0]["content"]


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_gemma_omite_thought_previo(mock_settings):
    """omit_prior_thinking del contrato Gemma: el historial assistant no reenvía bloques thought."""
    conv = _mock_conv("Global.", history_turns=2, model_id="gemma4:31b-cloud")
    existing = [
        _mock_msg("user", "¿2+2?"),
        _mock_msg("assistant", "<think>cuento con los dedos</think>\n4"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "¿3+3?", None, db, rag_context=None)
    assistant = next(m for m in msgs if m["role"] == "assistant")
    assert assistant["content"] == "4"
    assert "<think>" not in assistant["content"]
    assert "thinking" not in assistant


@patch("app.routers.api_conversations.settings")
def test_build_llm_messages_sin_quirk_conserva_thought_en_content(mock_settings):
    """Modelo sin overlay/quirk: el builder no reescribe bloques thought del historial."""
    conv = _mock_conv("Global.", history_turns=2, model_id="llama3.2")
    existing = [
        _mock_msg("user", "¿2+2?"),
        _mock_msg("assistant", "<think>cuento</think>\n4"),
    ]
    db = MagicMock()
    msgs, _ = _build_llm_messages(conv, existing, "¿3+3?", None, db, rag_context=None)
    assistant = next(m for m in msgs if m["role"] == "assistant")
    assert "<think>cuento</think>" in assistant["content"]
    assert "4" in assistant["content"]


@patch("app.routers.api_conversations.get_provider")
def test_send_message_ok(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Hola, soy el asistente."
    mock_get_provider.return_value = mock_provider
    create = client.post("/api/conversations", json={"title": "Chat", "model_id": "llama3.2"})
    cid = create.json()["id"]

    r = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Hola", "instruction_override": None},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "assistant"
    assert data["content"] == "Hola, soy el asistente."
    mock_provider.chat.assert_called_once()
    call_messages = mock_provider.chat.call_args[0][1]
    assert call_messages[-1]["role"] == "user"
    assert call_messages[-1]["content"] == "Hola"

    # Historial: la conversación tiene 2 mensajes (user + assistant)
    get_conv = client.get(f"/api/conversations/{cid}")
    assert len(get_conv.json()["messages"]) == 2
    assert get_conv.json()["messages"][0]["content"] == "Hola"
    assert get_conv.json()["messages"][1]["content"] == "Hola, soy el asistente."


@patch("app.routers.api_conversations.build_extra_body")
@patch("app.routers.api_conversations.get_provider")
def test_send_message_pasa_model_id_a_build_extra_body(mock_get_provider, mock_extra, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "ok"
    mock_get_provider.return_value = mock_provider
    mock_extra.return_value = {"think": "max"}
    cid = client.post(
        "/api/conversations",
        json={"title": "Chat", "model_id": "deepseek-v4-flash:cloud", "provider": "ollama"},
    ).json()["id"]
    r = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Hola", "model_params": {"think": "max"}},
    )
    assert r.status_code == 200
    mock_extra.assert_called_once()
    assert mock_extra.call_args.kwargs.get("model_id") == "deepseek-v4-flash:cloud"


@patch("app.routers.api_conversations.get_provider")
def test_send_message_strips_illustration_html_del_llm(mock_get_provider, client):
    """El LLM no puede persistir imgs de ilustración: salen rotas y sin metadatos."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = (
        "Había un faro.\n"
        '<img src="/api/illustrated-images/8a4e2f7c9d1b40a58b3c6e1f2d0a8b9_s1.jpg" '
        'alt="escena s1" class="chat-illustration" loading="lazy" />\n'
        "El mar."
    )
    mock_get_provider.return_value = mock_provider
    cid = client.post("/api/conversations", json={"title": "Chat", "model_id": "m"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", json={"content": "Cuenta"})
    assert r.status_code == 200
    assert "<img" not in r.json()["content"]
    assert "illustrated-images" not in r.json()["content"]
    assert "Había un faro." in r.json()["content"]
    assert "El mar." in r.json()["content"]
    stored = client.get(f"/api/conversations/{cid}").json()["messages"][1]["content"]
    assert "<img" not in stored


@patch("app.routers.api_conversations.get_provider")
def test_send_message_with_instruction_override(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta breve."
    mock_get_provider.return_value = mock_provider
    create = client.post(
        "/api/conversations",
        json={"title": "Chat", "model_id": "m", "system_instruction_global": "Global."},
    )
    cid = create.json()["id"]

    r = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Dime algo", "instruction_override": "Responde en una frase."},
    )
    assert r.status_code == 200
    call_messages = mock_provider.chat.call_args[0][1]
    # System: reglas (global). Luego user (prompt) y user (instruction_override) en último lugar.
    system_msgs = [m for m in call_messages if m["role"] == "system"]
    assert len(system_msgs) >= 1
    assert any("Global." in m["content"] for m in system_msgs)
    assert call_messages[-2]["role"] == "user" and call_messages[-2]["content"] == "Dime algo"
    assert call_messages[-1]["role"] == "user" and call_messages[-1]["content"] == "Responde en una frase."


def test_send_message_404(client):
    r = client.post(
        "/api/conversations/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "Hola"},
    )
    assert r.status_code == 404


def test_send_message_content_required(client):
    create = client.post("/api/conversations", json={"title": "C", "model_id": "m"})
    cid = create.json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", json={"content": ""})
    assert r.status_code == 422


@patch("app.routers.api_conversations.get_provider")
def test_send_message_provider_error(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ConnectionError("Connection refused")
    mock_get_provider.return_value = mock_provider
    create = client.post("/api/conversations", json={"title": "C", "model_id": "m"})
    cid = create.json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", json={"content": "Hola"})
    assert r.status_code == 502
    assert "ollama" in r.json()["detail"].lower()


@patch("app.routers.api_conversations.rag.add_message")
@patch("app.routers.api_conversations.rag.get_relevant_context")
@patch("app.routers.api_conversations.get_provider")
def test_send_message_calls_rag_get_context_and_add(mock_get_provider, mock_rag_context, mock_rag_add, client):
    """Al enviar un mensaje se llama a get_relevant_context y a add_message solo para el mensaje user."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta."
    mock_get_provider.return_value = mock_provider
    mock_rag_context.return_value = ""
    create = client.post("/api/conversations", json={"title": "RAG", "model_id": "m"})
    cid = create.json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Hola"})
    mock_rag_context.assert_called_once()
    assert mock_rag_context.call_args[0][0] == cid
    assert mock_rag_context.call_args[0][1] == "Hola"
    # add_message solo para el mensaje del usuario (no se guardan respuestas del asistente)
    mock_rag_add.assert_called_once()
    assert mock_rag_add.call_args[0][2] == "user"


@patch("app.routers.api_conversations.rag.delete_conversation_documents")
def test_delete_conversation_does_not_call_rag_delete_documents(mock_rag_delete, client):
    """Soft-delete no debe borrar documentos de Chroma (recuperable)."""
    create = client.post("/api/conversations", json={"title": "Borrar RAG", "model_id": "m"})
    cid = create.json()["id"]
    client.delete(f"/api/conversations/{cid}")
    mock_rag_delete.assert_not_called()


@patch("app.routers.api_conversations.get_provider")
def test_send_message_linear_expone_parent_y_hoja(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Ra"
    mock_get_provider.return_value = mock_provider
    cid = client.post("/api/conversations", json={"title": "Árbol", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "A"})
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["active_leaf_message_id"] == conv["messages"][1]["id"]
    assert conv["messages"][0]["parent_id"] is None
    assert conv["messages"][1]["parent_id"] == conv["messages"][0]["id"]


@patch("app.routers.api_conversations.get_provider")
def test_nuevo_intento_no_manda_la_otra_rama_al_llm(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ra", "Rb", "Rc"]
    mock_get_provider.return_value = mock_provider
    cid = client.post("/api/conversations", json={"title": "Intentos", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "A"})
    client.post(f"/api/conversations/{cid}/messages", json={"content": "B"})
    conv = client.get(f"/api/conversations/{cid}").json()
    by_content = {m["content"]: m for m in conv["messages"]}
    ancla = by_content["Ra"]["id"]
    client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "C", "parent_message_id": ancla},
    )
    third_call_messages = mock_provider.chat.call_args_list[2][0][1]
    contents = [m["content"] for m in third_call_messages if m["role"] in ("user", "assistant")]
    assert "A" in contents
    assert "Ra" in contents
    assert "C" in contents
    assert "B" not in contents
    assert "Rb" not in contents
    conv2 = client.get(f"/api/conversations/{cid}").json()
    assert len(conv2["messages"]) == 6
    by_content = {m["content"]: m for m in conv2["messages"]}
    assert by_content["C"]["parent_id"] == ancla
    assert conv2["active_leaf_message_id"] == by_content["Rc"]["id"]


@patch("app.routers.api_conversations.get_provider")
def test_cambiar_hoja_activa_persiste(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ra", "Rb", "Rc"]
    mock_get_provider.return_value = mock_provider
    cid = client.post("/api/conversations", json={"title": "Switch", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "A"})
    client.post(f"/api/conversations/{cid}/messages", json={"content": "B"})
    conv = client.get(f"/api/conversations/{cid}").json()
    ancla = next(m for m in conv["messages"] if m["content"] == "Ra")["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "C", "parent_message_id": ancla})
    conv = client.get(f"/api/conversations/{cid}").json()
    leaf_intento1 = next(m for m in conv["messages"] if m["content"] == "Rb")["id"]
    r = client.put(f"/api/conversations/{cid}", json={"active_leaf_message_id": leaf_intento1})
    assert r.status_code == 200
    assert r.json()["active_leaf_message_id"] == leaf_intento1
    assert client.get(f"/api/conversations/{cid}").json()["active_leaf_message_id"] == leaf_intento1


@patch("app.routers.api_conversations.get_provider")
def test_parent_message_id_inexistente_se_ignora(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Ok"
    mock_get_provider.return_value = mock_provider
    cid = client.post("/api/conversations", json={"title": "Ancla huérfana", "model_id": "m"}).json()["id"]
    r = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Hola", "parent_message_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 200
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["messages"][0]["parent_id"] is None


@patch("app.routers.api_conversations.get_provider")
def test_enviar_en_variante_con_origen_en_papelera(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ra", "Rb"]
    mock_get_provider.return_value = mock_provider
    origin_id = client.post("/api/conversations", json={"title": "Origen", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "A"})
    origin = client.get(f"/api/conversations/{origin_id}").json()
    ancla = origin["messages"][1]["id"]
    child_id = client.post(f"/api/conversations/{origin_id}/fork", json={"message_id": ancla}).json()["id"]
    assert client.delete(f"/api/conversations/{origin_id}").status_code == 204
    child = client.get(f"/api/conversations/{child_id}").json()
    assert [m["content"] for m in child["inherited_messages"]] == ["A", "Ra"]
    r = client.post(f"/api/conversations/{child_id}/messages", json={"content": "B"})
    assert r.status_code == 200
    contents = [m["content"] for m in mock_provider.chat.call_args_list[1][0][1] if m["role"] in ("user", "assistant")]
    assert contents == ["A", "Ra", "B"]


@patch("app.routers.api_conversations.get_provider")
def test_fork_no_copia_mensajes_y_el_llm_usa_prefijo_del_origen(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ra", "Rb", "Rc", "Rd"]
    mock_get_provider.return_value = mock_provider
    origin_id = client.post("/api/conversations", json={"title": "Origen", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "A"})
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "B"})
    origin = client.get(f"/api/conversations/{origin_id}").json()
    ancla = next(m for m in origin["messages"] if m["content"] == "Ra")["id"]
    r_fork = client.post(f"/api/conversations/{origin_id}/fork", json={"message_id": ancla})
    assert r_fork.status_code == 200
    child = r_fork.json()
    assert child["id"] != origin_id
    assert child["forked_from_conversation_id"] == origin_id
    assert child["forked_from_message_id"] == ancla
    assert child["messages"] == []
    assert [m["content"] for m in child["inherited_messages"]] == ["A", "Ra"]
    listed = client.get("/api/conversations").json()
    child_item = next(c for c in listed if c["id"] == child["id"])
    assert child_item["forked_from_conversation_id"] == origin_id
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "C"})
    child_after = client.get(f"/api/conversations/{child['id']}").json()
    assert child_after["messages"] == []
    assert [m["content"] for m in child_after["inherited_messages"]] == ["A", "Ra"]
    client.post(f"/api/conversations/{child['id']}/messages", json={"content": "D"})
    fourth = mock_provider.chat.call_args_list[3][0][1]
    contents = [m["content"] for m in fourth if m["role"] in ("user", "assistant")]
    assert contents == ["A", "Ra", "D"]
    sent = client.get(f"/api/conversations/{child['id']}").json()
    assert [m["content"] for m in sent["messages"]] == ["D", "Rd"]
    assert sent["messages"][0]["parent_id"] is None
    origin_final = client.get(f"/api/conversations/{origin_id}").json()
    assert [m["content"] for m in origin_final["messages"]] == ["A", "Ra", "B", "Rb", "C", "Rc"]


def test_fork_ancla_inexistente_404(client):
    cid = client.post("/api/conversations", json={"title": "Origen", "model_id": "m"}).json()["id"]
    r = client.post(
        f"/api/conversations/{cid}/fork",
        json={"message_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


@patch("app.routers.api_conversations.get_provider")
def test_fork_parent_heredado_en_envio_no_404(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ra", "Rb"]
    mock_get_provider.return_value = mock_provider
    origin_id = client.post("/api/conversations", json={"title": "Origen", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "A"})
    origin = client.get(f"/api/conversations/{origin_id}").json()
    ancla = origin["messages"][1]["id"]
    child_id = client.post(f"/api/conversations/{origin_id}/fork", json={"message_id": ancla}).json()["id"]
    r = client.post(
        f"/api/conversations/{child_id}/messages",
        json={"content": "B", "parent_message_id": ancla},
    )
    assert r.status_code == 200
    second = mock_provider.chat.call_args_list[1][0][1]
    contents = [m["content"] for m in second if m["role"] in ("user", "assistant")]
    assert contents == ["A", "Ra", "B"]


@patch("app.routers.api_conversations.get_provider")
def test_delete_mensaje_heredado_desde_fork_sigue_404(mock_get_provider, client):
    """El borrado no se resuelve al origen: solo mutaciones de contenido son compartidas."""
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Ra"
    mock_get_provider.return_value = mock_provider
    origin_id = client.post("/api/conversations", json={"title": "Origen", "model_id": "m"}).json()["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "A"})
    origin = client.get(f"/api/conversations/{origin_id}").json()
    ancla = origin["messages"][1]["id"]
    child_id = client.post(f"/api/conversations/{origin_id}/fork", json={"message_id": ancla}).json()["id"]
    r = client.delete(f"/api/conversations/{child_id}/messages/{ancla}")
    assert r.status_code == 404
    origin_after = client.get(f"/api/conversations/{origin_id}").json()
    assert any(m["id"] == ancla for m in origin_after["messages"])


def test_create_conversation_acepta_auto_title(client):
    data = client.post("/api/conversations", json={"title": "Manual", "auto_title": True}).json()
    assert data["auto_title"] is True
    assert data["title"] == "Manual"
    listed = client.get("/api/conversations").json()
    assert listed[0]["auto_title"] is True


@patch("app.routers.api_conversations.get_provider")
def test_auto_title_usa_primera_frase_del_ultimo_mensaje(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta del modelo. Segunda frase."
    mock_get_provider.return_value = mock_provider
    cid = client.post(
        "/api/conversations", json={"title": "Manual", "model_id": "m"}
    ).json()["id"]
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Hola, mundo. Extra."})
    before = client.get(f"/api/conversations/{cid}").json()
    assert before["title"] == "Manual"
    r = client.put(f"/api/conversations/{cid}", json={"auto_title": True})
    assert r.status_code == 200
    assert r.json()["auto_title"] is True
    assert r.json()["title"] == "Respuesta del modelo"
    ignored = client.put(f"/api/conversations/{cid}", json={"title": "No pises esto"})
    assert ignored.json()["title"] == "Respuesta del modelo"
    mock_provider.chat.return_value = "¿Otra cosa pasa?"
    client.post(f"/api/conversations/{cid}/messages", json={"content": "Siguiente"})
    after = client.get(f"/api/conversations/{cid}").json()
    assert after["title"] == "Otra cosa pasa"


@patch("app.routers.api_conversations.get_provider")
def test_auto_title_en_fork_usa_el_ancla_no_el_origen_posterior(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["Ancla heredada.", "Después del corte.", "Solo del fork."]
    mock_get_provider.return_value = mock_provider
    origin_id = client.post(
        "/api/conversations", json={"title": "Origen", "model_id": "m", "auto_title": True}
    ).json()["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "A"})
    origin = client.get(f"/api/conversations/{origin_id}").json()
    assert origin["title"] == "Ancla heredada"
    ancla = origin["messages"][1]["id"]
    client.post(f"/api/conversations/{origin_id}/messages", json={"content": "B"})
    origin_after = client.get(f"/api/conversations/{origin_id}").json()
    assert origin_after["title"] == "Después del corte"
    child = client.post(
        f"/api/conversations/{origin_id}/fork", json={"message_id": ancla}
    ).json()
    assert child["auto_title"] is True
    assert child["title"] == "Ancla heredada"
    client.post(f"/api/conversations/{child['id']}/messages", json={"content": "D"})
    child_after = client.get(f"/api/conversations/{child['id']}").json()
    assert child_after["title"] == "Solo del fork"


class _FakeStreamChunk:
    def __init__(self, content="ok"):
        self.type = "content"
        self.content = content
        self.error = None
        self.metadata = None


def _fake_async_stream(*_args, **_kwargs):
    async def _gen():
        yield _FakeStreamChunk()
    return _gen()


@patch("app.routers.api_conversations.get_provider")
def test_stream_con_provider_model_override_persiste_el_usado(mock_get_provider, client):
    """El modelo/proveedor elegidos en la UI viajan en el body y se guardan al enviar."""
    mock_provider = MagicMock()
    mock_provider.chat_stream = _fake_async_stream
    mock_get_provider.return_value = mock_provider
    cid = client.post(
        "/api/conversations", json={"title": "Chat", "model_id": "llama3.2", "provider": "ollama"}
    ).json()["id"]

    r = client.post(
        f"/api/conversations/{cid}/messages/stream",
        json={"content": "Hola", "provider": "mancer", "model": "mistral-large"},
    )
    assert r.status_code == 200
    assert "ok" in r.text
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["provider"] == "mancer"
    assert conv["model_id"] == "mistral-large"
    assert [m["content"] for m in conv["messages"] if m["role"] == "user"] == ["Hola"]
    mock_get_provider.assert_called_with("mancer")


@patch("app.routers.api_conversations.get_provider")
def test_stream_sin_override_respeta_el_modelo_de_la_conversacion(mock_get_provider, client):
    """Regresión: sin provider/model en el body se usa lo persistido en la conversación."""
    mock_provider = MagicMock()
    mock_provider.chat_stream = _fake_async_stream
    mock_get_provider.return_value = mock_provider
    cid = client.post(
        "/api/conversations", json={"title": "Chat", "model_id": "llama3.2", "provider": "ollama"}
    ).json()["id"]

    r = client.post(f"/api/conversations/{cid}/messages/stream", json={"content": "Hola"})
    assert r.status_code == 200
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["provider"] == "ollama"
    assert conv["model_id"] == "llama3.2"
    mock_get_provider.assert_called_with("ollama")


@patch("app.routers.api_conversations.get_provider")
def test_send_message_con_override_usa_y_persiste_el_modelo_elegido(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.chat.return_value = "Respuesta."
    mock_get_provider.return_value = mock_provider
    cid = client.post(
        "/api/conversations", json={"title": "Chat", "model_id": "llama3.2", "provider": "ollama"}
    ).json()["id"]

    r = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Hola", "provider": "mancer", "model": "mistral-large"},
    )
    assert r.status_code == 200
    assert mock_provider.chat.call_args[0][0] == "mistral-large"
    mock_get_provider.assert_called_with("mancer")
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["provider"] == "mancer"
    assert conv["model_id"] == "mistral-large"
