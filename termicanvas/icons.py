"""Ícones SVG monocromáticos inline para a UI.

Substitui emojis (📝, 🔁, ☰, ×, +, −, ▸, ⊞) por ícones vetoriais que
respondem a uma cor passada como parâmetro. Renderizado em runtime via
QSvgRenderer → QPixmap → QIcon.

Uso:
    from .icons import get_icon
    btn.setIcon(get_icon("edit", color=TEXT_MUTED))
    btn.setIconSize(QSize(14, 14))
"""

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# SVGs em viewBox 0 0 24 24, sem width/height fixos.
# Marcador "currentColor" em stroke= ou fill= é substituído pela cor pedida.
SVG_PATHS = {
    # ícones de stroke (linha) — usam stroke="currentColor"
    "edit": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>'
        '</svg>'
    ),
    "reply": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="9 14 4 9 9 4"/>'
        '<path d="M20 20v-7a4 4 0 0 0-4-4H4"/>'
        '</svg>'
    ),
    "menu": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="4" y1="6" x2="20" y2="6"/>'
        '<line x1="4" y1="12" x2="20" y2="12"/>'
        '<line x1="4" y1="18" x2="20" y2="18"/>'
        '</svg>'
    ),
    "chevron-left": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="15 18 9 12 15 6"/>'
        '</svg>'
    ),
    "chevron-right": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="9 18 15 12 9 6"/>'
        '</svg>'
    ),
    "plus": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="12" y1="5" x2="12" y2="19"/>'
        '<line x1="5" y1="12" x2="19" y2="12"/>'
        '</svg>'
    ),
    "minus": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="5" y1="12" x2="19" y2="12"/>'
        '</svg>'
    ),
    "square": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="4" y="4" width="16" height="16" rx="1"/>'
        '</svg>'
    ),
    # close em stroke (X de duas linhas) — fica mais limpo que fill
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="6" y1="6" x2="18" y2="18"/>'
        '<line x1="18" y1="6" x2="6" y2="18"/>'
        '</svg>'
    ),
    # ícones de fill — usam fill="currentColor"
    "dot": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor">'
        '<circle cx="12" cy="12" r="4"/>'
        '</svg>'
    ),
    "play": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor">'
        '<polygon points="8,5 19,12 8,19"/>'
        '</svg>'
    ),
}

# Cache módulo-level: (name, color, size) → QIcon
_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}


def get_icon(name: str, color: str = "#a8a8a8", size: int = 16) -> QIcon:
    """Retorna QIcon monocromático na cor pedida.

    Args:
        name: chave do dict SVG_PATHS.
        color: cor em hex (#rrggbb) ou nome válido em CSS.
        size: tamanho do pixmap em pixels (largura = altura).

    Retorna QIcon vazio se o nome não existir (não quebra a UI).
    """
    key = (name, color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    svg = SVG_PATHS.get(name)
    if svg is None:
        empty = QIcon()
        _ICON_CACHE[key] = empty
        return empty

    # substitui currentColor pela cor real
    svg_colored = svg.replace("currentColor", color)

    renderer = QSvgRenderer(QByteArray(svg_colored.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _ICON_CACHE[key] = icon
    return icon
