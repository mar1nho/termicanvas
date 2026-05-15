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
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4.56 -4.56 33.12 33.12" '
        'fill="none">'
        '<path d="M7.81 2C6.32 2 5.08 2.36 4.13 3.05C3.71 3.34 3.34 3.71 3.05 4.13C2.36 5.08 2 6.32 2 7.81V16.19C2 19.83 4.17 22 7.81 22H15.28V2H7.81ZM12.12 12.53L9.56 15.09C9.41 15.24 9.22 15.31 9.03 15.31C8.84 15.31 8.65 15.24 8.5 15.09C8.21 14.8 8.21 14.32 8.5 14.03L10.52 12L8.5 9.97C8.2 9.68 8.2 9.2 8.5 8.91C8.8 8.62 9.27 8.62 9.56 8.91L12.12 11.47C12.41 11.76 12.41 12.24 12.12 12.53Z" fill="currentColor"/>'
        '<path d="M16.7793 2.03125V21.9812C18.0093 21.9012 19.0493 21.5513 19.8693 20.9513C20.2893 20.6612 20.6593 20.2913 20.9493 19.8713C21.6393 18.9212 21.9993 17.6813 21.9993 16.1913V7.81125C21.9993 4.37125 20.0593 2.24125 16.7793 2.03125Z" fill="currentColor"/>'
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
    "chevron-down": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 12 15 18 9"/>'
        '</svg>'
    ),
    # Sol — modo claro (clique pra ir pra light)
    "sun": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="4"/>'
        '<line x1="12" y1="2" x2="12" y2="5"/>'
        '<line x1="12" y1="19" x2="12" y2="22"/>'
        '<line x1="2" y1="12" x2="5" y2="12"/>'
        '<line x1="19" y1="12" x2="22" y2="12"/>'
        '<line x1="4.93" y1="4.93" x2="7.05" y2="7.05"/>'
        '<line x1="16.95" y1="16.95" x2="19.07" y2="19.07"/>'
        '<line x1="4.93" y1="19.07" x2="7.05" y2="16.95"/>'
        '<line x1="16.95" y1="7.05" x2="19.07" y2="4.93"/>'
        '</svg>'
    ),
    # Lua — modo escuro (clique pra voltar pra dark)
    "moon": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
        '</svg>'
    ),
    # Globe
    "globe": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="2" y1="12" x2="22" y2="12"/>'
        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
        '</svg>'
    ),
    # Link — corrente de dois elos (usada pra criar chain entre agentes)
    "link": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
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
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
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
    "terminal_ps": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
        'fill="currentColor">'
        '<path d="M16.012 21.897c-0.004-0-0.009-0-0.014-0-0.637 0-1.153 0.516-1.153 1.154'
        's0.516 1.154 1.153 1.154c0.005 0 0.010-0 0.015-0h5.539c0.003 0 0.007 0 0.011 0'
        ' 0.637 0 1.153-0.516 1.153-1.153s-0.516-1.153-1.153-1.153c-0.004 0-0.008 0-0.011 0h0.001z'
        'M19.506 16.4c0.134-0.198 0.214-0.442 0.214-0.704 0-0.327-0.124-0.625-0.327-0.85'
        'l0.001 0.001-6.99-7.438c-0.239-0.227-0.562-0.367-0.918-0.367-0.736 0-1.333 0.597'
        '-1.333 1.333 0 0.326 0.117 0.625 0.311 0.856l-0.002-0.002 5.826 6.198v0.137'
        'l-9.272 6.716c-0.299 0.246-0.489 0.617-0.489 1.032 0 0.736 0.597 1.333 1.333 1.333'
        ' 0.268 0 0.517-0.079 0.726-0.215l-0.005 0.003 10.283-7.385'
        'c0.265-0.163 0.482-0.382 0.638-0.641l0.005-0.009z'
        'M29.972 4.721c0.012-0.001 0.026-0.001 0.041-0.001 0.55 0 0.995 0.446 0.995 0.995'
        ' 0 0.107-0.017 0.21-0.048 0.306l0.002-0.007-4.572 19.972'
        'c-0.187 0.724-0.817 1.256-1.577 1.293l-0.004 0h-22.781'
        'c-0.012 0.001-0.026 0.001-0.041 0.001-0.55 0-0.995-0.446-0.995-0.995'
        ' 0-0.107 0.017-0.21 0.048-0.306l-0.002 0.007 4.572-19.972'
        'c0.187-0.724 0.817-1.256 1.577-1.293l0.004-0z"/>'
        '</svg>'
    ),
    "terminal_cmd": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="16" rx="2"/>'
        '<polyline points="7 10 10 13 7 16"/>'
        '<line x1="12" y1="16" x2="17" y2="16"/>'
        '</svg>'
    ),
    "agent_code": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor" fill-rule="evenodd">'
        '<path clip-rule="evenodd" d="M20.998 10.949H24v3.102h-3v3.028h-1.487V20H18v-2.921'
        'h-1.487V20H15v-2.921H9V20H7.488v-2.921H6V20H4.487v-2.921H3V14.05H0V10.95h3V5'
        'h17.998v5.949zM6 10.949h1.488V8.102H6v2.847zm10.51 0H18V8.102h-1.49v2.847z"/>'
        '</svg>'
    ),
    "agent_openai": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor" fill-rule="evenodd">'
        '<path d="M9.205 8.658v-2.26c0-.19.072-.333.238-.428l4.543-2.616c.619-.357 '
        '1.356-.523 2.117-.523 2.854 0 4.662 2.212 4.662 4.566 0 .167 0 .357-.024.547'
        'l-4.71-2.759a.797.797 0 00-.856 0l-5.97 3.473zm10.609 8.8V12.06c0-.333-.143'
        '-.57-.429-.737l-5.97-3.473 1.95-1.118a.433.433 0 01.476 0l4.543 2.617c1.309'
        '.76 2.189 2.378 2.189 3.948 0 1.808-1.07 3.473-2.76 4.163zM7.802 12.703l-1.95'
        '-1.142c-.167-.095-.239-.238-.239-.428V5.899c0-2.545 1.95-4.472 4.591-4.472 '
        '1 0 1.927.333 2.712.928L8.23 5.067c-.285.166-.428.404-.428.737v6.898zM12 '
        '15.128l-2.795-1.57v-3.33L12 8.658l2.795 1.57v3.33L12 15.128zm1.796 7.23c-1 '
        '0-1.927-.332-2.712-.927l4.686-2.712c.285-.166.428-.404.428-.737v-6.898l1.974 '
        '1.142c.167.095.238.238.238.428v5.233c0 2.545-1.974 4.472-4.614 4.472zm-5.637'
        '-5.303l-4.544-2.617c-1.308-.761-2.188-2.378-2.188-3.948A4.482 4.482 0 014.21 '
        '6.327v5.423c0 .333.143.571.428.738l5.947 3.449-1.95 1.118a.432.432 0 01-.476 '
        '0zm-.262 3.9c-2.688 0-4.662-2.021-4.662-4.519 0-.19.024-.38.047-.57l4.686 '
        '2.71c.286.167.571.167.856 0l5.97-3.448v2.26c0 .19-.07.333-.237.428l-4.543 '
        '2.616c-.619.357-1.356.523-2.117.523zm5.899 2.83a5.947 5.947 0 005.827-4.756'
        'C22.287 18.339 24 15.84 24 13.296c0-1.665-.713-3.282-1.998-4.448.119-.5.19'
        '-.999.19-1.498 0-3.401-2.759-5.947-5.946-5.947-.642 0-1.26.095-1.88.31A5.962'
        ' 5.962 0 0010.205 0a5.947 5.947 0 00-5.827 4.757C1.713 5.447 0 7.945 0 10.49'
        'c0 1.666.713 3.283 1.998 4.448-.119.5-.19 1-.19 1.499 0 3.401 2.759 5.946 '
        '5.946 5.946.642 0 1.26-.095 1.88-.309a5.96 5.96 0 004.162 1.713z"/>'
        '</svg>'
    ),
    "agent_claude": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor" fill-rule="evenodd">'
        '<path d="M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097'
        '-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097'
        ' 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972'
        '-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491'
        ' 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619'
        'a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229'
        ' 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76'
        '.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212'
        'l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166'
        '-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28'
        ' 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061'
        ' 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91'
        '-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049'
        '-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353'
        '-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37'
        '-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042'
        '-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589'
        ' 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456'
        '.061-.746.231-.243 1.908-1.312-.006.006z"/>'
        '</svg>'
    ),
    "agent_gemini": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="currentColor" fill-rule="evenodd">'
        '<path d="M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452'
        '.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001'
        'c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677'
        'a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0'
        'c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678'
        '.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z"/>'
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
