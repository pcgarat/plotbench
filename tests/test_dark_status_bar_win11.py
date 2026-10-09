"""Barra de estado en dark: fondo navy Win11 como los laterales."""
from pathlib import Path
import re

STYLE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "styles" / "style.css"


def test_dark_status_bar_uses_win11_sidebar_navy():
    css = STYLE.read_text(encoding="utf-8")
    matches = list(re.finditer(r'\[data-theme="dark"\] \.app-status-bar\s*\{', css))
    assert matches, "Falta estilo dark de app-status-bar"
    bodies = []
    for m in matches:
        start = m.end()
        depth = 1
        i = start
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        bodies.append(css[start : i - 1])
    # Isla flotante: la barra comparte el lienzo continuo (shell canvas), ya no es
    # una banda navy propia; y se anula el efecto mica.
    assert any("--shell-canvas" in body for body in bodies)
    assert any("backdrop-filter: none" in body for body in bodies)
