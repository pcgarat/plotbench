"""Tests del endpoint GET /api/models, /api/providers y ficha de modelo (info, tags, capabilities)."""
import pytest
from unittest.mock import patch, MagicMock

from app.providers.base import ProviderModelInfo


@patch("app.routers.api_models.get_provider")
def test_list_models_ok(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.list_models.return_value = [
        ProviderModelInfo(name="llama3.2", provider="ollama"),
        ProviderModelInfo(name="mistral:latest", provider="ollama"),
    ]
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["name"] == "llama3.2"
    assert data[1]["name"] == "mistral:latest"
    mock_provider.list_models.assert_called_once()


@patch("app.routers.api_models.get_provider")
def test_list_models_empty(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.list_models.return_value = []
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/models")
    assert r.status_code == 200
    assert r.json() == []


@patch("app.routers.api_models.get_provider")
def test_list_models_provider_error(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.list_models.side_effect = ConnectionError("Provider no disponible")
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/models")
    assert r.status_code == 503
    assert "proveedor" in r.json()["detail"].lower()


@patch("app.routers.api_models.get_provider")
def test_list_models_with_provider_query(mock_get_provider, client):
    """GET /api/models?provider=X lista solo modelos de ese proveedor."""
    mock_provider = MagicMock()
    mock_provider.list_models.return_value = [
        ProviderModelInfo(name="m1", provider="mancer"),
    ]
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/models?provider=mancer")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "m1"
    mock_get_provider.assert_called_once_with("mancer")


@patch("app.routers.api_models.get_provider")
def test_list_models_value_error(mock_get_provider, client):
    """GET /api/models con proveedor inválido devuelve 400."""
    mock_get_provider.side_effect = ValueError("Proveedor 'x' no soportado")
    r = client.get("/api/models?provider=x")
    assert r.status_code == 400
    assert "no soportado" in r.json()["detail"].lower()


# ----- validate_provider -----


@patch("app.routers.api_models.get_provider")
def test_validate_provider_200(mock_get_provider, client):
    """GET /api/providers/{name}/validate devuelve 200 cuando el proveedor está disponible."""
    mock_provider = MagicMock()
    mock_provider.validate_connection.return_value = True
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/ollama/validate")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_provider.validate_connection.assert_called_once()


@patch("app.routers.api_models.get_provider")
def test_validate_provider_503(mock_get_provider, client):
    """GET /api/providers/{name}/validate devuelve 503 cuando no está disponible."""
    mock_provider = MagicMock()
    mock_provider.validate_connection.return_value = False
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/ollama/validate")
    assert r.status_code == 503
    assert "no disponible" in r.json()["detail"].lower()


@patch("app.routers.api_models.get_provider")
def test_validate_provider_503_on_exception(mock_get_provider, client):
    """validate_connection lanza excepción -> 503."""
    mock_provider = MagicMock()
    mock_provider.validate_connection.side_effect = ConnectionError("Connection refused")
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/ollama/validate")
    assert r.status_code == 503


# ----- list_provider_models excepciones -----


@patch("app.routers.api_models.get_provider")
def test_list_provider_models_connection_error(mock_get_provider, client):
    """GET /api/providers/X/models con ConnectionError devuelve 503."""
    mock_provider = MagicMock()
    mock_provider.list_models.side_effect = ConnectionError("No connection")
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/mancer/models")
    assert r.status_code == 503
    assert "conectar" in r.json()["detail"].lower()


@patch("app.routers.api_models.get_provider")
def test_list_provider_models_generic_exception(mock_get_provider, client):
    """GET /api/providers/X/models con Exception genérica devuelve 503."""
    mock_provider = MagicMock()
    mock_provider.list_models.side_effect = RuntimeError("Algo falló")
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/mancer/models")
    assert r.status_code == 503
    assert "listar" in r.json()["detail"].lower() or "mancer" in r.json()["detail"].lower()


# ----- list_all_models: un proveedor falla, se continúa con el siguiente -----


@patch("app.routers.api_models.get_provider")
@patch("app.routers.api_models.ProviderFactory.list_available_providers")
def test_list_all_models_one_provider_fails_continue(mock_list_providers, mock_get_provider, client):
    """Si un proveedor falla al listar, se devuelven los modelos del resto."""
    mock_list_providers.return_value = ["ollama", "mancer"]
    ollama_provider = MagicMock()
    ollama_provider.list_models.side_effect = ConnectionError("Ollama down")
    mancer_provider = MagicMock()
    mancer_provider.list_models.return_value = [
        ProviderModelInfo(name="mytho", provider="mancer"),
    ]

    def get_provider_side_effect(name):
        if name == "ollama":
            return ollama_provider
        return mancer_provider

    mock_get_provider.side_effect = get_provider_side_effect
    r = client.get("/api/models/all")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "mytho"
    assert data[0]["provider"] == "mancer"


def test_get_provider_params_ollama(client):
    """GET /api/providers/ollama/params devuelve los parámetros definidos en config."""
    r = client.get("/api/providers/ollama/params")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "ollama"
    assert "params" in data
    params = data["params"]
    assert "temperature" in params
    assert params["temperature"].get("api_key") == "options.temperature"
    assert params["temperature"].get("default") == 0.8
    assert "max_tokens" in params
    assert params["max_tokens"].get("api_key") == "options.num_predict"


def test_get_provider_params_mancer(client):
    """GET /api/providers/mancer/params devuelve los parámetros (API compatible OpenAI)."""
    r = client.get("/api/providers/mancer/params")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "mancer"
    assert "params" in data
    params = data["params"]
    assert "temperature" in params
    assert params["temperature"].get("api_key") == "temperature"
    assert params["temperature"].get("default") == 0.8
    assert "max_tokens" in params
    assert params["max_tokens"].get("api_key") == "max_tokens"
    assert "stop_sequences" in params
    assert params["stop_sequences"].get("api_key") == "stop"
    assert "presence_penalty" in params
    assert "frequency_penalty" in params


def test_get_provider_params_abliteration(client):
    """GET /api/providers/abliteration/params devuelve parámetros OpenAI-compatible."""
    r = client.get("/api/providers/abliteration/params")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "abliteration"
    params = data["params"]
    assert params["temperature"].get("api_key") == "temperature"
    assert params["max_tokens"].get("api_key") == "max_tokens"
    assert params["max_tokens"].get("default") == 4096


def test_get_provider_presets_abliteration(client):
    """GET /api/providers/abliteration/presets incluye los tres modelos oficiales."""
    r = client.get("/api/providers/abliteration/presets")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "abliteration"
    presets = data["presets"]
    assert "abliterated-model" in presets
    assert "abliterated-model-large" in presets
    assert "abliterated-model-large-v2" in presets
    assert presets["abliterated-model"]["context_length"]["max"] == 262144
    assert presets["abliterated-model-large"]["context_length"]["max"] == 1000000
    assert presets["abliterated-model-large-v2"]["context_length"]["max"] == 1000000


def test_get_provider_params_nan(client):
    """GET /api/providers/nan/params devuelve parámetros OpenAI-compatible."""
    r = client.get("/api/providers/nan/params")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "nan"
    params = data["params"]
    assert params["temperature"].get("api_key") == "temperature"
    assert params["max_tokens"].get("api_key") == "max_tokens"
    assert params["max_tokens"].get("default") == 4096


def test_get_provider_presets_nan(client):
    """GET /api/providers/nan/presets incluye los modelos del clúster NaN."""
    r = client.get("/api/providers/nan/presets")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "nan"
    presets = data["presets"]
    assert "deepseek-v4-flash" in presets
    assert "gemma4" in presets
    assert presets["deepseek-v4-flash"]["context_length"]["max"] == 1048576
    assert presets["gemma4"]["context_length"]["max"] == 262144


def test_get_provider_params_unknown(client):
    """GET /api/providers/unknown/params devuelve params vacío."""
    r = client.get("/api/providers/unknown_provider_xyz/params")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "unknown_provider_xyz"
    assert data["params"] == {}


def test_get_provider_presets_ollama(client):
    """GET /api/providers/ollama/presets devuelve presets desde config/ollama.json."""
    r = client.get("/api/providers/ollama/presets")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "ollama"
    assert "presets" in data
    presets = data["presets"]
    assert isinstance(presets, dict)
    # config/ollama.json tiene entradas por nombre de modelo
    if presets:
        name = next(iter(presets))
        entry = presets[name]
        assert isinstance(entry, dict)
        assert "temperature" in entry or "max_tokens" in entry


def test_get_provider_presets_unknown(client):
    """GET /api/providers/unknown/presets devuelve presets vacío si no hay archivo."""
    r = client.get("/api/providers/unknown_provider_xyz/presets")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "unknown_provider_xyz"
    assert data["presets"] == {}


@patch("app.routers.api_models.ProviderFactory.list_available_providers")
def test_list_providers(mock_list_providers, client):
    mock_list_providers.return_value = ["ollama", "mancer"]
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["name"] == "ollama"
    assert data[1]["name"] == "mancer"


@patch("app.routers.api_models.get_provider")
def test_list_provider_models(mock_get_provider, client):
    mock_provider = MagicMock()
    mock_provider.list_models.return_value = [
        ProviderModelInfo(name="mytholite", provider="mancer", context_length=8192),
    ]
    mock_get_provider.return_value = mock_provider
    r = client.get("/api/providers/mancer/models")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "mytholite"
    assert data[0]["provider"] == "mancer"
    assert data[0]["context_length"] == 8192


@patch("app.routers.api_models.get_provider")
def test_list_provider_models_invalid_provider(mock_get_provider, client):
    mock_get_provider.side_effect = ValueError("Proveedor 'invalid' no soportado")
    r = client.get("/api/providers/invalid/models")
    assert r.status_code == 400
    assert "no soportado" in r.json()["detail"]


@patch("app.routers.api_models.get_model_info")
@patch("app.routers.api_models.get_provider")
def test_get_context_length_from_provider_info(mock_get_provider, mock_get_model_info, client):
    """GET .../context-length devuelve context_length desde ficha (provider_info)."""
    mock_get_provider.return_value = MagicMock()
    mock_get_model_info.return_value = {
        "provider_info": {"model_info": {"llama.context_length": 4096}},
        "user_info": {},
    }
    r = client.get("/api/providers/ollama/models/llama3.2/context-length")
    assert r.status_code == 200
    assert r.json() == {"context_length": 4096}


@patch("app.routers.api_models.get_context_length_max")
@patch("app.routers.api_models.get_model_info")
@patch("app.routers.api_models.get_provider")
def test_get_context_length_from_preset(mock_get_provider, mock_get_model_info, mock_get_ctx_max, client):
    """GET .../context-length usa preset cuando la ficha no tiene context_length."""
    mock_get_provider.return_value = MagicMock()
    mock_get_model_info.return_value = {"provider_info": {}, "user_info": {}}
    mock_get_ctx_max.return_value = 8192
    r = client.get("/api/providers/ollama/models/llama3.2/context-length")
    assert r.status_code == 200
    assert r.json() == {"context_length": 8192}


@patch("app.routers.api_models.get_context_length_max")
@patch("app.routers.api_models.get_model_info")
@patch("app.routers.api_models.get_provider")
def test_get_context_length_null_when_unknown(mock_get_provider, mock_get_model_info, mock_get_ctx_max, client):
    """GET .../context-length devuelve context_length null si no hay fuente."""
    mock_get_provider.return_value = MagicMock()
    mock_get_provider.return_value.list_models.return_value = []
    mock_get_model_info.return_value = {"provider_info": {}, "user_info": {}}
    mock_get_ctx_max.return_value = None
    r = client.get("/api/providers/ollama/models/unknown/context-length")
    assert r.status_code == 200
    assert r.json()["context_length"] is None


# ----- Ficha de modelo: capabilities, info, tags, refresh -----


@patch("app.routers.api_models.get_provider_capabilities")
def test_get_capabilities_ollama(mock_get_caps, client):
    """GET /api/providers/ollama/capabilities devuelve lista de capacidades."""
    mock_get_caps.return_value = ["show_model", "unload_model"]
    r = client.get("/api/providers/ollama/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert data["capabilities"] == ["show_model", "unload_model"]
    mock_get_caps.assert_called_once_with("ollama")


@patch("app.routers.api_models.get_provider_capabilities")
def test_get_capabilities_invalid_provider(mock_get_caps, client):
    """GET /api/providers/invalid/capabilities con proveedor inexistente devuelve 400."""
    mock_get_caps.side_effect = ValueError("Proveedor no soportado")
    r = client.get("/api/providers/invalid/capabilities")
    assert r.status_code == 400


@pytest.fixture
def model_info_use_tmp_path(tmp_path):
    """Redirige persistencia de model_info a tmp_path para tests de API."""
    with (
        patch("app.model_info._MODEL_INFO_DIR", tmp_path),
        patch("app.model_info._MODEL_INFO_PATH", tmp_path / "model_info.json"),
        patch("app.model_info._MODEL_INFO_TMP", tmp_path / "model_info.json.tmp"),
    ):
        yield tmp_path


def test_get_model_info_returns_defaults_when_missing(client, model_info_use_tmp_path):
    """GET .../models/{model_id}/info devuelve ficha por defecto si no existe."""
    r = client.get("/api/providers/ollama/models/llama3.2/info")
    assert r.status_code == 200
    data = r.json()
    assert data["provider_info"] == {}
    assert data["user_info"]["uncensored"] is False
    assert data["user_info"]["instructions"] == []
    assert data["user_info"]["tags"] == []


def test_put_model_info_updates_user_info(client, model_info_use_tmp_path):
    """PUT .../models/{model_id}/info actualiza user_info."""
    r = client.put(
        "/api/providers/ollama/models/llama3.2/info",
        json={"uncensored": True, "tags": ["local", "test"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["user_info"]["uncensored"] is True
    assert data["user_info"]["tags"] == ["local", "test"]

    r2 = client.get("/api/providers/ollama/models/llama3.2/info")
    assert r2.status_code == 200
    assert r2.json()["user_info"]["uncensored"] is True
    assert set(r2.json()["user_info"]["tags"]) == {"local", "test"}


def test_get_models_tags_empty_then_after_put(client, model_info_use_tmp_path):
    """GET /api/models/tags devuelve tags únicos; vacío al inicio, con datos tras PUT."""
    r = client.get("/api/models/tags")
    assert r.status_code == 200
    assert r.json()["tags"] == []

    client.put("/api/providers/ollama/models/m1/info", json={"tags": ["a", "b"]})
    client.put("/api/providers/ollama/models/m2/info", json={"tags": ["b", "c"]})
    r2 = client.get("/api/models/tags")
    assert r2.status_code == 200
    assert set(r2.json()["tags"]) == {"a", "b", "c"}


def test_get_model_info_invalid_provider(client, model_info_use_tmp_path):
    """GET .../info con proveedor inexistente devuelve 400."""
    r = client.get("/api/providers/nonexistent_provider_xyz/models/llama3.2/info")
    assert r.status_code == 400


@patch("app.routers.api_models.get_presets")
@patch("app.routers.api_models.get_model_info")
@patch("app.routers.api_models.get_provider")
def test_get_model_info_openai_merges_preset_tags(
    mock_get_provider, mock_get_model_info, mock_get_presets, client, model_info_use_tmp_path
):
    """Para openai, la ficha devuelve tags del usuario + tags del preset (features/modalities)."""
    mock_get_model_info.return_value = {
        "provider_info": {},
        "user_info": {"tags": ["user-tag"], "uncensored": False, "instruction_ids": []},
    }
    mock_get_presets.return_value = {
        "gpt-4o-mini": {"tags": ["Chat Completions", "Image", "Realtime"], "context_length": {"max": 128000}},
    }
    r = client.get("/api/providers/openai/models/gpt-4o-mini/info")
    assert r.status_code == 200
    tags = r.json()["user_info"]["tags"]
    assert "user-tag" in tags
    assert "Chat Completions" in tags
    assert "Image" in tags
    assert "Realtime" in tags
    assert tags == sorted(tags)


@patch("app.routers.api_models.get_model_details")
def test_post_info_refresh_updates_provider_info(mock_get_model_details, client, model_info_use_tmp_path):
    """POST .../info/refresh llama a show_model y persiste provider_info."""
    mock_get_model_details.return_value = {
        "fetched_at": "2025-01-01T12:00:00Z",
        "details": {"family": "llama"},
        "template": "{{ .System }}",
    }
    r = client.post("/api/providers/ollama/models/llama3.2/info/refresh")
    assert r.status_code == 200
    data = r.json()
    assert data["provider_info"].get("details", {}).get("family") == "llama"
    assert "fetched_at" in data["provider_info"]
    mock_get_model_details.assert_called_once_with("ollama", "llama3.2")


@patch("app.routers.api_models.get_model_details")
def test_post_info_refresh_when_show_fails_returns_current(mock_get_model_details, client, model_info_use_tmp_path):
    """POST .../info/refresh cuando show_model devuelve None no sobrescribe; devuelve ficha actual."""
    client.put("/api/providers/ollama/models/llama3.2/info", json={"tags": ["keep"]})
    mock_get_model_details.return_value = None  # show falla
    r = client.post("/api/providers/ollama/models/llama3.2/info/refresh")
    assert r.status_code == 200
    data = r.json()
    assert data["provider_info"] == {}
    assert data["user_info"]["tags"] == ["keep"]


@patch("app.routers.api_models.get_model_details", return_value=None)
def test_get_model_contract_deepseek_shape(mock_details, client):
    r = client.get("/api/providers/ollama/models/deepseek-v4-flash:cloud/contract")
    assert r.status_code == 200
    data = r.json()
    assert set(data) >= {"provider", "model", "capabilities", "params", "recipes", "quirks"}
    assert data["provider"] == "ollama"
    assert data["model"] == "deepseek-v4-flash:cloud"
    assert data["capabilities"]["thinking"]["kind"] == "levels"
    assert data["capabilities"]["thinking"]["can_disable"] is True
    assert "max" in data["capabilities"]["thinking"]["values"]
    assert data["params"]["think"]["api_key"] == "think"
    assert data["params"]["temperature"]["api_key"] == "options.temperature"
    mock_details.assert_called_once_with("ollama", "deepseek-v4-flash:cloud")


@patch("app.routers.api_models.get_model_details", return_value=None)
def test_get_model_contract_gpt_oss_thinking_distinto(mock_details, client):
    r = client.get("/api/providers/ollama/models/gpt-oss:120b-cloud/contract")
    assert r.status_code == 200
    data = r.json()
    assert data["capabilities"]["thinking"]["can_disable"] is False
    assert data["capabilities"]["thinking"]["values"] == ["low", "medium", "high"]
    assert data["capabilities"]["vision"] is False


@patch("app.routers.api_models.get_model_details", return_value=None)
def test_get_model_contract_sin_overlay_200(mock_details, client):
    r = client.get("/api/providers/ollama/models/modelo-sin-overlay-xyz/contract")
    assert r.status_code == 200
    data = r.json()
    assert data["capabilities"]["thinking"]["kind"] == "none"
    assert data["recipes"] == []
    assert "think" not in data["params"]


def test_get_model_contract_proveedor_invalido(client):
    r = client.get("/api/providers/nonexistent_provider_xyz/models/llama3.2/contract")
    assert r.status_code == 400


@patch("app.routers.api_models.get_model_details", side_effect=ConnectionError("down"))
def test_get_model_contract_show_falla_sigue_200(mock_details, client):
    r = client.get("/api/providers/ollama/models/deepseek-v4-flash:cloud/contract")
    assert r.status_code == 200
    assert r.json()["capabilities"]["thinking"]["kind"] == "levels"


def test_get_params_y_presets_siguen_igual(client):
    params = client.get("/api/providers/ollama/params")
    presets = client.get("/api/providers/ollama/presets")
    assert params.status_code == 200
    assert "params" in params.json()
    assert "temperature" in params.json()["params"]
    assert presets.status_code == 200
    assert "presets" in presets.json()
