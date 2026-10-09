"""
Proveedor de LLM para Ollama (modelos locales).

Refactorizado desde ollama_client.py para cumplir con la interfaz LLMProvider.
"""

import json
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx
from ollama import Client

from app.config import settings
from app.providers.base import LLMProvider, ProviderModelInfo, StreamChunk


class OllamaProvider:
    """
    Proveedor para Ollama (modelos locales).

    Implementa la interfaz LLMProvider para interactuar con Ollama.
    Soporta chat síncrono, streaming asíncrono y listado de modelos.
    """

    def __init__(self, host: str | None = None):
        """
        Inicializa el proveedor de Ollama.

        Args:
            host: URL del servidor Ollama. Si es None, usa settings.ollama_host.
        """
        self._host = host or settings.ollama_host
        self._client: Client | None = None

    @property
    def provider_name(self) -> str:
        """Nombre identificador del proveedor."""
        return "ollama"

    @property
    def host(self) -> str:
        """URL del servidor Ollama."""
        return self._host

    def _get_client(self) -> Client:
        """Obtiene o crea el cliente de Ollama (singleton por instancia)."""
        if self._client is None:
            self._client = Client(host=self._host)
        return self._client

    def _dump_to_stderr(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        """Si verbose está activo, imprime en stderr el payload enviado a Ollama."""
        if not settings.verbose:
            return
        payload = {"model": model, "messages": messages}
        if extra_body:
            payload.update(extra_body)
        print("--- enviado a Ollama ---", file=sys.stderr)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        print("--- fin ---", file=sys.stderr)

    @staticmethod
    def _extract_model_name(m: Any) -> str:
        """Extrae el nombre del modelo tanto si es objeto como dict."""
        if hasattr(m, "model"):
            return getattr(m, "model", "") or ""
        return m.get("model") or m.get("name") or ""

    @staticmethod
    def _format_http_error(status_code: int, reason: str | None, body: bytes | str | None) -> str:
        """Construye un mensaje legible a partir de una respuesta HTTP de error de Ollama."""
        detail = ""
        if body:
            if isinstance(body, bytes):
                raw = body.decode("utf-8", errors="replace")
            elif isinstance(body, str):
                raw = body
            else:
                raw = ""
            if raw:
                try:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        detail = (
                            data.get("error")
                            or data.get("message")
                            or data.get("Status")
                            or ""
                        )
                except json.JSONDecodeError:
                    detail = raw.strip()
        if detail:
            return f"HTTP {status_code}: {detail}"
        return f"HTTP {status_code}: {reason or 'Unknown'}"

    def list_models(self) -> list[ProviderModelInfo]:
        """
        Lista los modelos disponibles en Ollama.

        Returns:
            Lista de ProviderModelInfo con info de cada modelo.

        Raises:
            ConnectionError: Si no se puede conectar a Ollama.
        """
        try:
            client = self._get_client()
            response = client.list()
            models = (
                response.get("models", [])
                if isinstance(response, dict)
                else getattr(response, "models", [])
            )
            result = []
            for m in models:
                name = self._extract_model_name(m)
                if name:
                    result.append(
                        ProviderModelInfo(
                            name=name,
                            provider=self.provider_name,
                            context_length=None,  # Ollama no expone esto fácilmente
                            pricing=None,  # Ollama es local, sin pricing
                        )
                    )
            return result
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a Ollama: {e}") from e

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        """
        Envía mensajes a Ollama y devuelve la respuesta completa.

        Args:
            model: Nombre del modelo a usar.
            messages: Lista de mensajes {"role": str, "content": str}.
            extra_body: Fragmento a fusionar en el payload (ej. {"options": {...}}).

        Returns:
            Contenido de la respuesta del asistente.

        Raises:
            ConnectionError: Si no se puede conectar a Ollama.
        """
        self._dump_to_stderr(model, messages, extra_body)
        try:
            if extra_body:
                # Con opciones extra hay que enviar el body completo por HTTP
                url = f"{self._host.rstrip('/')}/api/chat"
                payload = {"model": model, "messages": messages, "stream": False}
                payload.update(extra_body)
                with httpx.Client(timeout=httpx.Timeout(120)) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code != 200:
                        raise ConnectionError(
                            self._format_http_error(
                                resp.status_code, resp.reason_phrase, resp.content
                            )
                        )
                    data = resp.json()
                content = data.get("message", {}).get("content", "")
                return content or ""
            client = self._get_client()
            response = client.chat(model=model, messages=messages)
            content = response.get("message", {}).get("content", "")
            return content or ""
        except Exception as e:
            raise ConnectionError(f"Error al llamar a Ollama: {e}") from e

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Streaming de respuesta desde Ollama.

        Args:
            model: Nombre del modelo a usar.
            messages: Lista de mensajes {"role": str, "content": str}.
            extra_body: Fragmento a fusionar en el payload (ej. {"options": {...}}).

        Yields:
            StreamChunk con contenido parcial, errores o metadata.

        Note:
            Al cerrar el iterador, se cancela la conexión a Ollama.
        """
        self._dump_to_stderr(model, messages, extra_body)
        url = f"{self._host.rstrip('/')}/api/chat"
        payload = {"model": model, "messages": messages, "stream": True}
        if extra_body:
            payload.update(extra_body)

        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=httpx.Timeout(None),
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield StreamChunk.error_chunk(
                            self._format_http_error(
                                response.status_code, response.reason_phrase, body
                            ),
                            status_code=response.status_code,
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Verificar error de Ollama
                        if data.get("error"):
                            yield StreamChunk.error_chunk(data["error"])
                            continue

                        # Extraer contenido
                        msg = data.get("message") or {}
                        content = msg.get("content") or ""
                        if content:
                            yield StreamChunk.content_chunk(content)

                        # Verificar si terminó (Ollama incluye prompt_eval_count y eval_count en el chunk final)
                        if data.get("done"):
                            usage = None
                            prompt_eval = data.get("prompt_eval_count")
                            eval_count = data.get("eval_count")
                            if prompt_eval is not None or eval_count is not None:
                                usage = {
                                    "prompt_tokens": int(prompt_eval) if prompt_eval is not None else 0,
                                    "completion_tokens": int(eval_count) if eval_count is not None else 0,
                                }
                            yield StreamChunk.done_chunk(
                                model=data.get("model"),
                                total_duration=data.get("total_duration"),
                                eval_count=eval_count,
                                usage=usage,
                            )
                            return

            except GeneratorExit:
                # Cliente canceló, no hacer nada más
                raise
            except Exception as e:
                yield StreamChunk.error_chunk(
                    str(e),
                    exception_type=type(e).__name__,
                )

    def validate_connection(self) -> bool:
        """
        Verifica que Ollama esté accesible.

        Returns:
            True si Ollama responde correctamente.
        """
        try:
            self.list_models()
            return True
        except Exception:
            return False

    def show_model(self, model_name: str) -> dict[str, Any] | None:
        """
        Capacidad opcional: detalles del modelo vía POST /api/show.
        Devuelve un dict normalizado para almacenar en provider_info (con fetched_at).
        None si el modelo no existe o hay error de conexión.
        """
        from datetime import datetime, timezone

        url = f"{self._host.rstrip('/')}/api/show"
        payload = {"model": model_name}
        try:
            with httpx.Client(timeout=httpx.Timeout(30)) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception:
            return None
        # Normalizar: incluir fetched_at y campos típicos de la API show
        out = {
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "parameters": data.get("parameters"),
            "template": data.get("template"),
            "license": data.get("license"),
            "modified_at": data.get("modified_at"),
            "details": data.get("details"),
            "capabilities": data.get("capabilities"),
            "model_info": data.get("model_info"),
        }
        return {k: v for k, v in out.items() if v is not None}

    def model_facts(self, model_name: str):
        """Hechos fiables del modelo (puerto ModelFacts) desde `/api/show`."""
        from app.services.model_contract.facts import facts_from_show

        return facts_from_show(self.show_model(model_name))

    # --- Métodos adicionales específicos de Ollama ---

    def list_running_models(self) -> list[str]:
        """Lista los modelos actualmente cargados en VRAM/RAM."""
        import urllib.error
        import urllib.request

        url = f"{self._host.rstrip('/')}/api/ps"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            raise
        models = data.get("models") or []
        return [self._extract_model_name(m) for m in models if self._extract_model_name(m)]

    def unload_model_from_memory(self, model: str) -> None:
        """Descarga el modelo de VRAM/RAM (liberar memoria)."""
        import urllib.error
        import urllib.request

        url = f"{self._host.rstrip('/')}/api/generate"
        payload = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            raise


# Singleton global para compatibilidad con código existente
_default_provider: OllamaProvider | None = None


def get_ollama_provider() -> OllamaProvider:
    """Obtiene el proveedor de Ollama singleton (compatibilidad con ollama_client)."""
    global _default_provider
    if _default_provider is None:
        _default_provider = OllamaProvider()
    return _default_provider
