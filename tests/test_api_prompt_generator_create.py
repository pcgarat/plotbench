"""API: create de conversaciones prompt_generator."""

from app.services.prompt_generator.system import INITIAL_ASSISTANT_TEMPLATE


def test_create_default_kind_is_chat(client):
    r = client.post("/api/conversations", json={"title": "Normal", "model_id": "m"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "chat"
    assert data["prompt_brief"] is None or data["prompt_brief"].get("prompt_language") is None
    assert data["messages"] == []


def test_create_prompt_generator_seeds_template_and_brief(client):
    r = client.post(
        "/api/conversations",
        json={"kind": "prompt_generator", "model_id": "m", "provider": "ollama"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "prompt_generator"
    assert data["title"] == "txt2img"
    assert isinstance(data["prompt_brief"], dict)
    assert data["prompt_brief"].get("latest_prompt") is None
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "assistant"
    assert data["messages"][0]["content"] == INITIAL_ASSISTANT_TEMPLATE


def test_get_prompt_generator_conversation_returns_kind_and_brief(client):
    create = client.post(
        "/api/conversations",
        json={"kind": "prompt_generator", "model_id": "m"},
    )
    cid = create.json()["id"]
    r = client.get(f"/api/conversations/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "prompt_generator"
    assert "prompt_brief" in data
    assert len(data["messages"]) == 1


def test_create_rejects_invalid_kind(client):
    r = client.post("/api/conversations", json={"kind": "foo", "model_id": "m"})
    assert r.status_code == 422


def test_fork_prompt_generator_preserves_kind_and_brief(client):
    from unittest.mock import patch

    create = client.post("/api/conversations", json={"kind": "prompt_generator", "model_id": "m"})
    cid = create.json()["id"]
    anchor = create.json()["messages"][0]["id"]

    def fake_chat(model, messages, extra_body=None):
        return (
            '{"assistant_text":"ok","brief_patch":{"prompt_language":"en","lighting":"neon"},'
            '"phase":"interview","prompt":null}'
        )

    mock_provider = type("P", (), {"chat": staticmethod(fake_chat)})()
    with patch("app.services.prompt_generator.turn.get_provider", return_value=mock_provider):
        client.post(
            f"/api/conversations/{cid}/prompt-generator/turn",
            json={"message": "inglés"},
        )

    origin = client.get(f"/api/conversations/{cid}").json()
    r = client.post(f"/api/conversations/{cid}/fork", json={"message_id": anchor})
    assert r.status_code == 200
    child = r.json()
    assert child["kind"] == "prompt_generator"
    assert child["prompt_brief"]["prompt_language"] == "en"
    assert child["prompt_brief"]["lighting"] == "neon"
    assert child["messages"] == []
    assert child["forked_from_conversation_id"] == cid


def test_turn_prompt_generator_usa_y_persiste_el_modelo_elegido(client):
    from unittest.mock import patch

    seen = {}

    def fake_chat(model, messages, extra_body=None):
        seen["model"] = model
        return '{"assistant_text":"ok","brief_patch":{},"phase":"interview","prompt":null}'

    mock_provider = type("P", (), {"chat": staticmethod(fake_chat)})()
    cid = client.post(
        "/api/conversations",
        json={"kind": "prompt_generator", "model_id": "base", "provider": "ollama"},
    ).json()["id"]

    with patch("app.services.prompt_generator.turn.get_provider", return_value=mock_provider):
        r = client.post(
            f"/api/conversations/{cid}/prompt-generator/turn",
            json={"message": "hola", "provider": "mancer", "model": "mistral-large"},
        )
    assert r.status_code == 200
    assert seen["model"] == "mistral-large"
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["provider"] == "mancer"
    assert conv["model_id"] == "mistral-large"
