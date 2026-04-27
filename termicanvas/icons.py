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
    # ícones adicionais para o Debug Monitor (estilo Feather/Lucide)
    "clipboard": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="9" y="2" width="6" height="4" rx="1"/>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '</svg>'
    ),
    "save": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 3 7 8 15 8"/>'
        '</svg>'
    ),
    "trash": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/>'
        '</svg>'
    ),
    "refresh-cw": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="23 4 23 10 17 10"/>'
        '<polyline points="1 20 1 14 7 14"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>'
        '</svg>'
    ),
    "bug": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="8" y="6" width="8" height="14" rx="4"/>'
        '<path d="M12 20v-9"/>'
        '<line x1="8" y1="2" x2="9.5" y2="3.5"/>'
        '<line x1="16" y1="2" x2="14.5" y2="3.5"/>'
        '<line x1="3" y1="10" x2="6" y2="11"/>'
        '<line x1="3" y1="16" x2="6" y2="15"/>'
        '<line x1="21" y1="10" x2="18" y2="11"/>'
        '<line x1="21" y1="16" x2="18" y2="15"/>'
        '</svg>'
    ),
    "cpu": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<rect x="9" y="9" width="6" height="6"/>'
        '<line x1="9" y1="2" x2="9" y2="4"/>'
        '<line x1="15" y1="2" x2="15" y2="4"/>'
        '<line x1="9" y1="20" x2="9" y2="22"/>'
        '<line x1="15" y1="20" x2="15" y2="22"/>'
        '<line x1="20" y1="9" x2="22" y2="9"/>'
        '<line x1="20" y1="14" x2="22" y2="14"/>'
        '<line x1="2" y1="9" x2="4" y2="9"/>'
        '<line x1="2" y1="14" x2="4" y2="14"/>'
        '</svg>'
    ),
    "memory": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="6" width="18" height="12" rx="1"/>'
        '<line x1="7" y1="6" x2="7" y2="18"/>'
        '<line x1="11" y1="6" x2="11" y2="18"/>'
        '<line x1="15" y1="6" x2="15" y2="18"/>'
        '<line x1="19" y1="6" x2="19" y2="18"/>'
        '</svg>'
    ),
    "box": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
        '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>'
        '<line x1="12" y1="22.08" x2="12" y2="12"/>'
        '</svg>'
    ),
    "monitor": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>'
        '<line x1="8" y1="21" x2="16" y2="21"/>'
        '<line x1="12" y1="17" x2="12" y2="21"/>'
        '</svg>'
    ),
    "clock": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="12 6 12 12 16 14"/>'
        '</svg>'
    ),
    "inbox": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
        '<path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
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
