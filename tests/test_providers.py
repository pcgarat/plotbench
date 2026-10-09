"""
Tests para el sistema de proveedores de LLM.

Tests unitarios para:
- OllamaProvider
- MancerProvider
- OpenAIProvider
- AbliterationProvider
- NanProvider
- ProviderFactory
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.base import LLMProvider, ProviderModelInfo, StreamChunk
from app.providers.ollama import OllamaProvider, get_ollama_provider
from app.providers.factory import ProviderFactory, get_provider


class TestProviderModelInfo:
    """Tests para ProviderModelInfo dataclass."""

    def test_basic_creation(self):
        """Test creación básica de ProviderModelInfo."""
        info = ProviderModelInfo(name="llama3.2", provider="ollama")
        assert info.name == "llama3.2"
        assert info.provider == "ollama"
        assert info.display_name == "llama3.2 (ollama)"
        assert info.context_length is None
        assert info.pricing is None

    def test_with_all_fields(self):
        """Test creación con todos los campos."""
        info = ProviderModelInfo(
            name="mytholite",
            provider="mancer",
            display_name="Mytholite Custom",
            context_length=8192,
            pricing={"prompt_per_1k": 0.001, "completion_per_1k": 0.002},
        )
        assert info.name == "mytholite"
        assert info.display_name == "Mytholite Custom"
        assert info.context_length == 8192
        assert info.pricing["prompt_per_1k"] == 0.001


class TestStreamChunk:
    """Tests para StreamChunk dataclass."""

    def test_content_chunk(self):
        """Test creación de chunk de contenido."""
        chunk = StreamChunk.content_chunk("Hello")
        assert chunk.type == "content"
        assert chunk.content == "Hello"
        assert chunk.error is None

    def test_done_chunk(self):
        """Test creación de chunk de fin."""
        chunk = StreamChunk.done_chunk(model="llama3.2", tokens=100)
        assert chunk.type == "done"
        assert chunk.metadata["model"] == "llama3.2"
        assert chunk.metadata["tokens"] == 100

    def test_error_chunk(self):
        """Test creación de chunk de error."""
        chunk = StreamChunk.error_chunk("Connection failed", status_code=500)
        assert chunk.type == "error"
        assert chunk.error == "Connection failed"
        assert chunk.metadata["status_code"] == 500


class TestOllamaProvider:
    """Tests para OllamaProvider."""

    def test_provider_name(self):
        """Test que el nombre del proveedor es correcto."""
        provider = OllamaProvider(host="http://localhost:11434")
        assert provider.provider_name == "ollama"

    def test_host_default(self):
        """Test que usa el host de settings por defecto."""
        with patch("app.providers.ollama.settings") as mock_settings:
            mock_settings.ollama_host = "http://test:11434"
            mock_settings.verbose = False
            provider = OllamaProvider()
            assert provider.host == "http://test:11434"

    def test_host_override(self):
        """Test que se puede override el host."""
        provider = OllamaProvider(host="http://custom:11434")
        assert provider.host == "http://custom:11434"

    def test_list_models_success(self):
        """Test listado de modelos exitoso."""
        provider = OllamaProvider(host="http://localhost:11434")

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.list.return_value = {
                "models": [
                    {"model": "llama3.2:latest"},
                    {"model": "codellama:13b"},
                ]
            }
            models = provider.list_models()

        assert len(models) == 2
        assert models[0].name == "llama3.2:latest"
        assert models[0].provider == "ollama"
        assert models[1].name == "codellama:13b"

    def test_list_models_connection_error(self):
        """Test error de conexión al listar modelos."""
        provider = OllamaProvider(host="http://localhost:11434")

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.list.side_effect = Exception("Connection refused")

            with pytest.raises(ConnectionError) as exc_info:
                provider.list_models()
            assert "No se pudo conectar a Ollama" in str(exc_info.value)

    def test_chat_success(self):
        """Test chat exitoso."""
        provider = OllamaProvider(host="http://localhost:11434")

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.return_value = {
                "message": {"content": "Hello! How can I help you?"}
            }
            with patch("app.providers.ollama.settings") as mock_settings:
                mock_settings.verbose = False
                result = provider.chat(
                    "llama3.2",
                    [{"role": "user", "content": "Hi"}]
                )

        assert result == "Hello! How can I help you?"

    def test_chat_with_extra_body(self):
        """Chat con extra_body usa httpx y fusiona options en el payload."""
        provider = OllamaProvider(host="http://localhost:11434")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "Con temperatura 0.5"}}

        with patch("app.providers.ollama.httpx") as mock_httpx:
            mock_httpx.Timeout.return_value = None
            mock_client_ctx = MagicMock()
            mock_client_ctx.post.return_value = mock_resp
            mock_httpx.Client.return_value.__enter__.return_value = mock_client_ctx
            mock_httpx.Client.return_value.__exit__.return_value = None
            with patch("app.providers.ollama.settings") as mock_settings:
                mock_settings.verbose = False
                result = provider.chat(
                    "llama3.2",
                    [{"role": "user", "content": "Hi"}],
                    extra_body={"options": {"temperature": 0.5}},
                )
        assert result == "Con temperatura 0.5"
        call_payload = mock_client_ctx.post.call_args[1]["json"]
        assert call_payload.get("options", {}).get("temperature") == 0.5
        assert call_payload.get("stream") is False

    def test_chat_connection_error(self):
        """Chat lanza ConnectionError cuando Ollama falla."""
        provider = OllamaProvider(host="http://localhost:11434")
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.side_effect = Exception("Connection refused")
            with patch("app.providers.ollama.settings") as mock_settings:
                mock_settings.verbose = False
                with pytest.raises(ConnectionError) as exc_info:
                    provider.chat("llama3.2", [{"role": "user", "content": "Hi"}])
                assert "Ollama" in str(exc_info.value)

    def test_chat_stream_chunks_and_done(self):
        """chat_stream emite chunks de contenido y un chunk done al finalizar."""
        provider = OllamaProvider(host="http://localhost:11434")
        lines = [
            json.dumps({"message": {"content": "Hello"}}),
            json.dumps({"message": {"content": " "}}),
            json.dumps({"message": {"content": "world"}}),
            json.dumps({"done": True, "model": "llama3.2", "eval_count": 10}),
        ]

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: fake_aiter_lines()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.ollama.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                with patch("app.providers.ollama.settings") as mock_settings:
                    mock_settings.verbose = False
                    chunks = []
                    async for ch in provider.chat_stream("llama3.2", [{"role": "user", "content": "Hi"}]):
                        chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        content_chunks = [c for c in chunks if c.type == "content"]
        done_chunks = [c for c in chunks if c.type == "done"]
        assert len(content_chunks) == 3
        assert "".join(c.content for c in content_chunks) == "Hello world"
        assert len(done_chunks) == 1
        assert done_chunks[0].metadata.get("model") == "llama3.2"

    def test_chat_stream_error_chunk(self):
        """chat_stream emite chunk de error cuando Ollama devuelve error en la línea."""
        provider = OllamaProvider(host="http://localhost:11434")
        lines = [json.dumps({"error": "Model not found"})]

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: fake_aiter_lines()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.ollama.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                with patch("app.providers.ollama.settings") as mock_settings:
                    mock_settings.verbose = False
                    chunks = []
                    async for ch in provider.chat_stream("llama3.2", [{"role": "user", "content": "Hi"}]):
                        chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        error_chunks = [c for c in chunks if c.type == "error"]
        assert len(error_chunks) == 1
        assert error_chunks[0].error == "Model not found"

    def test_chat_stream_http_error(self):
        """chat_stream emite error cuando HTTP status != 200."""
        class EmptyAsyncIter:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        provider = OllamaProvider(host="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.reason_phrase = "Service Unavailable"
        mock_response.aread = AsyncMock(return_value=b"")
        mock_response.aiter_lines = lambda: EmptyAsyncIter()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.ollama.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                with patch("app.providers.ollama.settings") as mock_settings:
                    mock_settings.verbose = False
                    chunks = []
                    async for ch in provider.chat_stream("llama3.2", [{"role": "user", "content": "Hi"}]):
                        chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        error_chunks = [c for c in chunks if c.type == "error"]
        assert len(error_chunks) == 1
        assert "503" in (error_chunks[0].error or "")

    def test_chat_stream_http_403_includes_ollama_error_body(self):
        """chat_stream con 403 debe mostrar el mensaje de Ollama (p. ej. modelos cloud sin suscripción)."""
        subscription_msg = (
            "this model requires a subscription, upgrade for access: https://ollama.com/upgrade"
        )
        provider = OllamaProvider(host="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.reason_phrase = "Forbidden"
        mock_response.aread = AsyncMock(
            return_value=json.dumps({"error": subscription_msg}).encode("utf-8")
        )

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.ollama.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                with patch("app.providers.ollama.settings") as mock_settings:
                    mock_settings.verbose = False
                    chunks = []
                    async for ch in provider.chat_stream(
                        "glm-5:cloud", [{"role": "user", "content": "Hi"}]
                    ):
                        chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        error_chunks = [c for c in chunks if c.type == "error"]
        assert len(error_chunks) == 1
        assert subscription_msg in (error_chunks[0].error or "")
        assert error_chunks[0].metadata.get("status_code") == 403

    def test_validate_connection_success(self):
        """Test validación de conexión exitosa."""
        provider = OllamaProvider(host="http://localhost:11434")

        with patch.object(provider, "list_models") as mock_list:
            mock_list.return_value = [ProviderModelInfo(name="test", provider="ollama")]
            assert provider.validate_connection() is True

    def test_validate_connection_failure(self):
        """Test validación de conexión fallida."""
        provider = OllamaProvider(host="http://localhost:11434")

        with patch.object(provider, "list_models") as mock_list:
            mock_list.side_effect = ConnectionError("Failed")
            assert provider.validate_connection() is False

    def test_implements_protocol(self):
        """Test que OllamaProvider implementa LLMProvider protocol."""
        provider = OllamaProvider(host="http://localhost:11434")
        assert isinstance(provider, LLMProvider)

    def test_show_model_success(self):
        """show_model devuelve dict normalizado con fetched_at cuando Ollama responde 200."""
        provider = OllamaProvider(host="http://localhost:11434")
        with patch("app.providers.ollama.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "details": {"family": "llama", "parameter_size": "3B"},
                "template": "{{ .System }}",
                "modified_at": "2025-01-01T00:00:00Z",
            }
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_httpx.Client.return_value.__enter__.return_value = mock_client
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.show_model("llama3.2")
        assert result is not None
        assert result.get("details", {}).get("family") == "llama"
        assert result.get("template") == "{{ .System }}"
        assert "fetched_at" in result

    def test_show_model_returns_none_on_http_error(self):
        """show_model devuelve None si la API responde distinto de 200."""
        provider = OllamaProvider(host="http://localhost:11434")
        with patch("app.providers.ollama.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_httpx.Client.return_value.__enter__.return_value = mock_client
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.show_model("nonexistent")
        assert result is None

    def test_show_model_returns_none_on_exception(self):
        """show_model devuelve None si hay excepción (timeout, conexión)."""
        provider = OllamaProvider(host="http://localhost:11434")
        with patch("app.providers.ollama.httpx") as mock_httpx:
            mock_httpx.Client.return_value.__enter__.return_value.post.side_effect = Exception("timeout")
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.show_model("llama3.2")
        assert result is None


class TestOllamaProviderSingleton:
    """Tests para el singleton de OllamaProvider."""

    def test_get_ollama_provider_singleton(self):
        """Test que get_ollama_provider devuelve singleton."""
        # Reset singleton
        import app.providers.ollama as ollama_module
        ollama_module._default_provider = None

        provider1 = get_ollama_provider()
        provider2 = get_ollama_provider()
        assert provider1 is provider2


class TestProviderFactory:
    """Tests para ProviderFactory."""

    def setup_method(self):
        """Limpiar cache antes de cada test."""
        ProviderFactory.clear_cache()

    def test_get_ollama_provider(self):
        """Test obtener proveedor Ollama."""
        provider = ProviderFactory.get_provider("ollama")
        assert provider.provider_name == "ollama"
        assert isinstance(provider, OllamaProvider)

    def test_get_provider_cached(self):
        """Test que el proveedor se cachea."""
        provider1 = ProviderFactory.get_provider("ollama")
        provider2 = ProviderFactory.get_provider("ollama")
        assert provider1 is provider2

    def test_get_provider_case_insensitive(self):
        """Test que el tipo es case-insensitive."""
        provider1 = ProviderFactory.get_provider("OLLAMA")
        provider2 = ProviderFactory.get_provider("Ollama")
        assert provider1 is provider2

    def test_get_invalid_provider(self):
        """Test error con proveedor inválido."""
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.get_provider("invalid")
        assert "no soportado" in str(exc_info.value)

    def test_get_default_provider(self):
        """Test obtener proveedor por defecto."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider = ProviderFactory.get_default_provider()
            assert provider.provider_name == "ollama"

    def test_parse_model_id_with_provider_prefix(self):
        """Test parseo de model_id con prefijo de proveedor."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider_type, model_name = ProviderFactory.parse_model_id("mancer:mytholite")
            assert provider_type == "mancer"
            assert model_name == "mytholite"

    def test_parse_model_id_without_prefix(self):
        """Test parseo de model_id sin prefijo (usa default)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider_type, model_name = ProviderFactory.parse_model_id("llama3.2:latest")
            assert provider_type == "ollama"
            assert model_name == "llama3.2:latest"

    def test_list_available_providers_ollama_only(self):
        """Test listado de proveedores (solo Ollama si no hay keys de cloud)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.mancer_api_key = ""
            mock_settings.openai_api_key = ""
            mock_settings.ablit_key = ""
            mock_settings.nan_api_key = ""
            providers = ProviderFactory.list_available_providers()
            assert providers == ["ollama"]

    def test_list_available_providers_with_mancer(self):
        """Test listado de proveedores (incluyendo Mancer si hay key)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.mancer_api_key = "mcr-test-key"
            mock_settings.openai_api_key = ""
            mock_settings.ablit_key = ""
            mock_settings.nan_api_key = ""
            providers = ProviderFactory.list_available_providers()
            assert "ollama" in providers
            assert "mancer" in providers
            assert "openai" not in providers
            assert "abliteration" not in providers

    def test_list_available_providers_with_openai(self):
        """Test listado de proveedores (incluyendo OpenAI si hay OPENAI_API_KEY)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.mancer_api_key = ""
            mock_settings.openai_api_key = "sk-test-key"
            mock_settings.ablit_key = ""
            mock_settings.nan_api_key = ""
            providers = ProviderFactory.list_available_providers()
            assert "ollama" in providers
            assert "openai" in providers
            assert "mancer" not in providers
            assert "abliteration" not in providers

    def test_list_available_providers_with_abliteration(self):
        """Test listado de proveedores (incluyendo Abliteration si hay ABLIT_KEY)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.mancer_api_key = ""
            mock_settings.openai_api_key = ""
            mock_settings.ablit_key = "ak-test-key"
            mock_settings.nan_api_key = ""
            providers = ProviderFactory.list_available_providers()
            assert "ollama" in providers
            assert "abliteration" in providers
            assert "mancer" not in providers
            assert "openai" not in providers

    def test_list_available_providers_with_nan(self):
        """Test listado de proveedores (incluyendo NaN si hay NAN_API_KEY)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.mancer_api_key = ""
            mock_settings.openai_api_key = ""
            mock_settings.ablit_key = ""
            mock_settings.nan_api_key = "sk-nan-test-key"
            providers = ProviderFactory.list_available_providers()
            assert "ollama" in providers
            assert "nan" in providers
            assert "mancer" not in providers
            assert "openai" not in providers
            assert "abliteration" not in providers

    def test_get_openai_provider(self):
        """Test obtener proveedor OpenAI."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            provider = ProviderFactory.get_provider("openai")
            assert provider.provider_name == "openai"

    def test_get_abliteration_provider(self):
        """Test obtener proveedor Abliteration."""
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            provider = ProviderFactory.get_provider("abliteration")
            assert provider.provider_name == "abliteration"

    def test_get_nan_provider(self):
        """Test obtener proveedor NaN."""
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            provider = ProviderFactory.get_provider("nan")
            assert provider.provider_name == "nan"

    def test_parse_model_id_nan_prefix(self):
        """Test parseo de model_id con prefijo nan."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider_type, model_name = ProviderFactory.parse_model_id(
                "nan:deepseek-v4-flash"
            )
            assert provider_type == "nan"
            assert model_name == "deepseek-v4-flash"

    def test_parse_model_id_openai_prefix(self):
        """Test parseo de model_id con prefijo openai."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider_type, model_name = ProviderFactory.parse_model_id("openai:gpt-4o-mini")
            assert provider_type == "openai"
            assert model_name == "gpt-4o-mini"

    def test_parse_model_id_abliteration_prefix(self):
        """Test parseo de model_id con prefijo abliteration."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider_type, model_name = ProviderFactory.parse_model_id(
                "abliteration:abliterated-model"
            )
            assert provider_type == "abliteration"
            assert model_name == "abliterated-model"


class TestGetProviderFunction:
    """Tests para la función get_provider."""

    def setup_method(self):
        """Limpiar cache antes de cada test."""
        ProviderFactory.clear_cache()

    def test_get_provider_with_type(self):
        """Test get_provider con tipo específico."""
        provider = get_provider("ollama")
        assert provider.provider_name == "ollama"

    def test_get_provider_default(self):
        """Test get_provider sin tipo (usa default)."""
        with patch("app.providers.factory.settings") as mock_settings:
            mock_settings.default_llm_provider = "ollama"
            provider = get_provider()
            assert provider.provider_name == "ollama"


class TestMancerProvider:
    """Tests para MancerProvider."""

    def test_provider_name(self):
        """Test que el nombre del proveedor es correcto."""
        with patch("app.providers.mancer.settings") as mock_settings:
            mock_settings.mancer_api_key = "test-key"
            mock_settings.mancer_base_url = "https://neuro.mancer.tech"
            mock_settings.verbose = False

            from app.providers.mancer import MancerProvider
            provider = MancerProvider()
            assert provider.provider_name == "mancer"

    def test_missing_api_key(self):
        """Test error si no hay API key."""
        with patch("app.providers.mancer.settings") as mock_settings:
            mock_settings.mancer_api_key = ""
            mock_settings.mancer_base_url = "https://neuro.mancer.tech"

            from app.providers.mancer import MancerProvider
            with pytest.raises(ValueError) as exc_info:
                MancerProvider()
            assert "MANCER_API_KEY" in str(exc_info.value)

    def test_api_key_override(self):
        """Test que se puede override la API key."""
        with patch("app.providers.mancer.settings") as mock_settings:
            mock_settings.mancer_api_key = "default-key"
            mock_settings.mancer_base_url = "https://neuro.mancer.tech"
            mock_settings.verbose = False

            from app.providers.mancer import MancerProvider
            provider = MancerProvider(api_key="custom-key")
            assert provider._api_key == "custom-key"

    def test_implements_protocol(self):
        """Test que MancerProvider implementa LLMProvider protocol."""
        with patch("app.providers.mancer.settings") as mock_settings:
            mock_settings.mancer_api_key = "test-key"
            mock_settings.mancer_base_url = "https://neuro.mancer.tech"
            mock_settings.verbose = False

            from app.providers.mancer import MancerProvider
            provider = MancerProvider()
            assert isinstance(provider, LLMProvider)


class TestOpenAIProvider:
    """Tests para OpenAIProvider."""

    def test_provider_name(self):
        """Test que el nombre del proveedor es correcto."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
            assert provider.provider_name == "openai"

    def test_missing_api_key(self):
        """Test error si no hay OPENAI_API_KEY."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            mock_settings.openai_base_url = "https://api.openai.com"
            from app.providers.openai import OpenAIProvider
            with pytest.raises(ValueError) as exc_info:
                OpenAIProvider()
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_list_models_success(self):
        """Test listado de modelos exitoso (GET /v1/models)."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        with patch("app.providers.openai.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [
                    {"id": "gpt-4o-mini", "object": "model", "created": 123, "owned_by": "openai"},
                    {"id": "gpt-4o", "object": "model", "created": 456, "owned_by": "openai"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            models = provider.list_models()
        assert len(models) == 2
        assert models[0].name == "gpt-4o-mini"
        assert models[0].provider == "openai"
        assert models[0].context_length is None
        assert models[1].name == "gpt-4o"

    def test_chat_success(self):
        """Test chat exitoso (POST /v1/chat/completions)."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        with patch("app.providers.openai.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Hello from OpenAI!"}}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.chat("gpt-4o-mini", [{"role": "user", "content": "Hi"}])
        assert result == "Hello from OpenAI!"

    def test_chat_http_error(self):
        """Chat lanza ConnectionError cuando la API devuelve error."""
        import httpx as real_httpx
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        with patch("app.providers.openai.httpx") as mock_httpx:
            mock_httpx.HTTPStatusError = real_httpx.HTTPStatusError  # para que except httpx.HTTPStatusError funcione
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}
            mock_resp.raise_for_status.side_effect = real_httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_resp
            )
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            with pytest.raises(ConnectionError) as exc_info:
                provider.chat("gpt-4o-mini", [{"role": "user", "content": "Hi"}])
            assert "401" in str(exc_info.value)
            assert "Invalid API key" in str(exc_info.value)

    def test_chat_stream_content_and_done(self):
        """chat_stream emite chunks de contenido y done con usage si viene en el chunk."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " there"}}]}),
            "data: " + json.dumps({
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }),
        ]

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: fake_aiter_lines()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.openai.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                chunks = []
                async for ch in provider.chat_stream("gpt-4o-mini", [{"role": "user", "content": "Hi"}]):
                    chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        content_chunks = [c for c in chunks if c.type == "content"]
        done_chunks = [c for c in chunks if c.type == "done"]
        assert len(content_chunks) == 2
        assert "".join(c.content for c in content_chunks) == "Hi there"
        assert len(done_chunks) == 1
        assert done_chunks[0].metadata.get("usage") == {"prompt_tokens": 5, "completion_tokens": 2}

    def test_validate_connection_success(self):
        """validate_connection True cuando list_models responde OK."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        with patch.object(provider, "list_models") as mock_list:
            mock_list.return_value = [ProviderModelInfo(name="gpt-4o-mini", provider="openai")]
            assert provider.validate_connection() is True

    def test_validate_connection_failure(self):
        """validate_connection False cuando list_models falla."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
        with patch.object(provider, "list_models") as mock_list:
            mock_list.side_effect = ConnectionError("API error")
            assert provider.validate_connection() is False

    def test_implements_protocol(self):
        """Test que OpenAIProvider implementa LLMProvider protocol."""
        with patch("app.providers.openai.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_base_url = "https://api.openai.com"
            mock_settings.verbose = False
            from app.providers.openai import OpenAIProvider
            provider = OpenAIProvider()
            assert isinstance(provider, LLMProvider)


class TestAbliterationProvider:
    """Tests para AbliterationProvider."""

    def test_provider_name(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
            assert provider.provider_name == "abliteration"

    def test_missing_api_key(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = ""
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            from app.providers.abliteration import AbliterationProvider
            with pytest.raises(ValueError) as exc_info:
                AbliterationProvider()
            assert "ABLIT_KEY" in str(exc_info.value)

    def test_api_key_override(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "default-key"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider(api_key="custom-key")
            assert provider._api_key == "custom-key"

    def test_list_models_enriches_known_catalog(self):
        """list_models enriquece IDs de la API con context_length del catálogo."""
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        with patch("app.providers.abliteration.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [
                    {"id": "abliterated-model", "object": "model"},
                    {"id": "abliterated-model-large", "object": "model"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            models = provider.list_models()
        assert len(models) == 3
        by_name = {m.name: m for m in models}
        assert by_name["abliterated-model"].context_length == 262_144
        assert by_name["abliterated-model-large"].context_length == 1_000_000
        assert by_name["abliterated-model-large-v2"].context_length == 1_000_000
        assert by_name["abliterated-model"].pricing["prompt_per_1k"] == 0.003
        assert by_name["abliterated-model-large"].pricing["prompt_per_1k"] == 0.005
        assert by_name["abliterated-model-large-v2"].pricing["prompt_per_1k"] == 0.005

    def test_list_models_fallback_completes_catalog(self):
        """Si la API solo devuelve un modelo, se completa con el catálogo conocido."""
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        with patch("app.providers.abliteration.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [{"id": "abliterated-model", "object": "model"}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            models = provider.list_models()
        names = {m.name for m in models}
        assert names == {
            "abliterated-model",
            "abliterated-model-large",
            "abliterated-model-large-v2",
        }

    def test_chat_success(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        with patch("app.providers.abliteration.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Hello from Abliteration!"}}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.chat(
                "abliterated-model", [{"role": "user", "content": "Hi"}]
            )
        assert result == "Hello from Abliteration!"

    def test_chat_stream_content_and_done(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}),
            "data: " + json.dumps({
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            }),
        ]

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: fake_aiter_lines()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.abliteration.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(
                    return_value=mock_async_client
                )
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                chunks = []
                async for ch in provider.chat_stream(
                    "abliterated-model", [{"role": "user", "content": "Hi"}]
                ):
                    chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        content_chunks = [c for c in chunks if c.type == "content"]
        done_chunks = [c for c in chunks if c.type == "done"]
        assert "".join(c.content for c in content_chunks) == "Hi"
        assert done_chunks[0].metadata.get("usage") == {
            "prompt_tokens": 3,
            "completion_tokens": 1,
        }

    def test_show_model_uses_known_catalog(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        with patch("app.providers.abliteration.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.show_model("abliterated-model")
        assert result is not None
        assert result["context_length"] == 262_144
        assert "fetched_at" in result

    def test_validate_connection_success(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
        with patch.object(provider, "list_models") as mock_list:
            mock_list.return_value = [
                ProviderModelInfo(name="abliterated-model", provider="abliteration")
            ]
            assert provider.validate_connection() is True

    def test_implements_protocol(self):
        with patch("app.providers.abliteration.settings") as mock_settings:
            mock_settings.ablit_key = "ak-test"
            mock_settings.ablit_base_url = "https://api.abliteration.ai"
            mock_settings.verbose = False
            from app.providers.abliteration import AbliterationProvider
            provider = AbliterationProvider()
            assert isinstance(provider, LLMProvider)


class TestNanProvider:
    """Tests para NanProvider (NaN Builders, API compatible OpenAI)."""

    def test_provider_name(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
            assert provider.provider_name == "nan"

    def test_default_base_url(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = ""
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
            assert provider.base_url == "https://api.nan.builders"

    def test_missing_api_key(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = ""
            mock_settings.nan_base_url = "https://api.nan.builders"
            from app.providers.nan import NanProvider
            with pytest.raises(ValueError) as exc_info:
                NanProvider()
            assert "NAN_API_KEY" in str(exc_info.value)

    def test_api_key_override(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "default-key"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider(api_key="custom-key")
            assert provider._api_key == "custom-key"

    def test_implements_protocol(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
            assert isinstance(provider, LLMProvider)

    def test_list_models_enriches_known_catalog(self):
        """list_models enriquece IDs de la API con context_length y display_name del catálogo."""
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch("app.providers.nan.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [
                    {"id": "deepseek-v4-flash", "object": "model"},
                    {"id": "gemma4", "object": "model"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            models = provider.list_models()
        assert len(models) == 2
        by_name = {m.name: m for m in models}
        assert by_name["deepseek-v4-flash"].context_length == 1_048_576
        assert by_name["gemma4"].context_length == 262_144
        assert by_name["deepseek-v4-flash"].display_name is not None
        assert by_name["deepseek-v4-flash"].provider == "nan"

    def test_list_models_does_not_invent_models(self):
        """A diferencia de abliteration, NaN solo lista lo que la API devuelve (no añade catálogo)."""
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch("app.providers.nan.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": [{"id": "deepseek-v4-flash", "object": "model"}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            models = provider.list_models()
        assert [m.name for m in models] == ["deepseek-v4-flash"]

    def test_chat_success(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch("app.providers.nan.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Hola desde NaN!"}}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.chat(
                "deepseek-v4-flash", [{"role": "user", "content": "Hi"}]
            )
        assert result == "Hola desde NaN!"

    def test_chat_http_error(self):
        import httpx as real_httpx
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch("app.providers.nan.httpx") as mock_httpx:
            mock_httpx.HTTPStatusError = real_httpx.HTTPStatusError
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.json.return_value = {
                "error": {"message": "This API key does not have access to the requested model"}
            }
            mock_resp.raise_for_status.side_effect = real_httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_resp
            )
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            with pytest.raises(ConnectionError) as exc_info:
                provider.chat("glm5.3", [{"role": "user", "content": "Hi"}])
            assert "401" in str(exc_info.value)
            assert "does not have access" in str(exc_info.value)

    def test_chat_stream_content_and_done(self):
        """chat_stream ignora reasoning_content y expone content + usage."""
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "pensando..."}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " there"}}]}),
            "data: " + json.dumps({
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            }),
        ]

        async def fake_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: fake_aiter_lines()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        async def run():
            with patch("app.providers.nan.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.stream.return_value = mock_stream_ctx
                mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(
                    return_value=mock_async_client
                )
                mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=None)
                chunks = []
                async for ch in provider.chat_stream(
                    "deepseek-v4-flash", [{"role": "user", "content": "Hi"}]
                ):
                    chunks.append(ch)
            return chunks

        chunks = asyncio.run(run())
        content_chunks = [c for c in chunks if c.type == "content"]
        done_chunks = [c for c in chunks if c.type == "done"]
        assert "".join(c.content for c in content_chunks) == "Hi there"
        assert done_chunks[0].metadata.get("usage") == {
            "prompt_tokens": 7,
            "completion_tokens": 2,
        }

    def test_show_model_uses_known_catalog(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch("app.providers.nan.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_httpx.Client.return_value.__enter__.return_value.get.return_value = mock_resp
            mock_httpx.Client.return_value.__exit__.return_value = None
            result = provider.show_model("deepseek-v4-flash")
        assert result is not None
        assert result["context_length"] == 1_048_576
        assert "fetched_at" in result

    def test_validate_connection_success(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch.object(provider, "list_models") as mock_list:
            mock_list.return_value = [
                ProviderModelInfo(name="deepseek-v4-flash", provider="nan")
            ]
            assert provider.validate_connection() is True

    def test_validate_connection_failure(self):
        with patch("app.providers.nan.settings") as mock_settings:
            mock_settings.nan_api_key = "sk-nan-test"
            mock_settings.nan_base_url = "https://api.nan.builders"
            mock_settings.verbose = False
            from app.providers.nan import NanProvider
            provider = NanProvider()
        with patch.object(provider, "list_models") as mock_list:
            mock_list.side_effect = ConnectionError("API error")
            assert provider.validate_connection() is False
