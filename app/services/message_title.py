"""Título de un mensaje: primera frase, sin signos ni markup, con espacios entre palabras.

Comparte la limpieza con el título de conversación (``derive_auto_title``) y solo
añade un límite más corto para que el título sea una etiqueta breve con la que
buscar y ordenar.
"""

from __future__ import annotations

from app.services.conversation_title import derive_auto_title

MESSAGE_TITLE_MAX_LEN = 80


def derive_message_title(content: str | None) -> str:
    """Primera frase del mensaje; sin signos ni markup, con espacios. Vacío si no queda texto útil."""
    base = derive_auto_title(content)
    if not base:
        return ""
    return base[:MESSAGE_TITLE_MAX_LEN]
