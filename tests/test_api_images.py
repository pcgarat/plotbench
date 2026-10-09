"""Tests del endpoint de ilustración."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.image_illustration.models import IllustrationEvent


def _ndjson_lines(response):
    text = response.content.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_illustrate_404_conversation(client):
    res = client.post(
        "/api/conversations/no-existe/messages/m1/illustrate",
        json={"prompt_model": "llama3.2", "images_per_response": 1},
    )
    assert res.status_code == 404


def test_illustrate_at_404_conversation(client):
    res = client.post(
        "/api/conversations/no-existe/messages/m1/illustrations/illustrate-at",
        json={"prompt_model": "llama3.2", "paragraph_index": 0},
    )
    assert res.status_code == 404


def test_illustrate_at_rejects_user_message(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "user", "Párrafo uno.\n\nPárrafo dos.")
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/illustrate-at",
        json={"prompt_model": "llama3.2", "paragraph_index": 0},
    )
    assert res.status_code == 400
    assert "assistant" in res.json()["detail"].lower()


def test_illustrate_at_rejects_out_of_range_paragraph(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Solo un párrafo.")
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/illustrate-at",
        json={"prompt_model": "llama3.2", "paragraph_index": 3},
    )
    assert res.status_code == 400
    assert "rango" in res.json()["detail"].lower()


def test_illustrate_at_stream_forwards_paragraph_and_excerpt(client, db_session):
    from app import crud
    from app.services.image_illustration.models import ForgeParamOverrides

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Uno.\n\nDos.\n\nTres.")
    captured: dict = {}

    class FakeOrch:
        def run_at(
            self,
            text,
            *,
            paragraph_index,
            selected_excerpt="",
            retries=0,
            prompt="",
            include_prompt_debug=False,
            existing_prompts=None,
            forge_overrides=None,
            run_context=None,
            visual_consistency=True,
        ):
            captured["paragraph_index"] = paragraph_index
            captured["selected_excerpt"] = selected_excerpt
            captured["forge_overrides"] = forge_overrides
            yield IllustrationEvent(type="done", message="ok", content=text)

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/illustrate-at",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "paragraph_index": 1,
                "selected_excerpt": "Dos.",
                "retries": 0,
                "steps": 20,
                "debug": False,
            },
        )
    assert res.status_code == 200
    assert captured["paragraph_index"] == 1
    assert captured["selected_excerpt"] == "Dos."
    ov = captured["forge_overrides"]
    assert isinstance(ov, ForgeParamOverrides)
    assert ov.as_dict() == {"steps": 20}
    lines = _ndjson_lines(res)
    assert lines[-1]["type"] == "done"


def test_illustrate_stream_skips_when_planner_says_no(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "2+2=4")

    events_iter = iter(
        [
            IllustrationEvent(type="log", message="plan"),
            IllustrationEvent(type="done", message="sin ilustración", content="2+2=4"),
        ]
    )

    class FakeOrch:
        def run(self, *a, **k):
            yield from events_iter

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "images_per_response": 2,
                "retries": 0,
                "debug": False,
            },
        )
    assert res.status_code == 200
    lines = _ndjson_lines(res)
    assert lines[-1]["type"] == "done"
    assert not any(l["type"] == "log" for l in lines)  # debug off


def test_illustrate_always_forwards_status_events(client, db_session):
    """type=status no depende de debug (barra de estado)."""
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "texto")

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(
                type="status",
                message="Planificando escenas",
                data={"code": "images.planning"},
            )
            yield IllustrationEvent(type="log", message="oculto sin debug")
            yield IllustrationEvent(type="done", message="ok", content="texto")

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "images_per_response": 1,
                "debug": False,
            },
        )
    assert res.status_code == 200
    lines = _ndjson_lines(res)
    assert any(l["type"] == "status" and l["data"]["code"] == "images.planning" for l in lines)
    assert not any(l["type"] == "log" for l in lines)


def test_illustrate_emits_logs_when_debug(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un bosque.")

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(type="log", message="hola debug")
            yield IllustrationEvent(
                type="done",
                content='Había un bosque.\n<img src="/api/illustrated-images/x.png" class="chat-illustration" />',
            )

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "m",
                "images_per_response": 1,
                "debug": True,
            },
        )
    lines = _ndjson_lines(res)
    assert any(l["type"] == "log" for l in lines)
    refreshed = crud.get_message(db_session, conv.id, msg.id)
    assert "chat-illustration" in refreshed.content


def test_persist_illustrated_image_meta_retries_on_lock(client, db_session, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app import crud
    from app.routers import api_images

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "texto")
    attempts = {"n": 0}
    real = crud.save_illustrated_image_meta

    def flaky(db, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OperationalError("database is locked", {}, None)
        return real(db, **kwargs)

    monkeypatch.setattr(api_images.crud, "save_illustrated_image_meta", flaky)
    api_images._persist_illustrated_image_meta(
        message_id=msg.id,
        filename="retry.jpg",
        scene_id="s1",
        mode="txt2img",
        params={"prompt": "faro"},
    )
    assert attempts["n"] == 3
    row = crud.get_illustrated_image_meta(db_session, "retry.jpg")
    assert row is not None
    assert row.filename == "retry.jpg"


def test_illustrate_strips_missing_files_before_orchestrator(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    content = (
        'A\n<img src="/api/illustrated-images/fake_s1.jpg" class="chat-illustration" />\nB'
    )
    msg = crud.add_message(db_session, conv.id, "assistant", content)
    captured = {}

    class FakeOrch:
        def run(self, text, *a, **k):
            captured["text"] = text
            yield IllustrationEvent(type="done", content=text)

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={"prompt_model": "m", "images_per_response": 1, "debug": True},
        )
    assert res.status_code == 200
    assert "<img" not in captured["text"]
    assert "A" in captured["text"] and "B" in captured["text"]
    refreshed = crud.get_message(db_session, conv.id, msg.id)
    assert refreshed is not None
    assert "<img" not in (refreshed.content or "")


def test_get_illustrated_image_404(client):
    res = client.get("/api/illustrated-images/no-such.png")
    assert res.status_code == 404


def test_get_illustrated_image_ok(client, tmp_path, monkeypatch):
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path)
    name = storage.save_illustrated_image("s1", b"\x89PNG\r\n\x1a\n")
    res = client.get(f"/api/illustrated-images/{name}")
    assert res.status_code == 200
    assert res.content.startswith(b"\x89PNG")
    assert res.headers["content-type"].startswith("image/png")


def test_get_illustrated_image_serves_jpeg_bytes_as_jpeg_even_if_png_extension(
    client, tmp_path, monkeypatch
):
    """Forge a menudo devuelve JPEG guardado como *.png; el Content-Type debe oler el fichero."""
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    name = "6f9e20a6c846481bb7edbbe9cf9d6db1_s3.png"
    # Cabecera JPEG mínima (JFIF)
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32
    (tmp_path / name).write_bytes(jpeg)
    res = client.get(f"/api/illustrated-images/{name}")
    assert res.status_code == 200
    assert res.content.startswith(b"\xff\xd8\xff")
    assert res.headers["content-type"].startswith("image/jpeg")


def test_illustrate_forwards_panel_prompt_to_orchestrator(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un faro.")
    captured: dict = {}

    class FakeOrch:
        def run(self, text, *, max_images, retries, prompt="", include_prompt_debug=False, batch_size=10, existing_prompts=None, forge_overrides=None, run_context=None, visual_consistency=True, scene_selection_strategy="distributed"):
            captured["prompt"] = prompt
            captured["max_images"] = max_images
            captured["batch_size"] = batch_size
            captured["forge_overrides"] = forge_overrides
            yield IllustrationEvent(type="done", message="ok", content=text)

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "images_per_response": 1,
                "batch_size": 7,
                "retries": 0,
                "prompt": "oil painting, detailed",
            },
        )
    assert res.status_code == 200
    assert captured["prompt"] == "oil painting, detailed"
    assert captured["batch_size"] == 7
    assert _ndjson_lines(res)[-1]["type"] == "done"


def test_illustrate_forwards_forge_param_overrides_to_orchestrator(client, db_session):
    from app import crud
    from app.services.image_illustration.models import ForgeParamOverrides

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un faro.")
    captured: dict = {}

    class FakeOrch:
        def run(self, text, *, max_images, retries, prompt="", include_prompt_debug=False, batch_size=10, existing_prompts=None, forge_overrides=None, run_context=None, visual_consistency=True, scene_selection_strategy="distributed"):
            captured["forge_overrides"] = forge_overrides
            yield IllustrationEvent(type="done", message="ok", content=text)

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "images_per_response": 1,
                "retries": 0,
                "steps": 28,
                "width": 768,
                "height": 1024,
                "seed": -1,
            },
        )
    assert res.status_code == 200
    ov = captured["forge_overrides"]
    assert isinstance(ov, ForgeParamOverrides)
    assert ov.as_dict() == {"steps": 28, "width": 768, "height": 1024, "seed": -1}


def test_generate_remaining_forwards_forge_param_overrides(client, db_session):
    from app import crud
    from app.services.image_illustration.models import ForgeParamOverrides

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(
        db_session,
        conv.id,
        "assistant",
        '<span class="chat-illustration-placeholder" data-scene="s1" data-prompt="x">x</span>',
    )
    captured: dict = {}

    class FakeOrch:
        def run_remaining(self, text, *, retries, batch_size=10, forge_overrides=None, run_context=None):
            captured["forge_overrides"] = forge_overrides
            yield IllustrationEvent(type="done", message="ok", content=text)

    with patch("app.routers.api_images._build_forge_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/generate-remaining",
            json={"retries": 0, "steps": 12, "seed": 42},
        )
    assert res.status_code == 200
    ov = captured["forge_overrides"]
    assert isinstance(ov, ForgeParamOverrides)
    assert ov.as_dict() == {"steps": 12, "seed": 42}


def test_forge_reactor_defaults_api(client):
    res = client.get("/api/forge/reactor-defaults")
    assert res.status_code == 200
    data = res.json()
    assert "defaults" in data
    defaults = data["defaults"]
    assert defaults["model"] == "inswapper_128.onnx"
    assert "upscaler" in defaults
    assert "codeformer_weight" in defaults
    assert "gender_source" in defaults


def test_forge_last_generation_params_unavailable_without_data_path(client, monkeypatch):
    monkeypatch.setattr("app.routers.api_images.settings.forge_data_path", "")
    res = client.get("/api/forge/last-generation-params")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "FORGE_DATA_PATH" in (body.get("detail") or "")


def test_forge_last_generation_params_ok(client, tmp_path, monkeypatch):
    from tests.fixtures_forge_infotext import SAMPLE_PARAMS_TXT_IMG2IMG

    out = tmp_path / "output" / "txt2img-images"
    out.mkdir(parents=True)
    (out / "last.png").write_bytes(b"\x89PNGx")
    (tmp_path / "params.txt").write_text(SAMPLE_PARAMS_TXT_IMG2IMG, encoding="utf-8")
    monkeypatch.setattr("app.routers.api_images.settings.forge_data_path", str(tmp_path))
    monkeypatch.setattr("app.routers.api_images.settings.forge_base_url", "http://127.0.0.1:9")

    res = client.get("/api/forge/last-generation-params")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["steps"] == 8
    assert body["width"] == 1024
    assert body["height"] == 1024
    assert body["seed"] == 3815280852
    assert body["mode"] in ("txt2img", "img2img")


def test_build_orchestrator_passes_prompt_system_instructions():
    from app.routers.api_images import _build_orchestrator
    from app.schemas import IllustrateRequest

    captured: dict = {}

    with (
        patch("app.routers.api_images.get_provider", return_value=MagicMock()),
        patch("app.routers.api_images.LlmScenePlanner") as mock_planner,
        patch("app.routers.api_images.FileSystemLastPayloadSource"),
        patch("app.routers.api_images.ForgeHttpClient"),
    ):
        mock_planner.side_effect = lambda **kwargs: captured.update(kwargs) or MagicMock()
        body = IllustrateRequest(
            prompt_model="llama3.2",
            prompt_system_instructions="Prefiere iluminación nocturna",
        )
        _build_orchestrator(body)
    assert captured.get("system_instructions") == "Prefiere iluminación nocturna"


def test_build_orchestrator_use_chat_config_takes_conv_model_rules_and_params(db_session):
    from app import crud
    from app.routers.api_images import _build_orchestrator
    from app.schemas import IllustrateRequest

    rule = crud.create_rule(db_session, title="Estilo", content="Narración en segunda persona")
    conv = crud.create_conversation(
        db_session,
        title="t",
        model_id="abliterated-model",
        provider="abliteration",
        instruction_ids=[rule.id],
    )
    crud.update_conversation(
        db_session,
        conv.id,
        model_params={"temperature": 0.3, "top_p": 0.9},
    )
    conv = crud.get_conversation(db_session, conv.id)
    captured: dict = {}
    provider_calls: list = []

    with (
        patch("app.routers.api_images.get_provider") as mock_get,
        patch("app.routers.api_images.LlmScenePlanner") as mock_planner,
        patch("app.routers.api_images.FileSystemLastPayloadSource"),
        patch("app.routers.api_images.ForgeHttpClient"),
        patch(
            "app.routers.api_images.build_extra_body",
            return_value={"options": {"temperature": 0.3}},
        ) as mock_extra,
    ):
        mock_get.side_effect = lambda name: provider_calls.append(name) or MagicMock()
        mock_planner.side_effect = lambda **kwargs: captured.update(kwargs) or MagicMock()
        body = IllustrateRequest(
            use_chat_config=True,
            prompt_model="ignored-model",
            prompt_provider="ollama",
            prompt_system_instructions="iluminación nocturna",
        )
        _build_orchestrator(body, conv=conv, db=db_session)

    assert provider_calls == ["abliteration"]
    assert captured.get("model") == "abliterated-model"
    system = captured.get("system_instructions") or ""
    assert "Narración en segunda persona" in system
    assert "iluminación nocturna" in system
    assert captured.get("extra_body") == {"options": {"temperature": 0.3}}
    mock_extra.assert_called_once()
    assert mock_extra.call_args[0][0] == "abliteration"
    assert mock_extra.call_args.kwargs.get("model_id") == "abliterated-model"


def test_build_orchestrator_uses_prompt_model_params_when_not_chat_config():
    from app.routers.api_images import _build_orchestrator
    from app.schemas import IllustrateRequest

    captured: dict = {}
    with (
        patch("app.routers.api_images.get_provider", return_value=MagicMock()),
        patch("app.routers.api_images.LlmScenePlanner") as mock_planner,
        patch("app.routers.api_images.FileSystemLastPayloadSource"),
        patch("app.routers.api_images.ForgeHttpClient"),
        patch(
            "app.routers.api_images.build_extra_body",
            return_value={"think": False, "options": {"temperature": 0.5}},
        ) as mock_extra,
    ):
        mock_planner.side_effect = lambda **kwargs: captured.update(kwargs) or MagicMock()
        body = IllustrateRequest(
            prompt_provider="ollama",
            prompt_model="gemma4:31b-cloud",
            prompt_model_params={"think": False, "temperature": 0.5, "num_ctx": 16384},
        )
        _build_orchestrator(body)

    mock_extra.assert_called_once()
    assert mock_extra.call_args[0][0] == "ollama"
    assert mock_extra.call_args[0][1] == {"think": False, "temperature": 0.5, "num_ctx": 16384}
    assert mock_extra.call_args.kwargs.get("model_id") == "gemma4:31b-cloud"
    assert captured.get("extra_body") == {"think": False, "options": {"temperature": 0.5}}


def test_build_orchestrator_chat_config_prefers_live_prompt_model_params(db_session):
    """Con use_chat_config, params vivos del body ganan sobre los de BD (UI actual)."""
    from app import crud
    from app.routers.api_images import _build_orchestrator
    from app.schemas import IllustrateRequest

    conv = crud.create_conversation(
        db_session, title="t", model_id="m1", provider="ollama"
    )
    crud.update_conversation(db_session, conv.id, model_params={"temperature": 0.2})
    conv = crud.get_conversation(db_session, conv.id)
    captured: dict = {}
    with (
        patch("app.routers.api_images.get_provider", return_value=MagicMock()),
        patch("app.routers.api_images.LlmScenePlanner") as mock_planner,
        patch("app.routers.api_images.FileSystemLastPayloadSource"),
        patch("app.routers.api_images.ForgeHttpClient"),
        patch(
            "app.routers.api_images.build_extra_body",
            return_value={"options": {"temperature": 0.9}},
        ) as mock_extra,
    ):
        mock_planner.side_effect = lambda **kwargs: captured.update(kwargs) or MagicMock()
        body = IllustrateRequest(
            use_chat_config=True,
            prompt_model="ignored",
            prompt_model_params={"temperature": 0.9, "think": "max"},
        )
        _build_orchestrator(body, conv=conv, db=db_session)

    assert mock_extra.call_args[0][1] == {"temperature": 0.9, "think": "max"}
    assert captured.get("extra_body") == {"options": {"temperature": 0.9}}


def test_build_orchestrator_chat_config_falls_back_to_conv_params_when_body_empty(db_session):
    from app import crud
    from app.routers.api_images import _build_orchestrator
    from app.schemas import IllustrateRequest

    conv = crud.create_conversation(
        db_session, title="t", model_id="m1", provider="ollama"
    )
    crud.update_conversation(db_session, conv.id, model_params={"temperature": 0.2})
    conv = crud.get_conversation(db_session, conv.id)
    with (
        patch("app.routers.api_images.get_provider", return_value=MagicMock()),
        patch("app.routers.api_images.LlmScenePlanner"),
        patch("app.routers.api_images.FileSystemLastPayloadSource"),
        patch("app.routers.api_images.ForgeHttpClient"),
        patch(
            "app.routers.api_images.build_extra_body",
            return_value={"options": {"temperature": 0.2}},
        ) as mock_extra,
    ):
        body = IllustrateRequest(
            use_chat_config=True,
            prompt_model="ignored",
            prompt_model_params={},
        )
        _build_orchestrator(body, conv=conv, db=db_session)

    assert mock_extra.call_args[0][1] == {"temperature": 0.2}


def test_illustrate_request_requires_prompt_model_unless_use_chat_config():
    from pydantic import ValidationError

    from app.schemas import IllustrateRequest

    with pytest.raises(ValidationError):
        IllustrateRequest(prompt_model="", use_chat_config=False)
    ok = IllustrateRequest(prompt_model="", use_chat_config=True)
    assert ok.use_chat_config is True


def test_illustrate_request_allows_more_than_20_images_per_response():
    from app.schemas import IllustrateRequest

    req = IllustrateRequest(prompt_model="m", images_per_response=50)
    assert req.images_per_response == 50


def test_illustrate_request_visual_consistency_defaults_true():
    from app.schemas import IllustrateRequest

    assert IllustrateRequest(prompt_model="m").visual_consistency is True
    off = IllustrateRequest(prompt_model="m", visual_consistency=False)
    assert off.visual_consistency is False


def test_illustrate_forwards_visual_consistency_to_orchestrator(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un faro.")
    captured: dict = {}

    class FakeOrch:
        def run(
            self,
            text,
            *,
            max_images,
            retries,
            prompt="",
            include_prompt_debug=False,
            batch_size=10,
            existing_prompts=None,
            forge_overrides=None,
            run_context=None,
            visual_consistency=True,
            scene_selection_strategy="distributed",
        ):
            captured["visual_consistency"] = visual_consistency
            captured["scene_selection_strategy"] = scene_selection_strategy
            yield IllustrationEvent(type="done", message="ok", content=text)

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        omitted = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={"prompt_model": "llama3.2", "images_per_response": 1, "retries": 0},
        )
        assert omitted.status_code == 200
        assert captured["visual_consistency"] is True
        assert captured["scene_selection_strategy"] == "distributed"
        off = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "images_per_response": 1,
                "retries": 0,
                "visual_consistency": False,
                "scene_selection_strategy": "llm_erotic_story",
            },
        )
        assert off.status_code == 200
        assert captured["visual_consistency"] is False
        assert captured["scene_selection_strategy"] == "llm_erotic_story"


def test_illustrate_request_scene_selection_strategy_defaults_and_normalizes():
    from app.schemas import IllustrateRequest

    assert IllustrateRequest(prompt_model="m").scene_selection_strategy == "distributed"
    erotic = IllustrateRequest(
        prompt_model="m", scene_selection_strategy="llm_erotic_story"
    )
    assert erotic.scene_selection_strategy == "llm_erotic_story"
    unknown = IllustrateRequest(prompt_model="m", scene_selection_strategy="weird")
    assert unknown.scene_selection_strategy == "distributed"


def test_illustrate_request_batch_size_defaults_to_10():
    from app.schemas import GenerateRemainingRequest, IllustrateRequest

    assert IllustrateRequest(prompt_model="m").batch_size == 10
    assert GenerateRemainingRequest().batch_size == 10


def test_illustrate_accepts_concatenated_builtin_planner_guides(client, db_session):
    """El botón de ilustrar envía las reglas del planificador concatenadas; no debe 422."""
    from app import crud
    from app.services.rules.compose import concat_instruction_texts
    from app.services.rules.seed import (
        FLUX_PROMPT_GUIDE_PATH,
        KREA2_PHOTOREALISM_PATH,
        KREA2_POV_GUIDE_PATH,
    )

    extra = concat_instruction_texts(
        FLUX_PROMPT_GUIDE_PATH.read_text(encoding="utf-8"),
        KREA2_POV_GUIDE_PATH.read_text(encoding="utf-8"),
        KREA2_PHOTOREALISM_PATH.read_text(encoding="utf-8"),
    )
    assert "Guía de prompts visuales (FLUX)" in extra
    assert "Empieza cada prompt con `POV.`" in extra
    assert "KREA 2 - FOTOREALISMO" in extra

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un faro al anochecer.")

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(type="done", message="ok", content="Había un faro al anochecer.")

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={
                "prompt_model": "llama3.2",
                "prompt_provider": "ollama",
                "images_per_response": 1,
                "prompt_system_instructions": extra,
            },
        )
    assert res.status_code == 200, res.text


def test_illustrate_request_forge_param_overrides_optional():
    from pydantic import ValidationError

    from app.schemas import GenerateRemainingRequest, IllustrateRequest

    req = IllustrateRequest(prompt_model="m", steps=20, width=832, height=1216, seed=-1)
    assert req.steps == 20
    assert req.seed == -1
    rem = GenerateRemainingRequest(width=1024)
    assert rem.width == 1024
    assert rem.steps is None
    with pytest.raises(ValidationError):
        IllustrateRequest(prompt_model="m", steps=0)
    with pytest.raises(ValidationError):
        IllustrateRequest(prompt_model="m", width=32)


def test_illustrate_request_empty_panel_placeholders_are_none():
    """Inputs vacíos del panel (placeholder «del último gen» / «.env») no deben 422."""
    from app.schemas import IllustrateRequest, WorkspaceImagesSnapshot

    req = IllustrateRequest.model_validate(
        {
            "prompt_model": "m",
            "steps": "",
            "width": "",
            "height": "",
            "seed": "",
            "reactor": {"enabled": False, "codeformer_weight": ""},
        }
    )
    assert req.steps is None
    assert req.width is None
    assert req.reactor.codeformer_weight is None
    snap = WorkspaceImagesSnapshot.model_validate(
        {"reactor": {"codeformer_weight": ""}}
    )
    assert snap.reactor.codeformer_weight is None


def test_clear_photos_deletes_files_and_updates_content(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("s1", b"\x89PNG\r\n\x1a\n")
    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    content = (
        f'Había un faro.\n<img src="/api/illustrated-images/{name}" class="chat-illustration" />\n'
        "⟦img:s2⟧"
    )
    msg = crud.add_message(db_session, conv.id, "assistant", content)
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/clear-photos"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["deleted_files"] == 1
    assert "<img" not in body["content"]
    assert "⟦img:s2⟧" in body["content"]
    assert "faro" in body["content"]
    assert not (tmp_path / "illustrated" / name).is_file()
    refreshed = crud.get_message(db_session, conv.id, msg.id)
    assert refreshed is not None
    assert refreshed.content == body["content"]


def test_prune_orphans_keeps_photos(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("keep", b"\x89PNG\r\n\x1a\n")
    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    content = (
        f'A\n<img src="/api/illustrated-images/{name}" class="chat-illustration" />\n'
        "⟦img:s1⟧\n"
        '<span class="chat-illustration-error" data-scene="s2">fail</span>\nB'
    )
    msg = crud.add_message(db_session, conv.id, "assistant", content)
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/prune-orphans"
    )
    assert res.status_code == 200
    body = res.json()
    assert name in body["content"]
    assert "⟦img:" not in body["content"]
    assert "chat-illustration-error" not in body["content"]
    assert "A" in body["content"] and "B" in body["content"]


def test_prune_orphans_drops_imgs_without_file(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    content = (
        'A\n<img src="/api/illustrated-images/fake_s1.jpg" class="chat-illustration" />\nB'
    )
    msg = crud.add_message(db_session, conv.id, "assistant", content)
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/prune-orphans"
    )
    assert res.status_code == 200
    assert "<img" not in res.json()["content"]
    assert "A" in res.json()["content"] and "B" in res.json()["content"]


def _origin_fork_with_assistant(db_session, assistant_content="Ra"):
    from app import crud

    origin = crud.create_conversation(db_session, title="Origen", model_id="m", provider="ollama")
    crud.add_message(db_session, origin.id, "user", "A")
    assistant = crud.add_message(db_session, origin.id, "assistant", assistant_content)
    child = crud.fork_conversation(db_session, origin.id, assistant.id)
    return origin, assistant, child


def test_clear_photos_from_fork_mutates_origin_and_sibling(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("s1", b"\x89PNG\r\n\x1a\n")
    content = (
        f'Había un faro.\n<img src="/api/illustrated-images/{name}" class="chat-illustration" />\n'
        "⟦img:s2⟧"
    )
    origin, assistant, child = _origin_fork_with_assistant(db_session, content)
    sibling = crud.fork_conversation(db_session, origin.id, assistant.id)

    res = client.post(
        f"/api/conversations/{child.id}/messages/{assistant.id}/illustrations/clear-photos"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["deleted_files"] == 1
    assert "<img" not in body["content"]
    assert "⟦img:s2⟧" in body["content"]
    assert not (tmp_path / "illustrated" / name).is_file()

    origin_msg = crud.get_message(db_session, origin.id, assistant.id)
    assert origin_msg is not None
    assert origin_msg.content == body["content"]
    sibling_inherited = crud.get_inherited_prefix(db_session, sibling)
    assert sibling_inherited[-1].content == body["content"]


def test_prune_orphans_from_fork_mutates_origin(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("keep", b"\x89PNG\r\n\x1a\n")
    content = (
        f'A\n<img src="/api/illustrated-images/{name}" class="chat-illustration" />\n'
        "⟦img:s1⟧\n"
        '<span class="chat-illustration-error" data-scene="s2">fail</span>\nB'
    )
    origin, assistant, child = _origin_fork_with_assistant(db_session, content)
    res = client.post(
        f"/api/conversations/{child.id}/messages/{assistant.id}/illustrations/prune-orphans"
    )
    assert res.status_code == 200
    body = res.json()
    assert name in body["content"]
    assert "⟦img:" not in body["content"]
    assert "chat-illustration-error" not in body["content"]
    origin_msg = crud.get_message(db_session, origin.id, assistant.id)
    assert origin_msg is not None
    assert origin_msg.content == body["content"]


def test_illustration_ops_404_on_message_after_fork_anchor(client, db_session):
    from app import crud

    origin, assistant, child = _origin_fork_with_assistant(db_session)
    after = crud.add_message(db_session, origin.id, "assistant", "fuera del prefijo")
    res = client.post(
        f"/api/conversations/{child.id}/messages/{after.id}/illustrations/clear-photos"
    )
    assert res.status_code == 404


def test_illustrate_from_fork_persists_on_origin(client, db_session):
    from app import crud

    origin, assistant, child = _origin_fork_with_assistant(db_session, "Ra")
    sibling = crud.fork_conversation(db_session, origin.id, assistant.id)

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(type="done", content="Ra ilustrado")

    captured = {}

    def fake_build(body, *, conv=None, db=None):
        captured["conv_id"] = getattr(conv, "id", None)
        return FakeOrch()

    with patch("app.routers.api_images._build_orchestrator", side_effect=fake_build):
        res = client.post(
            f"/api/conversations/{child.id}/messages/{assistant.id}/illustrate",
            json={"prompt_model": "m", "images_per_response": 1, "debug": True},
        )
    assert res.status_code == 200
    assert captured["conv_id"] == child.id
    origin_msg = crud.get_message(db_session, origin.id, assistant.id)
    assert origin_msg is not None
    assert origin_msg.content == "Ra ilustrado"
    assert crud.get_inherited_prefix(db_session, sibling)[-1].content == "Ra ilustrado"


def test_generate_remaining_from_fork_persists_on_origin(client, db_session):
    from app import crud

    content = (
        'A\n<img src="/api/illustrated-images/keep.png" class="chat-illustration" />\n'
        '<span class="chat-illustration-placeholder" data-scene="s1" data-prompt="storm">'
        "pending</span>"
    )
    origin, assistant, child = _origin_fork_with_assistant(db_session, content)

    class FakeOrch:
        def run_remaining(self, *a, **k):
            yield IllustrationEvent(
                type="done",
                content=(
                    'A\n<img src="/api/illustrated-images/keep.png" class="chat-illustration" />\n'
                    '<img src="/api/illustrated-images/s1.png" alt="escena s1" class="chat-illustration" />'
                ),
            )

    with patch("app.routers.api_images._build_forge_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{child.id}/messages/{assistant.id}/illustrations/generate-remaining",
            json={"retries": 0},
        )
    assert res.status_code == 200
    origin_msg = crud.get_message(db_session, origin.id, assistant.id)
    assert origin_msg is not None
    assert "s1.png" in origin_msg.content


def test_clear_photos_rejects_user_message(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "user", "hola")
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/clear-photos"
    )
    assert res.status_code == 400


def test_generate_remaining_stream_regenerates_pending(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    content = (
        'A\n<img src="/api/illustrated-images/keep.png" class="chat-illustration" />\n'
        '<span class="chat-illustration-placeholder" data-scene="s1" data-prompt="storm">'
        "Generando imagen…\n\nstorm</span>\nB"
    )
    msg = crud.add_message(db_session, conv.id, "assistant", content)

    class FakeOrch:
        def run_remaining(self, text, *, retries, batch_size=10, forge_overrides=None, run_context=None):
            assert retries == 0
            assert batch_size == 5
            assert "data-prompt" in text
            new_content = (
                'A\n<img src="/api/illustrated-images/keep.png" class="chat-illustration" />\n'
                '<img src="/api/illustrated-images/s1.png" alt="escena s1" class="chat-illustration" />\nB'
            )
            yield IllustrationEvent(type="log", message="restantes")
            yield IllustrationEvent(
                type="image",
                scene_id="s1",
                content=new_content,
                data={"filename": "s1.png", "params": {"prompt": "storm"}, "mode": "txt2img"},
            )
            yield IllustrationEvent(type="done", message="restantes completadas", content=new_content)

    with patch("app.routers.api_images._build_forge_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/generate-remaining",
            json={"retries": 0, "batch_size": 5, "debug": True},
        )
    assert res.status_code == 200
    lines = _ndjson_lines(res)
    assert lines[-1]["type"] == "done"
    assert any(l["type"] == "image" for l in lines)
    assert any(l["type"] == "log" for l in lines)
    refreshed = crud.get_message(db_session, conv.id, msg.id)
    assert refreshed is not None
    assert "s1.png" in (refreshed.content or "")
    assert "keep.png" in (refreshed.content or "")


def test_generate_remaining_rejects_user_message(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "user", "hola")
    res = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/generate-remaining",
        json={"retries": 0},
    )
    assert res.status_code == 400


def test_illustrated_image_meta_roundtrip(client, db_session, tmp_path, monkeypatch):
    from app import crud
    from app.services.image_illustration import storage

    monkeypatch.setattr(storage, "DEFAULT_DIR", tmp_path / "illustrated")
    name = storage.save_illustrated_image("s1", b"\x89PNG\r\n\x1a\n")
    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", f'<img src="/api/illustrated-images/{name}" class="chat-illustration" />')
    crud.save_illustrated_image_meta(
        db_session,
        message_id=msg.id,
        filename=name,
        scene_id="s1",
        mode="txt2img",
        params={
            "prompt": "storm lighthouse",
            "steps": 8,
            "width": 768,
            "height": 512,
            "model": "flux.safetensors",
            "sampler_name": "Euler a",
            "seed": 99,
        },
    )
    res = client.get(f"/api/illustrated-images/{name}/meta")
    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == name
    assert body["scene_id"] == "s1"
    assert body["params"]["prompt"] == "storm lighthouse"
    assert body["params"]["width"] == 768
    assert body["params"]["model"] == "flux.safetensors"
    assert body["conversation_id"] == conv.id
    assert body["message_id"] == msg.id

    clear = client.post(
        f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/clear-photos"
    )
    assert clear.status_code == 200
    assert client.get(f"/api/illustrated-images/{name}/meta").status_code == 404


def _seed_gallery_image(
    db_session,
    *,
    conv,
    msg,
    filename: str,
    prompt: str,
    steps: int = 8,
    width: int = 768,
    height: int = 512,
    forge_model: str = "flux.safetensors",
    prompt_model: str | None = "llama3.2",
    prompt_provider: str | None = "ollama",
    mode: str = "txt2img",
    seed: int = 1,
    batch_id: str | None = None,
    created_at=None,
):
    from datetime import datetime

    from app import crud

    params = {
        "prompt": prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "model": forge_model,
        "sampler_name": "Euler a",
        "seed": seed,
    }
    if batch_id:
        params["batch_id"] = batch_id
    row = crud.save_illustrated_image_meta(
        db_session,
        message_id=msg.id,
        filename=filename,
        scene_id="s1",
        mode=mode,
        params=params,
        prompt_model=prompt_model,
        prompt_provider=prompt_provider,
    )
    if created_at is not None:
        row.created_at = created_at
        db_session.commit()
        db_session.refresh(row)
    elif row.created_at is None:
        row.created_at = datetime.utcnow()
        db_session.commit()
        db_session.refresh(row)
    return row


def test_illustrated_gallery_lists_newest_first(client, db_session):
    from datetime import datetime, timedelta

    from app import crud

    conv = crud.create_conversation(db_session, title="faro", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "x")
    older = datetime.utcnow() - timedelta(hours=2)
    newer = datetime.utcnow() - timedelta(hours=1)
    _seed_gallery_image(db_session, conv=conv, msg=msg, filename="old.png", prompt="old scene", created_at=older)
    _seed_gallery_image(db_session, conv=conv, msg=msg, filename="new.png", prompt="new scene", created_at=newer)

    res = client.get("/api/illustrated-images")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert [i["filename"] for i in body["items"]] == ["new.png", "old.png"]
    first = body["items"][0]
    assert first["conversation_id"] == conv.id
    assert first["conversation_title"] == "faro"
    assert first["message_id"] == msg.id
    assert first["prompt"] == "new scene"
    assert first["prompt_model"] == "llama3.2"
    assert first["forge_model"] == "flux.safetensors"
    assert first["url"] == "/api/illustrated-images/new.png"


def test_illustrated_gallery_filters_and_excludes_trash(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="a", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "x")
    _seed_gallery_image(
        db_session,
        conv=conv,
        msg=msg,
        filename="match.png",
        prompt="storm lighthouse at dusk",
        steps=20,
        width=832,
        height=1216,
        forge_model="flux.safetensors",
        prompt_model="qwen",
        prompt_provider="ollama",
        seed=42,
    )
    _seed_gallery_image(
        db_session,
        conv=conv,
        msg=msg,
        filename="other.png",
        prompt="cat in a kitchen",
        steps=8,
        width=768,
        height=512,
        forge_model="sdxl.safetensors",
        prompt_model="llama3.2",
        prompt_provider="mancer",
        mode="img2img",
        seed=99,
    )
    trashed = crud.create_conversation(db_session, title="papelera", model_id="m", provider="ollama")
    tmsg = crud.add_message(db_session, trashed.id, "assistant", "y")
    _seed_gallery_image(db_session, conv=trashed, msg=tmsg, filename="trashed.png", prompt="gone")
    crud.delete_conversation(db_session, trashed.id)

    listed = client.get("/api/illustrated-images").json()
    names = {i["filename"] for i in listed["items"]}
    assert names == {"match.png", "other.png"}

    by_llm = client.get("/api/illustrated-images", params={"prompt_model": "qwen"}).json()
    assert [i["filename"] for i in by_llm["items"]] == ["match.png"]

    by_forge = client.get("/api/illustrated-images", params={"forge_model": "sdxl.safetensors"}).json()
    assert [i["filename"] for i in by_forge["items"]] == ["other.png"]

    by_steps = client.get("/api/illustrated-images", params={"steps": 20}).json()
    assert [i["filename"] for i in by_steps["items"]] == ["match.png"]

    by_size = client.get("/api/illustrated-images", params={"size": "832x1216"}).json()
    assert [i["filename"] for i in by_size["items"]] == ["match.png"]

    by_mode = client.get("/api/illustrated-images", params={"mode": "img2img"}).json()
    assert [i["filename"] for i in by_mode["items"]] == ["other.png"]

    by_prompt = client.get("/api/illustrated-images", params={"prompt_q": "lighthouse"}).json()
    assert [i["filename"] for i in by_prompt["items"]] == ["match.png"]

    by_seed = client.get("/api/illustrated-images", params={"seed": 42}).json()
    assert [i["filename"] for i in by_seed["items"]] == ["match.png"]

    paged = client.get("/api/illustrated-images", params={"limit": 1, "offset": 0}).json()
    assert paged["total"] == 2
    assert len(paged["items"]) == 1


def test_illustrated_gallery_filters_missing_prompt_llm(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="a", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "x")
    _seed_gallery_image(
        db_session, conv=conv, msg=msg, filename="with.png", prompt="a", prompt_model="llama3.2"
    )
    _seed_gallery_image(
        db_session,
        conv=conv,
        msg=msg,
        filename="without.png",
        prompt="b",
        prompt_model=None,
        prompt_provider=None,
    )
    res = client.get("/api/illustrated-images", params={"prompt_model": ""})
    assert res.status_code == 200
    assert [i["filename"] for i in res.json()["items"]] == ["without.png"]


def test_illustrated_gallery_facets(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="a", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "x")
    _seed_gallery_image(
        db_session, conv=conv, msg=msg, filename="a.png", prompt="a", steps=8, prompt_model="llama3.2", seed=11
    )
    _seed_gallery_image(
        db_session,
        conv=conv,
        msg=msg,
        filename="b.png",
        prompt="b",
        steps=20,
        width=832,
        height=1216,
        prompt_model=None,
        prompt_provider=None,
        seed=22,
    )
    res = client.get("/api/illustrated-images/facets")
    assert res.status_code == 200
    body = res.json()
    assert "llama3.2" in body["prompt_models"]
    assert body["has_missing_prompt_llm"] is True
    assert 8 in body["steps"] and 20 in body["steps"]
    assert body["seeds"] == [11, 22]
    assert "768x512" in body["sizes"]
    assert "832x1216" in body["sizes"]
    assert body["batches"] == []


def test_illustrated_gallery_filters_by_batch_id(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="lotes", model_id="m", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "relato")
    _seed_gallery_image(
        db_session, conv=conv, msg=msg, filename="b1a.png", prompt="a", batch_id="batch-aaa"
    )
    _seed_gallery_image(
        db_session, conv=conv, msg=msg, filename="b1b.png", prompt="b", batch_id="batch-aaa"
    )
    _seed_gallery_image(
        db_session, conv=conv, msg=msg, filename="b2.png", prompt="c", batch_id="batch-bbb"
    )
    _seed_gallery_image(db_session, conv=conv, msg=msg, filename="orphan.png", prompt="d")

    by_batch = client.get("/api/illustrated-images", params={"batch_id": "batch-aaa"}).json()
    assert {i["filename"] for i in by_batch["items"]} == {"b1a.png", "b1b.png"}
    assert by_batch["total"] == 2
    assert all(i["batch_id"] == "batch-aaa" for i in by_batch["items"])

    multi = client.get(
        "/api/illustrated-images",
        params=[("batch_id", "batch-aaa"), ("batch_id", "batch-bbb")],
    ).json()
    assert {i["filename"] for i in multi["items"]} == {"b1a.png", "b1b.png", "b2.png"}
    assert multi["total"] == 3

    facets = client.get(
        "/api/illustrated-images/facets",
        params={"conversation_id": conv.id, "message_id": msg.id},
    ).json()
    batch_ids = [b["batch_id"] for b in facets["batches"]]
    assert set(batch_ids) == {"batch-aaa", "batch-bbb"}
    by_id = {b["batch_id"]: b["image_count"] for b in facets["batches"]}
    assert by_id["batch-aaa"] == 2
    assert by_id["batch-bbb"] == 1

    matching = client.get(
        "/api/illustrated-images/matching-filenames",
        params=[("conversation_id", conv.id), ("batch_id", "batch-bbb"), ("batch_id", "batch-aaa")],
    ).json()
    assert set(matching["filenames"]) == {"b1a.png", "b1b.png", "b2.png"}


def test_illustrated_gallery_filters_by_conversation_and_message(client, db_session):
    from app import crud

    conv_a = crud.create_conversation(db_session, title="faro", model_id="m", provider="ollama")
    conv_b = crud.create_conversation(db_session, title="otra", model_id="m", provider="ollama")
    msg_a1 = crud.add_message(db_session, conv_a.id, "assistant", "primer faro")
    msg_a2 = crud.add_message(db_session, conv_a.id, "assistant", "segundo faro")
    msg_b = crud.add_message(db_session, conv_b.id, "assistant", "otra escena")
    _seed_gallery_image(db_session, conv=conv_a, msg=msg_a1, filename="a1.png", prompt="lighthouse one")
    _seed_gallery_image(db_session, conv=conv_a, msg=msg_a2, filename="a2.png", prompt="lighthouse two")
    _seed_gallery_image(db_session, conv=conv_b, msg=msg_b, filename="b.png", prompt="kitchen")

    by_conv = client.get("/api/illustrated-images", params={"conversation_id": conv_a.id}).json()
    assert {i["filename"] for i in by_conv["items"]} == {"a1.png", "a2.png"}
    assert by_conv["total"] == 2

    by_msg = client.get(
        "/api/illustrated-images",
        params={"conversation_id": conv_a.id, "message_id": msg_a2.id},
    ).json()
    assert [i["filename"] for i in by_msg["items"]] == ["a2.png"]

    missing = client.get("/api/illustrated-images", params={"conversation_id": "no-such"}).json()
    assert missing["total"] == 0
    assert missing["items"] == []


def test_illustrated_gallery_matching_filenames_scoped_to_conversation(client, db_session):
    from app import crud

    conv_a = crud.create_conversation(db_session, title="faro", model_id="m", provider="ollama")
    conv_b = crud.create_conversation(db_session, title="otra", model_id="m", provider="ollama")
    msg_a = crud.add_message(db_session, conv_a.id, "assistant", "a")
    msg_b = crud.add_message(db_session, conv_b.id, "assistant", "b")
    _seed_gallery_image(
        db_session, conv=conv_a, msg=msg_a, filename="keep.png", prompt="lighthouse dusk", prompt_model="qwen", seed=7
    )
    _seed_gallery_image(
        db_session, conv=conv_a, msg=msg_a, filename="drop.png", prompt="kitchen cat", prompt_model="llama3.2", seed=8
    )
    _seed_gallery_image(
        db_session, conv=conv_b, msg=msg_b, filename="other-conv.png", prompt="lighthouse dusk", prompt_model="qwen", seed=7
    )

    missing_conv = client.get("/api/illustrated-images/matching-filenames")
    assert missing_conv.status_code == 422

    unknown = client.get(
        "/api/illustrated-images/matching-filenames", params={"conversation_id": "no-such"}
    )
    assert unknown.status_code == 404

    all_in_a = client.get(
        "/api/illustrated-images/matching-filenames", params={"conversation_id": conv_a.id}
    )
    assert all_in_a.status_code == 200
    assert set(all_in_a.json()["filenames"]) == {"keep.png", "drop.png"}

    by_llm = client.get(
        "/api/illustrated-images/matching-filenames",
        params={"conversation_id": conv_a.id, "prompt_model": "qwen", "prompt_q": "lighthouse"},
    )
    assert by_llm.status_code == 200
    assert by_llm.json()["filenames"] == ["keep.png"]

    by_seed = client.get(
        "/api/illustrated-images/matching-filenames",
        params={"conversation_id": conv_a.id, "seed": 8},
    )
    assert by_seed.json()["filenames"] == ["drop.png"]


def test_illustrated_gallery_includes_visible_history_on_fork(client, db_session):
    """Un fork ve ilustraciones del prefijo heredado y las propias, no las posteriores al ancla."""
    from app import crud

    origin, assistant, child = _origin_fork_with_assistant(db_session, "Ra")
    after_anchor = crud.add_message(db_session, origin.id, "assistant", "despues del ancla")
    fork_own = crud.add_message(db_session, child.id, "assistant", "solo del fork")
    _seed_gallery_image(
        db_session, conv=origin, msg=assistant, filename="inherited.png", prompt="prefijo"
    )
    _seed_gallery_image(
        db_session, conv=origin, msg=after_anchor, filename="after-anchor.png", prompt="origen tarde"
    )
    _seed_gallery_image(
        db_session, conv=child, msg=fork_own, filename="fork-own.png", prompt="rama"
    )

    by_fork = client.get("/api/illustrated-images", params={"conversation_id": child.id}).json()
    assert {i["filename"] for i in by_fork["items"]} == {"inherited.png", "fork-own.png"}
    assert by_fork["total"] == 2

    by_origin = client.get("/api/illustrated-images", params={"conversation_id": origin.id}).json()
    assert {i["filename"] for i in by_origin["items"]} == {"inherited.png", "after-anchor.png"}

    after_on_fork = client.get(
        "/api/illustrated-images",
        params={"conversation_id": child.id, "message_id": after_anchor.id},
    ).json()
    assert after_on_fork["total"] == 0

    chips = client.get(
        "/api/illustrated-images/messages", params={"conversation_id": child.id}
    ).json()["items"]
    assert [i["message_id"] for i in chips] == [assistant.id, fork_own.id]
    assert chips[0]["image_count"] == 1
    assert chips[1]["image_count"] == 1

    facets = client.get(
        "/api/illustrated-images/facets", params={"conversation_id": child.id}
    ).json()
    assert facets["prompt_models"] == ["llama3.2"]


def test_illustrated_gallery_message_summaries_and_trash(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="faro", model_id="m", provider="ollama")
    html_msg = crud.add_message(
        db_session,
        conv.id,
        "assistant",
        'Había un faro.\n<img src="/api/illustrated-images/a.png" class="chat-illustration" />',
    )
    later = crud.add_message(db_session, conv.id, "assistant", "Otra escena con el mismo faro de noche.")
    _seed_gallery_image(db_session, conv=conv, msg=html_msg, filename="a.png", prompt="lighthouse")
    _seed_gallery_image(db_session, conv=conv, msg=later, filename="b.png", prompt="lighthouse night")
    _seed_gallery_image(db_session, conv=conv, msg=later, filename="c.png", prompt="lighthouse close")

    res = client.get("/api/illustrated-images/messages", params={"conversation_id": conv.id})
    assert res.status_code == 200
    items = res.json()["items"]
    assert [i["message_id"] for i in items] == [html_msg.id, later.id]
    first = items[0]
    assert first["image_count"] == 1
    assert "faro" in first["excerpt"].lower()
    assert "<img" not in first["excerpt"]
    assert items[1]["image_count"] == 2

    missing = client.get("/api/illustrated-images/messages", params={"conversation_id": "no-such"})
    assert missing.status_code == 404

    crud.delete_conversation(db_session, conv.id)
    trashed = client.get("/api/illustrated-images/messages", params={"conversation_id": conv.id})
    assert trashed.status_code == 404
    listed = client.get("/api/illustrated-images", params={"conversation_id": conv.id}).json()
    assert listed["total"] == 0


def test_illustrated_gallery_facets_scoped_to_conversation(client, db_session):
    from app import crud

    conv_a = crud.create_conversation(db_session, title="a", model_id="m", provider="ollama")
    conv_b = crud.create_conversation(db_session, title="b", model_id="m", provider="ollama")
    msg_a = crud.add_message(db_session, conv_a.id, "assistant", "x")
    msg_b = crud.add_message(db_session, conv_b.id, "assistant", "y")
    _seed_gallery_image(
        db_session, conv=conv_a, msg=msg_a, filename="a.png", prompt="a", prompt_model="qwen"
    )
    _seed_gallery_image(
        db_session, conv=conv_b, msg=msg_b, filename="b.png", prompt="b", prompt_model="llama3.2"
    )
    scoped = client.get(
        "/api/illustrated-images/facets", params={"conversation_id": conv_a.id}
    ).json()
    assert scoped["prompt_models"] == ["qwen"]
    all_facets = client.get("/api/illustrated-images/facets").json()
    assert set(all_facets["prompt_models"]) >= {"qwen", "llama3.2"}


def test_illustrate_persists_prompt_llm_on_image_event(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="chat-model", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "Había un faro.")

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(
                type="image",
                scene_id="s1",
                data={
                    "filename": "gen.png",
                    "mode": "txt2img",
                    "params": {"prompt": "lighthouse", "steps": 8, "model": "flux.safetensors"},
                },
                content="ok",
            )
            yield IllustrationEvent(type="done", message="ok", content="ok")

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={"prompt_model": "planner-llm", "prompt_provider": "mancer", "images_per_response": 1},
        )
    assert res.status_code == 200
    meta = client.get("/api/illustrated-images/gen.png/meta")
    assert meta.status_code == 200
    assert meta.json()["prompt_model"] == "planner-llm"
    assert meta.json()["prompt_provider"] == "mancer"
    assert meta.json()["params"]["prompt_llm_model"] == "planner-llm"
    assert meta.json()["params"]["prompt_llm_provider"] == "mancer"
    assert meta.json()["params"]["use_chat_config"] is False
    assert meta.json()["params"]["model"] == "flux.safetensors"


def test_illustrate_use_chat_config_stores_conversation_llm(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="chat-model", provider="ollama")
    msg = crud.add_message(db_session, conv.id, "assistant", "texto")

    class FakeOrch:
        def run(self, *a, **k):
            yield IllustrationEvent(
                type="image",
                scene_id="s1",
                data={"filename": "chat.png", "mode": "txt2img", "params": {"prompt": "x"}},
                content="ok",
            )
            yield IllustrationEvent(type="done", message="ok", content="ok")

    with patch("app.routers.api_images._build_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrate",
            json={"prompt_model": "ignored", "use_chat_config": True, "images_per_response": 1},
        )
    assert res.status_code == 200
    meta = client.get("/api/illustrated-images/chat.png/meta").json()
    assert meta["prompt_model"] == "chat-model"
    assert meta["prompt_provider"] == "ollama"
    assert meta["params"]["prompt_llm_model"] == "chat-model"
    assert meta["params"]["use_chat_config"] is True


def test_generate_remaining_inherits_prompt_llm(client, db_session):
    from app import crud

    conv = crud.create_conversation(db_session, title="t", model_id="m", provider="ollama")
    msg = crud.add_message(
        db_session,
        conv.id,
        "assistant",
        '<span class="chat-illustration-placeholder" data-scene="s1" data-prompt="x">x</span>',
    )
    crud.save_illustrated_image_meta(
        db_session,
        message_id=msg.id,
        filename="prev.png",
        scene_id="s0",
        mode="txt2img",
        params={"prompt": "old"},
        prompt_model="qwen",
        prompt_provider="ollama",
    )

    class FakeOrch:
        def run_remaining(self, *a, **k):
            yield IllustrationEvent(
                type="image",
                scene_id="s1",
                data={"filename": "rest.png", "mode": "txt2img", "params": {"prompt": "x"}},
                content="ok",
            )
            yield IllustrationEvent(type="done", message="ok", content="ok")

    with patch("app.routers.api_images._build_forge_orchestrator", return_value=FakeOrch()):
        res = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/illustrations/generate-remaining",
            json={"retries": 0},
        )
    assert res.status_code == 200
    meta = client.get("/api/illustrated-images/rest.png/meta").json()
    assert meta["prompt_model"] == "qwen"
    assert meta["prompt_provider"] == "ollama"
