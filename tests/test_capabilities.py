"""Tests para el módulo de capacidades por proveedor (app/providers/capabilities.py)."""
import pytest
from unittest.mock import patch, MagicMock

from app.providers.capabilities import (
    get_provider_capabilities,
    get_model_details,
    SHOW_MODEL,
    UNLOAD_MODEL,
)


@patch("app.providers.capabilities.get_provider")
def test_get_provider_capabilities_ollama_has_show_and_unload(mock_get_provider):
    """Ollama tiene show_model y unload_model_from_memory."""
    mock_provider = MagicMock()
    mock_provider.show_model = lambda x: None
    mock_provider.unload_model_from_memory = lambda x: None
    mock_get_provider.return_value = mock_provider

    caps = get_provider_capabilities("ollama")
    assert SHOW_MODEL in caps
    assert UNLOAD_MODEL in caps
    assert len(caps) == 2


@patch("app.providers.mancer.settings")
def test_get_provider_capabilities_mancer_has_show_model(mock_settings):
    """Mancer tiene show_model (GET /oai/v1/models/{id})."""
    mock_settings.mancer_api_key = "test-key"
    mock_settings.mancer_base_url = "https://neuro.mancer.tech"
    mock_settings.verbose = False
    caps = get_provider_capabilities("mancer")
    assert SHOW_MODEL in caps


@patch("app.providers.capabilities.get_provider")
def test_get_provider_capabilities_provider_without_show(mock_get_provider):
    """Proveedor sin show_model no incluye esa capacidad (ej. openai)."""
    mock_provider = MagicMock(spec=["provider_name", "list_models", "chat", "chat_stream", "validate_connection"])
    mock_get_provider.return_value = mock_provider

    caps = get_provider_capabilities("openai")
    assert SHOW_MODEL not in caps


@patch("app.providers.nan.httpx.Client")
@patch("app.providers.nan.settings")
def test_get_provider_capabilities_nan_has_show_model(mock_settings, mock_httpx_client):
    """NaN tiene show_model (GET /v1/models/{id}) en el catálogo de capacidades."""
    mock_settings.nan_api_key = "sk-nan-test"
    mock_settings.nan_base_url = "https://api.nan.builders"
    mock_settings.verbose = False
    caps = get_provider_capabilities("nan")
    assert SHOW_MODEL in caps


@patch("app.providers.capabilities.get_provider")
def test_get_provider_capabilities_invalid_provider(mock_get_provider):
    """Proveedor inexistente devuelve lista vacía."""
    mock_get_provider.side_effect = ValueError("Proveedor 'invalid' no soportado")
    caps = get_provider_capabilities("invalid")
    assert caps == []


@patch("app.providers.capabilities.get_provider")
def test_get_model_details_returns_dict_when_supported(mock_get_provider):
    """get_model_details devuelve el dict de show_model cuando el proveedor lo soporta."""
    mock_provider = MagicMock()
    mock_provider.show_model.return_value = {"details": {"family": "llama"}, "fetched_at": "2025-01-01T00:00:00Z"}
    mock_get_provider.return_value = mock_provider

    result = get_model_details("ollama", "llama3.2")
    assert result == {"details": {"family": "llama"}, "fetched_at": "2025-01-01T00:00:00Z"}
    mock_provider.show_model.assert_called_once_with("llama3.2")


@patch("app.providers.capabilities.get_provider")
def test_get_model_details_returns_none_when_provider_has_no_show(mock_get_provider):
    """get_model_details devuelve None si el proveedor no implementa show_model."""
    mock_provider = MagicMock(spec=["provider_name", "list_models"])
    mock_get_provider.return_value = mock_provider

    result = get_model_details("openai", "gpt-4")
    assert result is None


@patch("app.providers.capabilities.get_provider")
def test_get_model_details_returns_none_on_value_error(mock_get_provider):
    """get_model_details devuelve None si el proveedor no existe."""
    mock_get_provider.side_effect = ValueError("Proveedor no soportado")
    result = get_model_details("unknown", "m1")
    assert result is None


@patch("app.providers.mancer.httpx.Client")
@patch("app.providers.mancer.settings")
def test_mancer_show_model_returns_normalized_info(mock_settings, mock_httpx_client):
    """MancerProvider.show_model normaliza la respuesta de GET /oai/v1/models/{id}."""
    mock_settings.mancer_api_key = "test-key"
    mock_settings.mancer_base_url = "https://neuro.mancer.tech"
    mock_settings.verbose = False

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "mytholite",
        "context_length": 8192,
        "pricing": {"prompt": 0.001, "completion": 0.002},
    }
    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    from app.providers.mancer import MancerProvider
    provider = MancerProvider()
    result = provider.show_model("mytholite")

    assert result is not None
    assert result["id"] == "mytholite"
    assert result["context_length"] == 8192
    assert result["pricing"] == {"prompt": 0.001, "completion": 0.002}
    assert "fetched_at" in result
    assert "model_info" in result
    assert result["model_info"]["context_length"] == 8192
    mock_client_instance.get.assert_called_once()
    call_args = mock_client_instance.get.call_args
    assert "mytholite" in str(call_args[0][0])
