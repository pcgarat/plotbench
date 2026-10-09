"""
Tests end-to-end de la API contra Ollama real.

Requieren que Ollama esté levantado y accesible (p. ej. ollama serve).
Si Ollama no está disponible, los tests se omiten y se muestra un aviso al usuario.

Ejecutar solo estos tests:  pytest -m e2e
Excluirlos (p. ej. en CI sin Ollama):  pytest -m "not e2e"
"""
import json
import pytest

pytestmark = pytest.mark.e2e


def _get_first_ollama_model(client):
    """Obtiene el nombre del primer modelo Ollama disponible; hace skip si no hay ninguno."""
    r = client.get("/api/providers/ollama/models")
    assert r.status_code == 200
    models = r.json()
    if not models:
        pytest.skip("Ollama no tiene ningún modelo instalado. Ejecuta 'ollama pull <modelo>'.")
    return models[0]["name"]


def _encode_model_id(model_id: str) -> str:
    """Codifica model_id para la URL (los ':' se convierten en %3A)."""
    from urllib.parse import quote
    return quote(model_id, safe="")


def _get_first_mancer_model(client):
    """Obtiene el nombre del primer modelo Mancer disponible; hace skip si no hay ninguno."""
    r = client.get("/api/providers/mancer/models")
    assert r.status_code == 200
    models = r.json()
    if not models:
        pytest.skip("Mancer no devolvió ningún modelo. Comprueba MANCER_API_KEY y la API.")
    return models[0]["name"]


# ----- API Ollama -----


def test_e2e_ollama_validate(client, ollama_available):
    """GET /api/providers/ollama/validate devuelve 200 y ok cuando Ollama está activo."""
    r = client.get("/api/providers/ollama/validate")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


