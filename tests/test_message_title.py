"""Título de mensaje: primera frase, sin signos ni markup, con espacios entre palabras."""

import pytest

from app.services.conversation_title import TITLE_SOFT_MAX_LEN
from app.services.message_title import MESSAGE_TITLE_MAX_LEN, derive_message_title


@pytest.mark.parametrize(
    "content,expected",
    [
        ("Hola, mundo. Adiós.", "Hola mundo"),
        ("¿Qué hora es?", "Qué hora es"),
        ("solo una línea", "solo una línea"),
        ("La Ventana de la Culpa\nDesde mi punto de vista", "La Ventana de la Culpa"),
        ("El faro-3 y el mar_azul.", "El faro3 y el marazul"),
    ],
)
def test_derive_message_title_conserva_espacios(content, expected):
    assert derive_message_title(content) == expected


def test_derive_message_title_quita_html_e_ilustraciones():
    raw = '<p>Un faro al anochecer.</p><img class="chat-illustration" src="x.png"/>⟦img:s1⟧ Más texto.'
    assert derive_message_title(raw) == "Un faro al anochecer"


@pytest.mark.parametrize("content", ["", "   ", "!!!", None, "<img src='x.png'>"])
def test_derive_message_title_vacio_o_solo_ruido(content):
    assert derive_message_title(content) == ""


def test_derive_message_title_recorta_parrafo_largo():
    out = derive_message_title("palabra " * 40)
    assert out
    assert len(out) <= MESSAGE_TITLE_MAX_LEN
    assert len(out) <= TITLE_SOFT_MAX_LEN
    assert out.startswith("palabra palabra")
    assert not out.endswith(" ")
