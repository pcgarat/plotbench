"""
Interfaz base para proveedores de LLM.

Usa Protocol (structural subtyping) para definir el contrato que
todos los proveedores deben cumplir.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class ProviderModelInfo:
    """Información de un modelo del proveedor."""

    name: str
    provider: str
    display_name: str | None = None
    context_length: int | None = None
    pricing: dict[str, float] | None = None  # {"prompt_per_1k": 0.001, "completion_per_1k": 0.002}

    def __post_init__(self):
        if self.display_name is None:
            self.display_name = f"{self.name} ({self.provider})"


@dataclass
class StreamChunk:
    """
    Chunk de respuesta en streaming.

    Tipos de chunks:
    - content: Contenido parcial de la respuesta
    - done: Indica fin del stream
    - error: Error durante el streaming
    - metadata: Info adicional (model, usage, etc.)
    """

    type: str  # "content" | "done" | "error" | "metadata"
    content: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def content_chunk(cls, content: str) -> "StreamChunk":
        """Crea un chunk de contenido."""
        return cls(type="content", content=content)

    @classmethod
    def done_chunk(cls, **metadata) -> "StreamChunk":
        """Crea un chunk de fin de stream."""
        return cls(type="done", metadata=metadata)

    @classmethod
    def error_chunk(cls, error: str, **metadata) -> "StreamChunk":
        """Crea un chunk de error."""
        return cls(type="error", error=error, metadata=metadata)

    @classmethod
    def metadata_chunk(cls, **metadata) -> "StreamChunk":
        """Crea un chunk de metadata."""
        return cls(type="metadata", metadata=metadata)


@runtime_checkable
class LLMProvider(Protocol):
    """
    Interfaz común para todos los proveedores de LLM.

    Implementaciones:
    - OllamaProvider: Modelos locales
    - MancerProvider: Mancer.tech (API OpenAI-compatible)
    - OpenAIProvider: API oficial OpenAI
    - AbliterationProvider: abliteration.ai (API OpenAI-compatible)
    - NanProvider: NaN Builders (API OpenAI-compatible)

    Capacidad opcional (no en el Protocol, se comprueba con `hasattr`):
    - model_facts(model_name) -> ModelFacts: hechos fiables del modelo para el
      generador de overlays (Ollama los deriva de show; NaN, de su catálogo).
    """

    @property
    def provider_name(self) -> str:
        """Nombre identificador del proveedor (ej: 'ollama', 'mancer')."""
        ...

    def list_models(self) -> list[ProviderModelInfo]:
        """
        Lista los modelos disponibles en este proveedor.

        Returns:
            Lista de ProviderModelInfo con info de cada modelo.

        Raises:
            ConnectionError: Si no se puede conectar al proveedor.
        """
        ...

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        """
        Envía mensajes y devuelve la respuesta completa (sin streaming).

        Args:
            model: Nombre del modelo a usar.
            messages: Lista de mensajes con format {"role": str, "content": str}.
            extra_body: Fragmento a fusionar en el payload HTTP (parámetros de generación).

        Returns:
            Contenido de la respuesta del asistente.

        Raises:
            ConnectionError: Si no se puede conectar al proveedor.
            ValueError: Si el modelo no existe o hay error en los mensajes.
        """
        ...

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Streaming de respuesta.

        Args:
            model: Nombre del modelo a usar.
            messages: Lista de mensajes con format {"role": str, "content": str}.
            extra_body: Fragmento a fusionar en el payload HTTP (parámetros de generación).

        Yields:
            StreamChunk con contenido parcial, errores o metadata.

        Note:
            Al cerrar el iterador (GeneratorExit), se debe cancelar
            la conexión al proveedor para detener la generación.
        """
        ...

    def validate_connection(self) -> bool:
        """
        Verifica que el proveedor esté accesible.

        Returns:
            True si el proveedor responde correctamente.
        """
        ...