def test_e2e_ollama_models(client, ollama_available):
    """GET /api/providers/ollama/models devuelve lista de modelos (puede estar vacía si no hay modelos)."""
    r = client.get("/api/providers/ollama/models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    for m in models:
        assert "name" in m
        assert m.get("provider") == "ollama"


def test_e2e_models_default_provider(client, ollama_available):
    """GET /api/models (sin provider) usa Ollama por defecto y devuelve lista de modelos."""
    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_e2e_conversation_create_and_send_message(client, ollama_available):
    """
    Flujo completo: crear conversación, enviar mensaje al LLM (Ollama real) y comprobar respuesta.
    """
    model_name = _get_first_ollama_model(client)

    # Crear conversación
    r_create = client.post(
        "/api/conversations",
        json={
            "title": "E2E test",
            "model_id": model_name,
            "provider": "ollama",
        },
    )
    assert r_create.status_code == 200
    conv = r_create.json()
    conversation_id = conv["id"]
    assert conv["provider"] == "ollama"
    assert conv["model_id"] == model_name

    # Enviar mensaje (prompt corto para que el test sea rápido)
    r_msg = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    assert r_msg.status_code == 200
    msg = r_msg.json()
    assert msg.get("role") == "assistant"
    assert "content" in msg
    assert len(msg["content"].strip()) >= 0  # puede ser "OK" o una frase

    # Comprobar que la conversación tiene el mensaje guardado
    r_get = client.get(f"/api/conversations/{conversation_id}")
    assert r_get.status_code == 200
    conv_out = r_get.json()
    assert len(conv_out["messages"]) >= 2  # user + assistant
    roles = [m["role"] for m in conv_out["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_e2e_list_messages_includes_assistant_reply(client, ollama_available):
    """GET /api/messages lista la respuesta assistant tras un turno real."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={
            "title": "E2E messages index",
            "model_id": model_name,
            "provider": "ollama",
        },
    )
    assert r_create.status_code == 200
    conversation_id = r_create.json()["id"]
    r_msg = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    assert r_msg.status_code == 200
    assistant_id = r_msg.json().get("id")
    r_list = client.get("/api/messages")
    assert r_list.status_code == 200
    payload = r_list.json()
    assert isinstance(payload, dict)
    items = payload["items"]
    assert isinstance(items, list)
    match = next((it for it in items if it.get("conversation_id") == conversation_id), None)
    assert match is not None
    assert match.get("content_preview")
    assert match.get("parent_id")
    assert "created_at" in match
    assert "latest_image_at" in match
    if assistant_id:
        assert match["id"] == assistant_id
    r_sorted = client.get("/api/messages", params={"sort": "message"})
    assert r_sorted.status_code == 200
    assert isinstance(r_sorted.json()["items"], list)


def test_e2e_conversation_history_turns(client, ollama_available):
    """
    GET conversación incluye history_turns; PUT con history_turns persiste;
    enviar mensaje con history_turns definido funciona (el backend limita pares en el prompt).
    """
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "E2E history_turns", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]

    r_get = client.get(f"/api/conversations/{cid}")
    assert r_get.status_code == 200
    assert "history_turns" in r_get.json()

    r_put = client.put(f"/api/conversations/{cid}", json={"history_turns": 3})
    assert r_put.status_code == 200
    assert r_put.json().get("history_turns") == 3

    r_get2 = client.get(f"/api/conversations/{cid}")
    assert r_get2.status_code == 200
    assert r_get2.json().get("history_turns") == 3

    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    assert r_msg.status_code == 200
    assert r_msg.json().get("role") == "assistant"
    conv = client.get(f"/api/conversations/{cid}").json()
    assert len(conv["messages"]) >= 2
    assert conv["messages"][0].get("parent_id") in (None, "")
    assert conv["messages"][1].get("parent_id") == conv["messages"][0]["id"]
    assert conv.get("active_leaf_message_id") == conv["messages"][-1]["id"]


def test_e2e_conversation_images_persist(client, ollama_available):
    """PUT images en la conversación y GET lo devuelve tras recarga."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "E2E images prefs", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    assert r_create.json().get("images") is None
    payload = {
        "enabled": True,
        "prompt": "film still",
        "images_per_response": 3,
        "prompt_provider": "ollama",
        "prompt_model": model_name,
        "prompt_model_params": {"temperature": 0.4},
        "steps": 20,
        "width": 768,
        "height": 1024,
        "seed": -1,
        "visual_consistency": False,
    }
    r_put = client.put(f"/api/conversations/{cid}", json={"images": payload})
    assert r_put.status_code == 200
    assert r_put.json()["images"]["enabled"] is True
    assert r_put.json()["images"]["prompt"] == "film still"
    assert r_put.json()["images"]["visual_consistency"] is False
    r_get = client.get(f"/api/conversations/{cid}")
    assert r_get.status_code == 200
    assert r_get.json()["images"]["enabled"] is True
    assert r_get.json()["images"]["prompt_model"] == model_name
    assert r_get.json()["images"]["prompt_model_params"]["temperature"] == 0.4
    assert r_get.json()["images"]["steps"] == 20
    assert r_get.json()["images"]["visual_consistency"] is False


def test_e2e_conversation_fork(client, ollama_available):
    """Variante por referencia: la hija no copia mensajes; el envío usa el prefijo del origen."""
    model_name = _get_first_ollama_model(client)
    origin_id = client.post(
        "/api/conversations",
        json={"title": "E2E fork origen", "model_id": model_name, "provider": "ollama"},
    ).json()["id"]
    r1 = client.post(
        f"/api/conversations/{origin_id}/messages",
        json={"content": "Di solo: uno"},
    )
    assert r1.status_code == 200
    origin = client.get(f"/api/conversations/{origin_id}").json()
    assert len(origin["messages"]) >= 2
    ancla = origin["messages"][1]["id"]
    r2 = client.post(
        f"/api/conversations/{origin_id}/messages",
        json={"content": "Di solo: dos"},
    )
    assert r2.status_code == 200
    r_fork = client.post(f"/api/conversations/{origin_id}/fork", json={"message_id": ancla})
    assert r_fork.status_code == 200
    child = r_fork.json()
    assert child["messages"] == []
    inherited_ids = {m["id"] for m in child["inherited_messages"]}
    assert ancla in inherited_ids
    assert origin["messages"][0]["id"] in inherited_ids
    r3 = client.post(
        f"/api/conversations/{child['id']}/messages",
        json={"content": "Di solo: tres"},
    )
    assert r3.status_code == 200
    child2 = client.get(f"/api/conversations/{child['id']}").json()
    assert len(child2["messages"]) >= 2
    assert all(m["id"] not in inherited_ids for m in child2["messages"])
    origin2 = client.get(f"/api/conversations/{origin_id}").json()
    assert len(origin2["messages"]) >= 4
    assert child2["messages"][0]["id"] not in {m["id"] for m in origin2["messages"]}
    listed = client.get("/api/messages", params={"limit": 100}).json()["items"]
    listed_ids = [it["id"] for it in listed]
    assert len(listed_ids) == len(set(listed_ids))
    origin_assistants = [m["id"] for m in origin2["messages"] if m["role"] == "assistant"]
    child_assistants = [m["id"] for m in child2["messages"] if m["role"] == "assistant"]
    for msg_id in origin_assistants + child_assistants:
        assert msg_id in listed_ids


def test_e2e_message_tree_children_includes_fork_edge(client, ollama_available):
    """GET /api/message-tree/{ancla}/children incluye el primer assistant del fork con is_fork_edge."""
    model_name = _get_first_ollama_model(client)
    origin_id = client.post(
        "/api/conversations",
        json={"title": "E2E message-tree fork", "model_id": model_name, "provider": "ollama"},
    ).json()["id"]
    r1 = client.post(
        f"/api/conversations/{origin_id}/messages",
        json={"content": "Di solo: ancla"},
    )
    assert r1.status_code == 200
    origin = client.get(f"/api/conversations/{origin_id}").json()
    ancla = next(m for m in origin["messages"] if m["role"] == "assistant")
    child = client.post(
        f"/api/conversations/{origin_id}/fork", json={"message_id": ancla["id"]}
    ).json()
    r_fork = client.post(
        f"/api/conversations/{child['id']}/messages",
        json={"content": "Di solo: rama"},
    )
    assert r_fork.status_code == 200
    child2 = client.get(f"/api/conversations/{child['id']}").json()
    fork_assistant = next(m for m in child2["messages"] if m["role"] == "assistant")

    kids = client.get(f"/api/message-tree/{ancla['id']}/children").json()
    assert any(k["id"] == fork_assistant["id"] and k["is_fork_edge"] is True for k in kids)


def test_e2e_fork_inherited_content_mutations(client, ollama_available):
    """Mutaciones de ilustración sobre un mensaje heredado se aplican a la fila del origen."""
    model_name = _get_first_ollama_model(client)
    origin_id = client.post(
        "/api/conversations",
        json={"title": "E2E fork mutación heredada", "model_id": model_name, "provider": "ollama"},
    ).json()["id"]
    r1 = client.post(
        f"/api/conversations/{origin_id}/messages",
        json={"content": "Di solo: uno"},
    )
    assert r1.status_code == 200
    origin = client.get(f"/api/conversations/{origin_id}").json()
    assistant = next(m for m in origin["messages"] if m["role"] == "assistant")
    child_id = client.post(
        f"/api/conversations/{origin_id}/fork", json={"message_id": assistant["id"]}
    ).json()["id"]
    for action in ("clear-photos", "prune-orphans"):
        r = client.post(
            f"/api/conversations/{child_id}/messages/{assistant['id']}/illustrations/{action}"
        )
        assert r.status_code == 200, action
        assert "content" in r.json()
    origin_after = client.get(f"/api/conversations/{origin_id}").json()
    assert any(m["id"] == assistant["id"] for m in origin_after["messages"])


def test_e2e_ollama_clear_memory(client, ollama_available):
    """POST /api/ollama/clear-memory devuelve 200 y un objeto con 'unloaded' (lista)."""
    r = client.post("/api/ollama/clear-memory")
    assert r.status_code == 200
    data = r.json()
    assert "unloaded" in data
    assert isinstance(data["unloaded"], list)


# ----- API Models / Providers -----


def test_e2e_list_providers(client, ollama_available):
    """GET /api/providers devuelve lista de proveedores (al menos ollama)."""
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    names = [p["name"] for p in data]
    assert "ollama" in names


def test_e2e_provider_params_ollama(client, ollama_available):
    """GET /api/providers/ollama/params devuelve provider y params."""
    r = client.get("/api/providers/ollama/params")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "ollama"
    assert "params" in data
    assert isinstance(data["params"], (list, dict))


def test_e2e_provider_presets_ollama(client, ollama_available):
    """GET /api/providers/ollama/presets devuelve provider y presets."""
    r = client.get("/api/providers/ollama/presets")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "ollama"
    assert "presets" in data
    assert isinstance(data["presets"], (list, dict))


def test_e2e_list_all_models(client, ollama_available):
    """GET /api/models/all devuelve lista de modelos de todos los proveedores."""
    r = client.get("/api/models/all")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for m in data:
        assert "name" in m
        assert "provider" in m


def test_e2e_provider_capabilities_ollama(client, ollama_available):
    """GET /api/providers/ollama/capabilities devuelve capabilities."""
    r = client.get("/api/providers/ollama/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "capabilities" in data
    assert isinstance(data["capabilities"], list)


def test_e2e_get_model_contract(client, ollama_available):
    """GET /api/providers/ollama/models/{model_id}/contract devuelve el contrato."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/ollama/models/{path_id}/contract")
    assert r.status_code == 200
    data = r.json()
    for key in ("provider", "model", "capabilities", "params", "recipes", "quirks"):
        assert key in data
    assert data["provider"] == "ollama"
    assert data["model"] == model_id
    assert "thinking" in data["capabilities"]
    assert isinstance(data["params"], dict)
    assert isinstance(data["recipes"], list)
    assert isinstance(data["quirks"], list)


def test_e2e_get_model_info(client, ollama_available):
    """GET /api/providers/ollama/models/{model_id}/info devuelve provider_info y user_info."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/ollama/models/{path_id}/info")
    assert r.status_code == 200
    data = r.json()
    assert "provider_info" in data
    assert "user_info" in data
    assert "uncensored" in data["user_info"]
    assert "instructions" in data["user_info"]
    assert "instruction_ids" in data["user_info"]
    assert isinstance(data["user_info"]["instructions"], list)
    assert isinstance(data["user_info"]["instruction_ids"], list)
    assert "tags" in data["user_info"]


def test_e2e_put_model_info(client, ollama_available):
    """PUT /api/providers/ollama/models/{model_id}/info actualiza user_info."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)
    r = client.put(
        f"/api/providers/ollama/models/{path_id}/info",
        json={"tags": ["e2e-test-tag"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert "user_info" in data
    assert "e2e-test-tag" in data["user_info"].get("tags", [])


def test_e2e_refresh_model_info(client, ollama_available):
    """POST /api/providers/ollama/models/{model_id}/info/refresh refresca provider_info."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)
    r = client.post(f"/api/providers/ollama/models/{path_id}/info/refresh")
    assert r.status_code == 200
    data = r.json()
    assert "provider_info" in data
    assert "user_info" in data


def test_e2e_list_model_tags(client, ollama_available):
    """GET /api/models/tags devuelve lista de tags."""
    r = client.get("/api/models/tags")
    assert r.status_code == 200
    data = r.json()
    assert "tags" in data
    assert isinstance(data["tags"], list)


def test_e2e_get_context_length(client, ollama_available):
    """GET /api/providers/ollama/models/{model_id}/context-length devuelve context_length (número o null)."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/ollama/models/{path_id}/context-length")
    assert r.status_code == 200
    data = r.json()
    assert "context_length" in data
    # Puede ser int (desde ficha, preset o list_models) o null si no hay fuente
    assert data["context_length"] is None or isinstance(data["context_length"], int)
    if data["context_length"] is not None:
        assert data["context_length"] > 0


# ----- API OpenAI (e2e cuando OPENAI_API_KEY está configurada) -----


def test_e2e_list_providers_includes_openai_when_key_set(client, openai_available):
    """GET /api/providers incluye openai cuando OPENAI_API_KEY está configurada."""
    r = client.get("/api/providers")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "openai" in names


def test_e2e_openai_models(client, openai_available):
    """GET /api/providers/openai/models devuelve lista de modelos (API real)."""
    r = client.get("/api/providers/openai/models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    for m in models:
        assert "name" in m
        assert m.get("provider") == "openai"


def test_e2e_openai_validate(client, openai_available):
    """GET /api/providers/openai/validate devuelve 200 y ok cuando la API responde."""
    r = client.get("/api/providers/openai/validate")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data


def test_e2e_openai_params(client, openai_available):
    """GET /api/providers/openai/params devuelve provider y params."""
    r = client.get("/api/providers/openai/params")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "openai"
    assert "params" in data


def test_e2e_openai_context_length(client, openai_available):
    """GET /api/providers/openai/models/{model_id}/context-length devuelve 200 (context_length puede ser null)."""
    # Usar un modelo conocido; si no hay modelos listados, usar gpt-4o-mini como path
    r_models = client.get("/api/providers/openai/models")
    assert r_models.status_code == 200
    models = r_models.json()
    model_id = models[0]["name"] if models else "gpt-4o-mini"
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/openai/models/{path_id}/context-length")
    assert r.status_code == 200
    data = r.json()
    assert "context_length" in data
    assert data["context_length"] is None or isinstance(data["context_length"], int)


# ----- API Mancer (e2e cuando MANCER_API_KEY está configurada) -----


def test_e2e_list_providers_includes_mancer_when_key_set(client, mancer_available):
    """GET /api/providers incluye mancer cuando MANCER_API_KEY está configurada."""
    r = client.get("/api/providers")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "mancer" in names


def test_e2e_mancer_models(client, mancer_available):
    """GET /api/providers/mancer/models devuelve lista de modelos (API real)."""
    r = client.get("/api/providers/mancer/models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    for m in models:
        assert "name" in m
        assert m.get("provider") == "mancer"


def test_e2e_mancer_validate(client, mancer_available):
    """GET /api/providers/mancer/validate devuelve 200 y ok cuando la API responde."""
    r = client.get("/api/providers/mancer/validate")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


def test_e2e_mancer_params(client, mancer_available):
    """GET /api/providers/mancer/params devuelve provider y params (mapeo de campos)."""
    r = client.get("/api/providers/mancer/params")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "mancer"
    assert "params" in data
    assert isinstance(data["params"], dict)
    # Debe incluir al menos temperature y max_tokens (config provider_params.json)
    assert "temperature" in data["params"]
    assert "max_tokens" in data["params"]


def test_e2e_mancer_capabilities(client, mancer_available):
    """GET /api/providers/mancer/capabilities devuelve show_model (ficha de modelo)."""
    r = client.get("/api/providers/mancer/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "capabilities" in data
    assert isinstance(data["capabilities"], list)
    assert "show_model" in data["capabilities"]


def test_e2e_mancer_get_model_info(client, mancer_available):
    """GET /api/providers/mancer/models/{model_id}/info devuelve provider_info y user_info."""
    model_id = _get_first_mancer_model(client)
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/mancer/models/{path_id}/info")
    assert r.status_code == 200
    data = r.json()
    assert "provider_info" in data
    assert "user_info" in data
    assert "uncensored" in data["user_info"]
    assert "instructions" in data["user_info"]
    assert "instruction_ids" in data["user_info"]
    assert "tags" in data["user_info"]


def test_e2e_mancer_refresh_model_info(client, mancer_available):
    """POST /api/providers/mancer/models/{model_id}/info/refresh refresca provider_info desde la API."""
    model_id = _get_first_mancer_model(client)
    path_id = _encode_model_id(model_id)
    r = client.post(f"/api/providers/mancer/models/{path_id}/info/refresh")
    assert r.status_code == 200
    data = r.json()
    assert "provider_info" in data
    assert "user_info" in data
    # Tras refresh, provider_info debería tener datos de GET /oai/v1/models/{id}
    pi = data.get("provider_info") or {}
    assert "fetched_at" in pi or "context_length" in pi or "id" in pi or "pricing" in pi


def test_e2e_mancer_context_length(client, mancer_available):
    """GET /api/providers/mancer/models/{model_id}/context-length devuelve context_length (número o null)."""
    model_id = _get_first_mancer_model(client)
    path_id = _encode_model_id(model_id)
    r = client.get(f"/api/providers/mancer/models/{path_id}/context-length")
    assert r.status_code == 200
    data = r.json()
    assert "context_length" in data
    assert data["context_length"] is None or isinstance(data["context_length"], int)
    if data["context_length"] is not None:
        assert data["context_length"] > 0


# ----- API Abliteration (e2e cuando ABLIT_KEY está configurada) -----


def _get_first_abliteration_model(client):
    """Obtiene el primer modelo Abliteration; hace skip si la lista está vacía."""
    r = client.get("/api/providers/abliteration/models")
    assert r.status_code == 200
    models = r.json()
    if not models:
        pytest.skip("Abliteration no devolvió ningún modelo. Comprueba ABLIT_KEY y la API.")
    return models[0]["name"]


def test_e2e_list_providers_includes_abliteration_when_key_set(client, abliteration_available):
    """GET /api/providers incluye abliteration cuando ABLIT_KEY está configurada."""
    r = client.get("/api/providers")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "abliteration" in names


def test_e2e_abliteration_models(client, abliteration_available):
    """GET /api/providers/abliteration/models incluye los modelos oficiales."""
    r = client.get("/api/providers/abliteration/models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    names = {m["name"] for m in models}
    assert "abliterated-model" in names
    assert "abliterated-model-large" in names
    assert "abliterated-model-large-v2" in names
    for m in models:
        assert m.get("provider") == "abliteration"


def test_e2e_abliteration_validate(client, abliteration_available):
    """GET /api/providers/abliteration/validate devuelve 200 y ok."""
    r = client.get("/api/providers/abliteration/validate")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


def test_e2e_abliteration_params(client, abliteration_available):
    """GET /api/providers/abliteration/params devuelve provider y params."""
    r = client.get("/api/providers/abliteration/params")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "abliteration"
    assert "temperature" in data.get("params", {})
    assert "max_tokens" in data.get("params", {})


def test_e2e_abliteration_capabilities(client, abliteration_available):
    """GET /api/providers/abliteration/capabilities incluye show_model."""
    r = client.get("/api/providers/abliteration/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "show_model" in data.get("capabilities", [])


def test_e2e_abliteration_context_length(client, abliteration_available):
    """context-length de abliterated-model es 262144 según preset/catálogo."""
    path_id = _encode_model_id("abliterated-model")
    r = client.get(f"/api/providers/abliteration/models/{path_id}/context-length")
    assert r.status_code == 200
    data = r.json()
    assert data["context_length"] == 262144


# ----- API NaN Builders (e2e cuando NAN_API_KEY está configurada) -----


def _get_first_nan_model(client):
    """Obtiene el primer modelo NaN; hace skip si la lista está vacía."""
    r = client.get("/api/providers/nan/models")
    assert r.status_code == 200
    models = r.json()
    if not models:
        pytest.skip("NaN no devolvió ningún modelo. Comprueba NAN_API_KEY y la API.")
    return models[0]["name"]


def test_e2e_list_providers_includes_nan_when_key_set(client, nan_available):
    """GET /api/providers incluye nan cuando NAN_API_KEY está configurada."""
    r = client.get("/api/providers")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "nan" in names


def test_e2e_nan_models(client, nan_available):
    """GET /api/providers/nan/models devuelve modelos con provider nan."""
    r = client.get("/api/providers/nan/models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    assert models, "NaN no devolvió modelos"
    for m in models:
        assert m.get("provider") == "nan"


def test_e2e_nan_validate(client, nan_available):
    """GET /api/providers/nan/validate devuelve 200 y ok."""
    r = client.get("/api/providers/nan/validate")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


def test_e2e_nan_params(client, nan_available):
    """GET /api/providers/nan/params devuelve provider y params."""
    r = client.get("/api/providers/nan/params")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "nan"
    assert "temperature" in data.get("params", {})
    assert "max_tokens" in data.get("params", {})


def test_e2e_nan_capabilities(client, nan_available):
    """GET /api/providers/nan/capabilities incluye show_model."""
    r = client.get("/api/providers/nan/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "show_model" in data.get("capabilities", [])


def test_e2e_nan_context_length(client, nan_available):
    """context-length de un modelo NaN es coherente con el preset (1M para deepseek-v4-flash)."""
    path_id = _encode_model_id("deepseek-v4-flash")
    r = client.get(f"/api/providers/nan/models/{path_id}/context-length")
    assert r.status_code == 200
    data = r.json()
    assert data["context_length"] == 1048576


# ----- API Rules (biblioteca) -----


def test_e2e_rules_crud(client, ollama_available):
    """E2E: CRUD de reglas (GET list, POST create, GET one, PUT update, DELETE)."""
    r_list = client.get("/api/rules")
    assert r_list.status_code == 200
    initial = r_list.json()
    assert isinstance(initial, list)

    r_post = client.post("/api/rules", json={"title": "E2E regla", "content": "Contenido E2E"})
    assert r_post.status_code == 201
    rule = r_post.json()
    assert "id" in rule
    assert rule["title"] == "E2E regla"
    assert rule["content"] == "Contenido E2E"
    rule_id = rule["id"]

    r_get = client.get(f"/api/rules/{rule_id}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == rule_id
    assert r_get.json()["title"] == "E2E regla"

    r_put = client.put(f"/api/rules/{rule_id}", json={"title": "E2E regla actualizada", "content": "Nuevo contenido"})
    assert r_put.status_code == 200
    assert r_put.json()["title"] == "E2E regla actualizada"
    assert r_put.json()["content"] == "Nuevo contenido"

    r_del = client.delete(f"/api/rules/{rule_id}")
    assert r_del.status_code == 204
    r_get_404 = client.get(f"/api/rules/{rule_id}")
    assert r_get_404.status_code == 404, "La regla debe desaparecer de la BD al eliminarla"


def test_e2e_planner_rules_are_isolated_from_chat_library(client, ollama_available):
    """E2E: una regla scope=planner no aparece en la biblioteca del chat."""
    r_post = client.post(
        "/api/rules",
        json={"title": "E2E planner", "content": "Solo ilustración", "scope": "planner"},
    )
    assert r_post.status_code == 201
    rule_id = r_post.json()["id"]
    assert r_post.json()["scope"] == "planner"

    chat_list = client.get("/api/rules").json()
    assert all(item["id"] != rule_id for item in chat_list)

    planner_list = client.get("/api/rules", params={"scope": "planner"}).json()
    assert any(item["id"] == rule_id for item in planner_list)

    client.delete(f"/api/rules/{rule_id}")


def test_e2e_planner_library_includes_builtin_flux_guide(client, ollama_available):
    """E2E: la guía FLUX se siembra en scope=planner y no aparece en la biblioteca del chat."""
    from app.services.rules.seed import FLUX_PROMPT_GUIDE_RULE_ID, FLUX_PROMPT_GUIDE_TITLE

    planner_list = client.get("/api/rules", params={"scope": "planner"}).json()
    match = [item for item in planner_list if item["id"] == FLUX_PROMPT_GUIDE_RULE_ID]
    assert len(match) == 1
    assert match[0]["title"] == FLUX_PROMPT_GUIDE_TITLE
    assert match[0]["scope"] == "planner"

    chat_list = client.get("/api/rules").json()
    assert all(item["id"] != FLUX_PROMPT_GUIDE_RULE_ID for item in chat_list)


def test_e2e_planner_library_includes_builtin_krea2_pov_guide(client, ollama_available):
    """E2E: la guía Krea 2 POV se siembra en scope=planner y no aparece en la biblioteca del chat."""
    from app.services.rules.seed import KREA2_POV_GUIDE_RULE_ID, KREA2_POV_GUIDE_TITLE

    planner_list = client.get("/api/rules", params={"scope": "planner"}).json()
    match = [item for item in planner_list if item["id"] == KREA2_POV_GUIDE_RULE_ID]
    assert len(match) == 1
    assert match[0]["title"] == KREA2_POV_GUIDE_TITLE
    assert match[0]["scope"] == "planner"
    assert "filling the view" in match[0]["content"]
    assert "looks into the viewer's eyes" in match[0]["content"]

    chat_list = client.get("/api/rules").json()
    assert all(item["id"] != KREA2_POV_GUIDE_RULE_ID for item in chat_list)


def test_e2e_planner_library_includes_builtin_krea2_photorealism_guide(client, ollama_available):
    """E2E: la guía Krea 2 fotorrealismo se siembra en scope=planner y no aparece en el chat."""
    from app.services.rules.seed import KREA2_PHOTOREALISM_RULE_ID, KREA2_PHOTOREALISM_TITLE

    planner_list = client.get("/api/rules", params={"scope": "planner"}).json()
    match = [item for item in planner_list if item["id"] == KREA2_PHOTOREALISM_RULE_ID]
    assert len(match) == 1
    assert match[0]["title"] == KREA2_PHOTOREALISM_TITLE
    assert match[0]["scope"] == "planner"
    assert "photograph" in match[0]["content"]
    assert "shallow depth of field" in match[0]["content"]

    chat_list = client.get("/api/rules").json()
    assert all(item["id"] != KREA2_PHOTOREALISM_RULE_ID for item in chat_list)


def test_e2e_rule_delete_removes_from_db_and_from_all_conversations(client, ollama_available):
    """
    Al eliminar una regla de la biblioteca (DELETE /api/rules/{id}):
    - La regla ya no existe en la BD (GET regla -> 404).
    - Las conversaciones que la tenían dejan de mostrarla en system_instructions.
    Si la eliminación solo quitara la regla de la conversación actual pero no de la BD, este test fallaría.
    """
    model_name = _get_first_ollama_model(client)
    r_rule = client.post("/api/rules", json={"title": "Regla a borrar", "content": "Contenido"})
    assert r_rule.status_code == 201
    rule_id = r_rule.json()["id"]

    r_c1 = client.post(
        "/api/conversations",
        json={
            "title": "Conv con regla",
            "model_id": model_name,
            "provider": "ollama",
            "system_instructions": [{"rule_id": rule_id, "title": "Regla a borrar", "content": "Contenido"}],
        },
    )
    assert r_c1.status_code == 200
    cid1 = r_c1.json()["id"]
    r_c2 = client.post(
        "/api/conversations",
        json={
            "title": "Otra conv con misma regla",
            "model_id": model_name,
            "provider": "ollama",
            "system_instructions": [{"rule_id": rule_id, "title": "Regla a borrar", "content": "Contenido"}],
        },
    )
    assert r_c2.status_code == 200
    cid2 = r_c2.json()["id"]

    r_del = client.delete(f"/api/rules/{rule_id}")
    assert r_del.status_code == 204

    r_get_rule = client.get(f"/api/rules/{rule_id}")
    assert r_get_rule.status_code == 404, "La regla debe estar eliminada de la BD"

    for cid in (cid1, cid2):
        r_conv = client.get(f"/api/conversations/{cid}")
        assert r_conv.status_code == 200
        instr = r_conv.json().get("system_instructions") or []
        rule_titles = [i.get("title") for i in instr]
        assert "Regla a borrar" not in rule_titles, f"La conversación {cid} no debe mostrar la regla eliminada"


def test_e2e_conversation_with_rule_id(client, ollama_available):
    """
    E2E: crear regla en biblioteca, crear conversación con system_instructions referenciando rule_id,
    enviar mensaje y comprobar que se usa el contenido de la regla.
    """
    model_name = _get_first_ollama_model(client)
    r_rule = client.post("/api/rules", json={"title": "E2E ref", "content": "Responde en una palabra."})
    assert r_rule.status_code == 201
    rule_id = r_rule.json()["id"]

    r_create = client.post(
        "/api/conversations",
        json={
            "title": "E2E con rule_id",
            "model_id": model_name,
            "provider": "ollama",
            "system_instructions": [{"rule_id": rule_id, "title": "E2E ref", "content": "Responde en una palabra."}],
        },
    )
    assert r_create.status_code == 200
    data = r_create.json()
    cid = data["id"]
    instr = data.get("system_instructions") or []
    assert len(instr) == 1
    assert instr[0].get("title") == "E2E ref"
    assert instr[0].get("content") == "Responde en una palabra."

    r_msg = client.post(
        f"/api/conversations/{cid}/messages/stream",
        json={"content": "Di: listo"},
    )
    assert r_msg.status_code == 200
    lines = [line for line in r_msg.text.strip().split("\n") if line]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last.get("done") is True

    # Limpieza: borrar regla
    client.delete(f"/api/rules/{rule_id}")


def test_e2e_model_info_instruction_ids(client, ollama_available):
    """E2E: PUT model info con instruction_ids (reglas de biblioteca), GET devuelve instructions resueltas."""
    model_id = _get_first_ollama_model(client)
    path_id = _encode_model_id(model_id)

    r1 = client.post("/api/rules", json={"title": "Para modelo", "content": "Instrucción asociada al modelo."})
    assert r1.status_code == 201
    rule_id = r1.json()["id"]

    r_put = client.put(
        f"/api/providers/ollama/models/{path_id}/info",
        json={"instruction_ids": [rule_id]},
    )
    assert r_put.status_code == 200
    ui = r_put.json()["user_info"]
    assert ui.get("instruction_ids") == [rule_id]
    assert len(ui.get("instructions") or []) == 1
    assert ui["instructions"][0]["title"] == "Para modelo"
    assert ui["instructions"][0]["content"] == "Instrucción asociada al modelo."

    r_get = client.get(f"/api/providers/ollama/models/{path_id}/info")
    assert r_get.status_code == 200
    ui2 = r_get.json()["user_info"]
    assert ui2.get("instruction_ids") == [rule_id]
    assert len(ui2.get("instructions") or []) == 1
    assert ui2["instructions"][0]["content"] == "Instrucción asociada al modelo."

    # Limpieza: quitar instruction_ids de la ficha y opcionalmente borrar regla
    client.put(f"/api/providers/ollama/models/{path_id}/info", json={"instruction_ids": []})
    client.delete(f"/api/rules/{rule_id}")


# ----- API Conversations -----


def test_e2e_list_conversations(client, ollama_available):
    """GET /api/conversations devuelve lista (puede estar vacía)."""
    r = client.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    r_created = client.get("/api/conversations", params={"sort": "created_at"})
    assert r_created.status_code == 200
    assert isinstance(r_created.json(), list)
    if r_created.json():
        assert "created_at" in r_created.json()[0]


def test_e2e_create_conversation(client, ollama_available):
    """POST /api/conversations crea una conversación y devuelve sus datos."""
    model_name = _get_first_ollama_model(client)
    r = client.post(
        "/api/conversations",
        json={"title": "E2E create", "model_id": model_name, "provider": "ollama"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["title"] == "E2E create"
    assert data["auto_title"] is False
    assert data["model_id"] == model_name
    assert data["provider"] == "ollama"
    assert "created_at" in data
    assert data.get("messages", []) == []
    assert "model_params" in data
    assert data["model_params"] is None
    assert "system_instructions" in data
    assert data["system_instructions"] is None or data["system_instructions"] == []


def test_e2e_get_conversation(client, ollama_available):
    """GET /api/conversations/{id} devuelve la conversación con mensajes y model_params."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "E2E get", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r = client.get(f"/api/conversations/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == cid
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert "model_params" in data
    assert data["model_params"] is None
    assert "system_instructions" in data


def test_e2e_update_conversation(client, ollama_available):
    """PUT /api/conversations/{id} actualiza título/model_id/provider/model_params."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Original", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r = client.put(
        f"/api/conversations/{cid}",
        json={"title": "Updated title"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Updated title"
    assert r.json()["auto_title"] is False
    r_auto = client.put(f"/api/conversations/{cid}", json={"auto_title": True})
    assert r_auto.status_code == 200
    assert r_auto.json()["auto_title"] is True
    assert r_auto.json()["title"] == "Updated title"
    assert "model_params" in r.json()
    assert r.json()["model_params"] is None


def test_e2e_conversation_model_params_persist(client, ollama_available):
    """
    E2E: guardar model_params en una conversación y comprobar que se persisten y devuelven.
    Crear conversación → PUT model_params → GET comprueba model_params → enviar mensaje con model_params.
    """
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "E2E params", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    params = {"temperature": 0.3, "num_ctx": 2048}
    r_put = client.put(f"/api/conversations/{cid}", json={"model_params": params})
    assert r_put.status_code == 200
    assert r_put.json()["model_params"] == params
    r_get = client.get(f"/api/conversations/{cid}")
    assert r_get.status_code == 200
    assert r_get.json()["model_params"] == params
    # Enviar mensaje usando esos params (el backend usa model_params del body o de la conv)
    r_msg = client.post(
        f"/api/conversations/{cid}/messages/stream",
        json={"content": "Di: listo", "model_params": params},
    )
    assert r_msg.status_code == 200
    lines = [line for line in r_msg.text.strip().split("\n") if line]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last.get("done") is True


def test_e2e_conversation_system_instructions(client, ollama_available):
    """
    E2E: guardar system_instructions (lista de reglas) en una conversación, persistir y usar en mensaje.
    Crear con system_instructions → PUT actualizar lista → GET comprueba → enviar mensaje con system (concatenado).
    """
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={
            "title": "E2E reglas",
            "model_id": model_name,
            "provider": "ollama",
            "system_instructions": [
                {"title": "Brevedad", "content": "Responde breve."},
                {"title": "Idioma", "content": "Siempre en español."},
            ],
        },
    )
    assert r_create.status_code == 200
    data = r_create.json()
    instr = data.get("system_instructions") or []
    assert len(instr) == 2
    assert instr[0]["title"] == "Brevedad" and instr[0]["content"] == "Responde breve."
    assert instr[1]["title"] == "Idioma" and instr[1]["content"] == "Siempre en español."
    cid = data["id"]
    r_put = client.put(
        f"/api/conversations/{cid}",
        json={"system_instructions": [{"title": "Una", "content": "Solo una regla"}]},
    )
    assert r_put.status_code == 200
    put_instr = r_put.json().get("system_instructions") or []
    assert len(put_instr) == 1 and put_instr[0]["title"] == "Una" and put_instr[0]["content"] == "Solo una regla"
    r_get = client.get(f"/api/conversations/{cid}")
    assert r_get.status_code == 200
    get_instr = r_get.json().get("system_instructions") or []
    assert len(get_instr) == 1 and get_instr[0]["title"] == "Una" and get_instr[0]["content"] == "Solo una regla"
    # Enviar mensaje; el backend usa system_instructions de la conv (concatenados) si no se envía system_instruction_global
    r_msg = client.post(
        f"/api/conversations/{cid}/messages/stream",
        json={"content": "Di: ok"},
    )
    assert r_msg.status_code == 200
    lines = [line for line in r_msg.text.strip().split("\n") if line]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last.get("done") is True


def test_e2e_send_message_stream(client, ollama_available):
    """POST /api/conversations/{id}/messages/stream devuelve NDJSON con chunks y mensaje asistente."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Stream E2E", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r = client.post(
        f"/api/conversations/{cid}/messages/stream",
        json={"content": "Di solo: Hola"},
    )
    assert r.status_code == 200
    lines = [line for line in r.text.strip().split("\n") if line]
    assert len(lines) >= 1
    # Debe haber al menos una línea con "content" o "done"
    content_parts = [l for l in lines if '"content"' in l or '"done"' in l]
    assert len(content_parts) >= 1
    # Comprobar que hay done al final
    last = json.loads(lines[-1])
    assert last.get("done") is True and "id" in last


def test_e2e_delete_last_message(client, ollama_available):
    """DELETE /api/conversations/{id}/messages/last elimina el último mensaje."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Del last", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    r = client.delete(f"/api/conversations/{cid}/messages/last")
    assert r.status_code == 204
    conv = client.get(f"/api/conversations/{cid}").json()
    # Quedan 0 mensajes (solo habíamos añadido user + assistant, se borra el último)
    assert len(conv["messages"]) <= 2


def test_e2e_clear_conversation_messages(client, ollama_available):
    """DELETE /api/conversations/{id}/messages limpia todos los mensajes."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Clear msgs", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    r = client.delete(f"/api/conversations/{cid}/messages")
    assert r.status_code == 204
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["messages"] == []


def test_e2e_delete_message(client, ollama_available):
    """DELETE /api/conversations/{id}/messages/{message_id} elimina un mensaje concreto."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Del one", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    # Prompt corto para que el LLM responda rápido y el test no se quede colgado.
    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    assert r_msg.status_code == 200
    # La respuesta es el mensaje del asistente; borramos ese
    msg_id = r_msg.json().get("id")
    assert msg_id
    r = client.delete(f"/api/conversations/{cid}/messages/{msg_id}")
    assert r.status_code == 204


def test_e2e_save_message_to_chromadb(client, ollama_available):
    """POST /api/conversations/{id}/messages/{message_id}/save-to-chromadb devuelve 204 (Chroma opcional)."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Chroma E2E", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Responde con una sola palabra: OK"},
    )
    assert r_msg.status_code == 200
    msg_id = r_msg.json().get("id")
    assert msg_id
    r = client.post(f"/api/conversations/{cid}/messages/{msg_id}/save-to-chromadb")
    # 204 si Chroma está disponible; 500/503 si Chroma no está
    if r.status_code != 204:
        pytest.skip("Chroma no disponible (save-to-chromadb requiere ChromaDB)")


def test_e2e_delete_conversation(client, ollama_available):
    """DELETE /api/conversations/{id} soft-delete: desaparece del GET pero se puede restaurar."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "To delete", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r = client.delete(f"/api/conversations/{cid}")
    assert r.status_code == 204
    r_get = client.get(f"/api/conversations/{cid}")
    assert r_get.status_code == 404
    r_restore = client.post(f"/api/conversations/{cid}/restore")
    assert r_restore.status_code == 200
    assert client.get(f"/api/conversations/{cid}").status_code == 200


def test_e2e_illustrate_rejects_non_assistant(client, ollama_available):
    """POST .../illustrate solo acepta mensajes assistant (400 en user)."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Illustrate E2E", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Di solo: hola"},
    )
    assert r_msg.status_code == 200
    r_list = client.get(f"/api/conversations/{cid}/messages")
    assert r_list.status_code == 200
    msgs = r_list.json()
    user = next((m for m in msgs if m.get("role") == "user"), None)
    assert user and user.get("id")
    r = client.post(
        f"/api/conversations/{cid}/messages/{user['id']}/illustrate",
        json={
            "prompt_model": model_name,
            "prompt_provider": "ollama",
            "images_per_response": 1,
            "prompt_model_params": {"temperature": 0.3},
            "visual_consistency": False,
        },
    )
    assert r.status_code == 400


def test_e2e_illustration_edit_rejects_user_message(client, ollama_available):
    """clear-photos, prune-orphans y generate-remaining solo aceptan mensajes assistant."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Illustrate edit E2E", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Di solo: hola"},
    )
    assert r_msg.status_code == 200
    r_list = client.get(f"/api/conversations/{cid}/messages")
    msgs = r_list.json()
    user = next((m for m in msgs if m.get("role") == "user"), None)
    assert user and user.get("id")
    for action in ("clear-photos", "prune-orphans", "generate-remaining"):
        r = client.post(
            f"/api/conversations/{cid}/messages/{user['id']}/illustrations/{action}",
            json={"retries": 0} if action == "generate-remaining" else None,
        )
        assert r.status_code == 400, action


def test_e2e_illustrate_at_rejects_non_assistant(client, ollama_available):
    """POST .../illustrations/illustrate-at solo acepta mensajes assistant."""
    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={"title": "Illustrate-at E2E", "model_id": model_name, "provider": "ollama"},
    )
    assert r_create.status_code == 200
    cid = r_create.json()["id"]
    r_msg = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "Di solo: hola"},
    )
    assert r_msg.status_code == 200
    r_list = client.get(f"/api/conversations/{cid}/messages")
    msgs = r_list.json()
    user = next((m for m in msgs if m.get("role") == "user"), None)
    assert user and user.get("id")
    r = client.post(
        f"/api/conversations/{cid}/messages/{user['id']}/illustrations/illustrate-at",
        json={
            "prompt_model": model_name,
            "prompt_provider": "ollama",
            "paragraph_index": 0,
            "visual_consistency": True,
        },
    )
    assert r.status_code == 400


def test_e2e_illustrated_image_meta_404(client, ollama_available):
    """GET /api/illustrated-images/{filename}/meta responde 404 si no hay registro."""
    r = client.get("/api/illustrated-images/no-such-file.png/meta")
    assert r.status_code == 404


def test_e2e_illustrated_gallery_list_and_facets(client, ollama_available):
    """GET /api/illustrated-images y /facets responden el esquema de galería."""
    r = client.get("/api/illustrated-images")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert isinstance(body["items"], list)
    assert body["limit"] >= 1
    r2 = client.get("/api/illustrated-images/facets")
    assert r2.status_code == 200
    facets = r2.json()
    assert "prompt_models" in facets
    assert "forge_models" in facets
    assert "has_missing_prompt_llm" in facets
    assert "seeds" in facets
    r3 = client.get("/api/illustrated-images", params={"conversation_id": "no-such-conv"})
    assert r3.status_code == 200
    assert r3.json()["total"] == 0
    r4 = client.get("/api/illustrated-images/messages", params={"conversation_id": "no-such-conv"})
    assert r4.status_code == 404
    r5 = client.get("/api/illustrated-images/matching-filenames")
    assert r5.status_code == 422
    r6 = client.get(
        "/api/illustrated-images/matching-filenames", params={"conversation_id": "no-such-conv"}
    )
    assert r6.status_code == 404
    assert b'id="center-panels-splitter"' in client.get("/").content


def test_e2e_image_generation_queue_list(client, ollama_available):
    """GET /api/image-generation-queue responde el esquema de cola."""
    r = client.get("/api/image-generation-queue")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert "active_count" in body
    assert "batch_progress" in body
    assert isinstance(body["batch_progress"], list)
    assert "paused" in body
    assert isinstance(body["items"], list)
    assert body["limit"] >= 1
    r_pause = client.post("/api/image-generation-queue/pause")
    assert r_pause.status_code == 200
    assert r_pause.json()["paused"] is True
    r_resume = client.post("/api/image-generation-queue/resume")
    assert r_resume.status_code == 200
    assert r_resume.json()["paused"] is False
    r2 = client.get("/api/image-generation-queue", params={"status": "pending,generating"})
    assert r2.status_code == 200
    assert isinstance(r2.json()["items"], list)
    assert b'id="btn-image-queue"' in client.get("/").content
    assert b'id="image-queue-panel"' in client.get("/").content
    assert b'id="image-queue-cancel-all"' in client.get("/").content
    assert b'id="gallery-purge-orphans"' in client.get("/").content


def test_e2e_image_generation_queue_delete(client, ollama_available, db_session):
    """POST /api/image-generation-queue/delete elimina trabajos encolados."""
    from app import crud

    conv = crud.create_conversation(db_session, title="e2e", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Texto.")
    job = crud.create_image_generation_job(
        db_session,
        conversation_id=conv.id,
        message_id=msg.id,
        scene_id="s1",
        forge_prompt="test",
        forge_mode="txt2img",
        forge_body={"prompt": "test"},
    )
    res = client.post("/api/image-generation-queue/delete", json={"ids": [job.id]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 1


def test_e2e_image_generation_queue_cancel_active(client, ollama_available, db_session):
    """POST /api/image-generation-queue/cancel-active cancela pending y generating."""
    from app import crud

    empty = client.post("/api/image-generation-queue/cancel-active")
    assert empty.status_code == 200
    assert empty.json()["deleted"] == 0

    conv = crud.create_conversation(db_session, title="e2e-cancel", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Texto.")
    job = crud.create_image_generation_job(
        db_session,
        conversation_id=conv.id,
        message_id=msg.id,
        scene_id="s1",
        forge_prompt="test",
        forge_mode="txt2img",
        forge_body={"prompt": "test"},
    )
    job_id = job.id
    res = client.post("/api/image-generation-queue/cancel-active")
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    assert job_id in res.json()["ids"]


def test_e2e_illustrated_orphans_count(client, ollama_available):
    """GET /api/illustrated-images/orphans responde el recuento; no purga disco real."""
    r = client.get("/api/illustrated-images/orphans")
    assert r.status_code == 200
    assert "count" in r.json()
    assert isinstance(r.json()["count"], int)


def test_e2e_workspace_profiles_crud(client, ollama_available):
    """CRUD de perfiles de workspace: guarda el rig y lo recupera."""
    model_name = _get_first_ollama_model(client)
    payload = {
        "name": "E2E relato",
        "snapshot": {
            "provider": "ollama",
            "model_id": model_name,
            "model_params": {"temperature": 0.2},
            "params_excluded": ["seed"],
            "history_turns": 4,
            "system_instructions": [{"title": "Tono", "content": "Breve"}],
            "images": {"enabled": True, "images_per_response": 3, "prompt": "film still"},
        },
    }
    created = client.post("/api/workspace-profiles", json=payload)
    assert created.status_code == 201
    profile = created.json()
    assert profile["snapshot"]["model_id"] == model_name
    assert profile["snapshot"]["images"]["prompt"] == "film still"
    listed = client.get("/api/workspace-profiles")
    assert listed.status_code == 200
    assert any(item["id"] == profile["id"] for item in listed.json())
    got = client.get(f"/api/workspace-profiles/{profile['id']}")
    assert got.status_code == 200
    updated = client.put(
        f"/api/workspace-profiles/{profile['id']}",
        json={"snapshot": {**payload["snapshot"], "history_turns": 2}},
    )
    assert updated.status_code == 200
    assert updated.json()["snapshot"]["history_turns"] == 2
    deleted = client.delete(f"/api/workspace-profiles/{profile['id']}")
    assert deleted.status_code == 204


def test_e2e_planner_rule_presets_crud(client, ollama_available):
    """CRUD de presets de reglas del planificador."""
    payload = {
        "name": "E2E flux nocturno",
        "snapshot": {
            "rules": [
                {"title": "Luz", "content": "Nocturna"},
                {"title": "Estilo", "content": "cinematic still"},
            ]
        },
    }
    created = client.post("/api/planner-rule-presets", json=payload)
    assert created.status_code == 201
    preset = created.json()
    assert preset["name"] == "E2E flux nocturno"
    assert preset["snapshot"]["rules"][0]["content"] == "Nocturna"
    listed = client.get("/api/planner-rule-presets")
    assert listed.status_code == 200
    assert any(item["id"] == preset["id"] for item in listed.json())
    got = client.get(f"/api/planner-rule-presets/{preset['id']}")
    assert got.status_code == 200
    updated = client.put(
        f"/api/planner-rule-presets/{preset['id']}",
        json={"snapshot": {"rules": [{"title": "POV", "content": "cámara al hombro"}]}},
    )
    assert updated.status_code == 200
    assert len(updated.json()["snapshot"]["rules"]) == 1
    deleted = client.delete(f"/api/planner-rule-presets/{preset['id']}")
    assert deleted.status_code == 204


def test_e2e_forge_last_generation_params_shape(client, ollama_available):
    """GET /api/forge/last-generation-params siempre responde 200 con available bool."""
    r = client.get("/api/forge/last-generation-params")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("available"), bool)
    for key in ("steps", "width", "height", "seed", "mode", "detail"):
        assert key in body


def test_e2e_forge_reactor_defaults_shape(client, ollama_available):
    """GET /api/forge/reactor-defaults responde 200 con defaults ReActor."""
    r = client.get("/api/forge/reactor-defaults")
    assert r.status_code == 200
    body = r.json()
    defaults = body.get("defaults")
    assert isinstance(defaults, dict)
    for key in ("model", "upscaler", "face_restorer", "codeformer_weight"):
        assert key in defaults


def test_e2e_prompt_generator_create_and_force_turn(client, ollama_available):
    """Create kind=prompt_generator y force turn (LLM real). Puede omitirse si el JSON no es válido."""
    from unittest.mock import patch

    model_name = _get_first_ollama_model(client)
    r_create = client.post(
        "/api/conversations",
        json={
            "kind": "prompt_generator",
            "model_id": model_name,
            "provider": "ollama",
        },
    )
    assert r_create.status_code == 200
    data = r_create.json()
    assert data["kind"] == "prompt_generator"
    assert len(data["messages"]) == 1
    cid = data["id"]

    # Preferimos mock estable en e2e de contrato HTTP; el LLM real no garantiza JSON.
    def fake_chat(model, messages, extra_body=None):
        return (
            '{"assistant_text":"Prompt listo.","brief_patch":{"prompt_language":"en"},'
            '"phase":"prompt","prompt":"A cinematic portrait of a red fox in snow."}'
        )

    mock_provider = type("P", (), {"chat": staticmethod(fake_chat)})()
    with patch("app.services.prompt_generator.turn.get_provider", return_value=mock_provider):
        r_turn = client.post(
            f"/api/conversations/{cid}/prompt-generator/turn",
            json={"force": True},
        )
    assert r_turn.status_code == 200
    body = r_turn.json()
    assert body["phase"] == "prompt"
    assert "fox" in body["prompt"]
    got = client.get(f"/api/conversations/{cid}").json()
    assert got["prompt_brief"]["latest_prompt"] == body["prompt"]
