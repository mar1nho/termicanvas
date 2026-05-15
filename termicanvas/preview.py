"""PreviewWidget: visualizador de Markdown/HTML como node do canvas."""

from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .icons import get_icon
from .tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    theme_palette,
)


MODE_AUTO = "auto"
MODE_MARKDOWN = "markdown"
MODE_HTML = "html"
MODES = {MODE_AUTO, MODE_MARKDOWN, MODE_HTML}


def mode_for_path(path: str) -> str:
    suffix = Path(path or "").suffix.lower()
    if suffix in (".md", ".markdown", ".mdown"):
        return MODE_MARKDOWN
    if suffix in (".html", ".htm"):
        return MODE_HTML
    return MODE_MARKDOWN


class PreviewWidget(QWidget):
    """Renderiza Markdown em QTextBrowser e HTML em QtWebEngine quando disponivel."""

    def __init__(self, path: str = "", mode: str = MODE_AUTO):
        super().__init__()
        self.path = str(path or "")
        self.mode = mode if mode in MODES else MODE_AUTO
        self._light_mode = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._toolbar = QWidget()
        row = QHBoxLayout(self._toolbar)
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(8)

        self._path_label = QLabel()
        row.addWidget(self._path_label, 1)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Auto", MODE_AUTO)
        self._mode_combo.addItem("Markdown", MODE_MARKDOWN)
        self._mode_combo.addItem("HTML", MODE_HTML)
        row.addWidget(self._mode_combo)

        self._open_btn = self._tool_button("Escolher arquivo", "folder")
        self._open_btn.clicked.connect(self.choose_file)
        row.addWidget(self._open_btn)

        self._refresh_btn = self._tool_button("Recarregar", "refresh-cw")
        self._refresh_btn.clicked.connect(self.reload)
        row.addWidget(self._refresh_btn)

        root.addWidget(self._toolbar)

        self._root_layout = root

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        root.addWidget(self.browser, 1)

        self.web = None
        self._html_scroll = QScrollArea()
        self._html_scroll.setWidgetResizable(False)
        self._html_image = QLabel()
        self._html_image.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._html_scroll.setWidget(self._html_image)
        self._html_scroll.hide()
        root.addWidget(self._html_scroll, 1)

        self._mode_combo.setCurrentIndex(max(0, [MODE_AUTO, MODE_MARKDOWN, MODE_HTML].index(self.mode)))
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._refresh_path_label()
        self._apply_theme()
        self.reload()

    def _tool_button(self, tooltip: str, icon_name: str) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(get_icon(icon_name, color=TEXT_SECONDARY, size=14))
        btn.setFixedSize(26, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        # Stylesheet aplicado em _apply_theme — registramos pra repintar.
        if not hasattr(self, "_tool_buttons"):
            self._tool_buttons = []
        self._tool_buttons.append(btn)
        return btn

    def _apply_theme(self):
        pal = theme_palette(self._light_mode)
        self.setStyleSheet(f"background: {pal['bg_surface']};")
        self._toolbar.setStyleSheet(
            f"background: {pal['bg_elevated']}; border-bottom: 1px solid {pal['border']};"
        )
        self._path_label.setStyleSheet(
            f"color: {pal['text_secondary']}; font-family: 'Cascadia Mono','Consolas',monospace;"
            "font-size: 8.5pt; background: transparent;"
        )
        self._mode_combo.setStyleSheet(f"""
            QComboBox {{
                background: {pal['bg_surface']}; color: {pal['text_primary']};
                border: 1px solid {pal['border']}; border-radius: 2px;
                padding: 4px 8px; font-size: 8.5pt;
            }}
            QComboBox:hover {{ border-color: {pal['border_hover']}; }}
            QComboBox QAbstractItemView {{
                background: {pal['bg_elevated']}; color: {pal['text_primary']};
                selection-background-color: {ACCENT};
            }}
        """)
        for btn in getattr(self, "_tool_buttons", []):
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: none; border-radius: 3px; }}
                QPushButton:hover {{ background: {pal['bg_surface']}; }}
            """)
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                background: {pal['bg_surface']}; color: {pal['text_primary']};
                border: none; padding: 14px;
                font-family: 'Segoe UI', sans-serif; font-size: 10.5pt;
                selection-background-color: {ACCENT};
            }}
            QScrollBar:vertical {{ background: {pal['bg_surface']}; width: 9px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {pal['border']}; border-radius: 4px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {pal['border_hover']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self._html_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {pal['bg_surface']}; border: none; }}
            QScrollBar:vertical {{ background: {pal['bg_surface']}; width: 9px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {pal['border']}; border-radius: 4px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {pal['border_hover']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self._html_image.setStyleSheet(f"background: {pal['bg_surface']};")
        if self.web is not None:
            self.web.setStyleSheet(f"background: {pal['bg_surface']}; border: none;")

    def set_light_mode(self, enabled: bool):
        self._light_mode = bool(enabled)
        self._apply_theme()

    def _on_mode_changed(self):
        self.mode = self._mode_combo.currentData() or MODE_AUTO
        self.reload()

    def choose_file(self):
        start = str(Path(self.path).parent) if self.path else str(Path.cwd())
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha um arquivo para preview",
            start,
            "Markdown/HTML (*.md *.markdown *.mdown *.html *.htm);;Todos os arquivos (*.*)",
        )
        if chosen:
            self.set_file(chosen)

    def set_file(self, path: str, mode: str | None = None):
        self.path = str(path or "")
        if mode is not None and mode in MODES:
            self.mode = mode
            idx = self._mode_combo.findData(mode)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
        self._refresh_path_label()
        self.reload()

    def _refresh_path_label(self):
        self._path_label.setText(self.path or "Nenhum arquivo selecionado")
        self._path_label.setToolTip(self.path)

    def reload(self):
        if not self.path:
            self._show_message("Escolha um arquivo Markdown ou HTML.")
            return

        path = Path(self.path)
        if not path.exists() or not path.is_file():
            self._show_message(f"Arquivo nao encontrado:<br><pre>{self.path}</pre>")
            return

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self._show_message(f"Erro ao ler arquivo: {e}")
            return

        render_mode = mode_for_path(self.path) if self.mode == MODE_AUTO else self.mode
        if render_mode == MODE_HTML:
            if self._ensure_web():
                self.browser.hide()
                self._html_scroll.show()
                self._html_image.setText("Carregando preview HTML...")
                self.web.load(QUrl.fromLocalFile(str(path.resolve())))
            else:
                self.browser.setSearchPaths([str(path.parent)])
                self.browser.setHtml(content)
                self._show_browser()
        else:
            self.browser.setSearchPaths([str(path.parent)])
            self.browser.setMarkdown(content)
            self._show_browser()

    def _show_message(self, message: str):
        self.browser.setHtml(f"<p style='color:{TEXT_MUTED};'>{message}</p>")
        self._show_browser()

    def _ensure_web(self) -> bool:
        if self.web is None:
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView
                from PyQt6.QtWebEngineCore import QWebEngineSettings
            except ImportError:
                return False
            self.web = QWebEngineView()
            settings = self.web.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self.web.setStyleSheet(f"background: {BG_SURFACE}; border: none;")
            self.web.resize(1200, 1800)
            self.web.move(-20000, -20000)
            self.web.loadFinished.connect(self._capture_web_snapshot)
            self.web.show()
        return True

    def _show_browser(self):
        self._html_scroll.hide()
        self.browser.show()

    def _capture_web_snapshot(self, ok: bool):
        if not ok or self.web is None:
            self._html_image.setText("Falha ao carregar HTML.")
            return
        QTimer.singleShot(350, self._resize_web_to_document)

    def _resize_web_to_document(self):
        if self.web is None:
            return
        script = "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 800)"
        self.web.page().runJavaScript(script, self._on_document_height)

    def _on_document_height(self, height):
        if self.web is None:
            return
        try:
            h = int(height)
        except (TypeError, ValueError):
            h = 1800
        self.web.resize(1200, max(800, min(h + 40, 12000)))
        QTimer.singleShot(150, self._grab_web_snapshot)

    def _grab_web_snapshot(self):
        if self.web is None:
            return
        pixmap = self.web.grab()
        if pixmap.isNull():
            self._html_image.setText("Falha ao renderizar HTML.")
            return
        self._html_image.setPixmap(pixmap)
        self._html_image.resize(pixmap.size())

    def shutdown(self):
        if self.web is not None:
            try:
                self.web.stop()
                self.web.hide()
                self.web.setParent(None)
                self.web.deleteLater()
            except Exception:
                pass
            self.web = None
        self._html_image.clear()
        try:
            self.browser.clear()
        except Exception:
            pass
