"""Design tokens: cores usadas em toda a UI + helpers de contraste."""

BG_CANVAS   = "#000000"
BG_SURFACE  = "#1a1a1a"
BG_SIDEBAR  = "#0a0a0a"
BG_ELEVATED = "#242424"
BG_TERMINAL = "#0f0f0f"

BORDER       = "#333333"
BORDER_HOVER = "#4a4a4a"
BORDER_FOCUS = "#5a8dff"

TEXT_PRIMARY   = "#f0f0f0"
TEXT_SECONDARY = "#a8a8a8"
TEXT_MUTED     = "#666666"

ACCENT       = "#5a8dff"
ACCENT_HOVER = "#7aa3ff"
ACCENT_PRESS = "#4a75d8"

DANGER  = "#e5484d"
SUCCESS = "#5eba7d"


# Fallback usado quando uma cor custom tem luminância muito baixa
# e a borda de um node/chip ficaria invisível contra o fundo.
DARK_BORDER_FALLBACK = "#4a4a4a"  # mesmo valor de BORDER_HOVER; separado semanticamente


def _hex_to_rgb(hex_color):
    """Converte '#rrggbb' em (r, g, b) floats em [0, 1]."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    try:
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.0, 0.0, 0.0)


def relative_luminance(hex_color):
    """Luminancia relativa WCAG (0 = preto, 1 = branco)."""
    r, g, b = _hex_to_rgb(hex_color)

    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def readable_text_color(bg_hex):
    """Retorna '#000000' ou '#ffffff' conforme contraste contra o fundo."""
    return "#000000" if relative_luminance(bg_hex) > 0.5 else "#ffffff"


def safe_border_color(color_hex, threshold=0.05):
    """
    Se a cor for muito escura (luminancia < threshold), devolve DARK_BORDER_FALLBACK.
    Caso contrario, devolve a propria cor.
    Usado para evitar bordas invisiveis contra fundos pretos.
    """
    return DARK_BORDER_FALLBACK if relative_luminance(color_hex) < threshold else color_hex
