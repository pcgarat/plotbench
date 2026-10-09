"""
Factory para crear instancias de proveedores de LLM.

Patrón Factory: Centraliza la creación de proveedores según configuración.
"""

from typing import TYPE_CHECKING

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.ollama import OllamaProvider

if TYPE_CHECKING:
    from app.providers.mancer import MancerProvider


class ProviderFactory:
    """
    Factory para crear instancias de proveedores de LLM.

    Uso:
        provider = ProviderFactory.get_provider("ollama")
        provider = ProviderFactory.get_provider("mancer")
        provider = ProviderFactory.get_default_provider()
    """

    _providers: dict[str, LLMProvider] = {}

    @classmethod
    def get_provider(cls, provider_type: str) -> LLMProvider:
        """
        Obtiene una instancia del proveedor especificado.

        Args:
            provider_type: Tipo de proveedor ("ollama", "mancer", "openai", "abliteration", "nan").

        Returns:
            Instancia del proveedor.

        Raises:
            ValueError: Si el tipo de proveedor no es válido.
        """
        provider_type = provider_type.lower().strip()

        # Cache de instancias (singleton por tipo)
        if provider_type in cls._providers:
            return cls._providers[provider_type]

        if provider_type == "ollama":
            provider = OllamaProvider()
        elif provider_type == "mancer":
            # Import diferido para evitar dependencias circulares
            from app.providers.mancer import MancerProvider

            provider = MancerProvider()
        elif provider_type == "openai":
            from app.providers.openai import OpenAIProvider

            provider = OpenAIProvider()
        elif provider_type == "abliteration":
            from app.providers.abliteration import AbliterationProvider

            provider = AbliterationProvider()
        elif provider_type == "nan":
            from app.providers.nan import NanProvider

            provider = NanProvider()
        else:
            raise ValueError(
                f"Proveedor '{provider_type}' no soportado. "
                f"Proveedores disponibles: ollama, mancer, openai, abliteration, nan"
            )

        cls._providers[provider_type] = provider
        return provider

    @classmethod
    def get_default_provider(cls) -> LLMProvider:
        """
        Obtiene el proveedor por defecto según configuración.

        Returns:
            Instancia del proveedor por defecto.
        """
        return cls.get_provider(settings.default_llm_provider)

    @classmethod
    def get_provider_for_model(cls, model_id: str) -> LLMProvider:
        """
        Obtiene el proveedor apropiado para un modelo.

        Si el model_id tiene formato "provider:model" (ej: "mancer:mytholite"),
        usa ese proveedor. Si no, usa el proveedor por defecto.

        Args:
            model_id: ID del modelo, opcionalmente con prefijo de proveedor.

        Returns:
            Tupla (provider, model_name) donde model_name es sin el prefijo.
        """
        if ":" in model_id:
            provider_type, model_name = model_id.split(":", 1)
            return cls.get_provider(provider_type)
        return cls.get_default_provider()

    @classmethod
    def parse_model_id(cls, model_id: str) -> tuple[str, str]:
        """
        Parsea un model_id y devuelve (provider_type, model_name).

        Args:
            model_id: ID del modelo (ej: "mancer:mytholite" o "llama3.2:latest").

        Returns:
            Tupla (provider_type, model_name).
        """
        if ":" in model_id:
            parts = model_id.split(":", 1)
            # Verificar si el primer parte es un proveedor conocido
            if parts[0].lower() in ("ollama", "mancer", "openai", "abliteration", "nan"):
                return parts[0].lower(), parts[1]
        # Si no hay prefijo de proveedor, usar el default
        return settings.default_llm_provider, model_id

    @classmethod
    def list_available_providers(cls) -> list[str]:
        """
        Lista los proveedores disponibles.

        Returns:
            Lista de nombres de proveedores.
        """
        providers = ["ollama"]
        if settings.mancer_api_key:
            providers.append("mancer")
        if settings.openai_api_key:
            providers.append("openai")
        if settings.ablit_key:
            providers.append("abliteration")
        if settings.nan_api_key:
            providers.append("nan")
        return providers

    @classmethod
    def clear_cache(cls) -> None:
        """Limpia la cache de instancias (útil para tests)."""
        cls._providers.clear()


# Función de conveniencia
def get_provider(provider_type: str | None = None) -> LLMProvider:
    """
    Obtiene un proveedor de LLM.

    Args:
        provider_type: Tipo de proveedor. Si es None, usa el default.

    Returns:
        Instancia del proveedor.
    """
    if provider_type is None:
        return ProviderFactory.get_default_provider()
    return ProviderFactory.get_provider(provider_type)
