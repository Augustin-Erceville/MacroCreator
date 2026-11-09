"""Thème de l'interface : palettes, feuille de style et pictogrammes.

Deux palettes sont disponibles (« sombre » et « claire »). La feuille de
style Qt est construite à partir de la palette choisie, ce qui évite de
disséminer des couleurs en dur dans le reste du code.

Les pictogrammes des actions sont dessinés à l'exécution (formes
géométriques simples) plutôt que chargés depuis des fichiers : ils
s'adaptent ainsi à la palette et ne dépendent d'aucune police.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# ==============================================================
# PALETTES
# ==============================================================

DARK = {
    "name": "dark",
    "bg": "#16181d",
    "surface": "#1e2127",
    "surface_alt": "#262a32",
    "border": "#323741",
    "text": "#e8eaf0",
    "muted": "#9298a6",
    "accent": "#4c8dff",
    "accent_hover": "#5f9bff",
    "accent_pressed": "#3d7ae6",
    "on_accent": "#ffffff",
    "danger": "#ef5b5b",
    "danger_hover": "#f36f6f",
    "success": "#43c17a",
    "warning": "#efb45b",
    "selection": "#2f3b52",
    "hover": "#272c35",
    "running": "#2a3a2f",
}

LIGHT = {
    "name": "light",
    "bg": "#f4f5f8",
    "surface": "#ffffff",
    "surface_alt": "#eef0f5",
    "border": "#d8dce4",
    "text": "#1c1f26",
    "muted": "#6b7280",
    "accent": "#2f6df6",
    "accent_hover": "#4580ff",
    "accent_pressed": "#2559d0",
    "on_accent": "#ffffff",
    "danger": "#d94040",
    "danger_hover": "#e25555",
    "success": "#1f9d5a",
    "warning": "#b8780f",
    "selection": "#dbe6ff",
    "hover": "#eaeef7",
    "running": "#dcf3e4",
}

PALETTES = {"dark": DARK, "light": LIGHT}

DEFAULT_PALETTE = "dark"

# Palette active, mise à jour par apply_theme()
_current = DARK


def current():
    return _current


def color(key):
    """Couleur de la palette active, sous forme de texte CSS."""

    return _current.get(key, "#000000")


# ==============================================================
# FEUILLE DE STYLE
# ==============================================================

def stylesheet(palette):

    return f"""
    QWidget {{
        background-color: {palette['bg']};
        color: {palette['text']};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}

    QMainWindow, QDialog {{
        background-color: {palette['bg']};
    }}

    /* ----- Barre de menus ----- */

    QMenuBar {{
        background-color: {palette['bg']};
        border-bottom: 1px solid {palette['border']};
        padding: 2px 4px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: 6px;
    }}

    QMenuBar::item:selected {{
        background-color: {palette['hover']};
    }}

    QMenu {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
        padding: 6px;
    }}

    QMenu::item {{
        padding: 7px 24px 7px 14px;
        border-radius: 6px;
    }}

    QMenu::item:selected {{
        background-color: {palette['accent']};
        color: {palette['on_accent']};
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {palette['border']};
        margin: 6px 8px;
    }}

    /* ----- Cartes et sections ----- */

    QGroupBox {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
        margin-top: 14px;
        padding: 14px 12px 12px 12px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 6px;
        color: {palette['muted']};
        font-size: 11px;
        text-transform: uppercase;
    }}

    QFrame#card {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
    }}

    QFrame#header {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
    }}

    QFrame#separator {{
        background-color: {palette['border']};
        max-height: 1px;
        border: none;
    }}

    /* ----- Boutons ----- */

    QPushButton {{
        background-color: {palette['surface_alt']};
        color: {palette['text']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
        padding: 8px 14px;
        text-align: left;
    }}

    QPushButton:hover {{
        background-color: {palette['hover']};
        border-color: {palette['accent']};
    }}

    QPushButton:pressed {{
        background-color: {palette['accent_pressed']};
        color: {palette['on_accent']};
    }}

    QPushButton:disabled {{
        color: {palette['muted']};
        border-color: {palette['border']};
        background-color: {palette['surface']};
    }}

    QPushButton#primary {{
        background-color: {palette['accent']};
        color: {palette['on_accent']};
        border: none;
        font-weight: 600;
        text-align: center;
        padding: 10px 22px;
    }}

    QPushButton#primary:hover {{
        background-color: {palette['accent_hover']};
    }}

    QPushButton#primary:pressed {{
        background-color: {palette['accent_pressed']};
    }}

    QPushButton#danger {{
        background-color: {palette['danger']};
        color: #ffffff;
        border: none;
        font-weight: 600;
        text-align: center;
        padding: 10px 22px;
    }}

    QPushButton#danger:hover {{
        background-color: {palette['danger_hover']};
    }}

    QPushButton#record {{
        font-weight: 600;
        text-align: center;
    }}

    QPushButton#record:hover {{
        border-color: {palette['danger']};
    }}

    QPushButton#compact {{
        text-align: center;
        padding: 7px 8px;
    }}

    /* ----- Champs de saisie ----- */

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
        background-color: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {palette['accent']};
        selection-color: {palette['on_accent']};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QComboBox:focus, QTextEdit:focus {{
        border-color: {palette['accent']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
        selection-background-color: {palette['accent']};
        selection-color: {palette['on_accent']};
        padding: 4px;
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border: none;
        width: 16px;
    }}

    QCheckBox {{
        spacing: 8px;
        background: transparent;
    }}

    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border: 1px solid {palette['border']};
        border-radius: 5px;
        background-color: {palette['surface_alt']};
    }}

    QCheckBox::indicator:checked {{
        background-color: {palette['accent']};
        border-color: {palette['accent']};
    }}

    /* ----- Listes et arbres ----- */

    QTreeWidget, QListWidget {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 10px;
        padding: 6px;
        outline: none;
    }}

    QTreeWidget::item, QListWidget::item {{
        padding: 7px 6px;
        border-radius: 7px;
        margin: 1px 2px;
    }}

    QTreeWidget::item:hover, QListWidget::item:hover {{
        background-color: {palette['hover']};
    }}

    QTreeWidget::item:selected, QListWidget::item:selected {{
        background-color: {palette['selection']};
        color: {palette['text']};
    }}

    /* ----- Barres de défilement ----- */

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {palette['border']};
        border-radius: 5px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {palette['muted']};
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px 4px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {palette['border']};
        border-radius: 5px;
        min-width: 30px;
    }}

    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
        width: 0;
    }}

    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}

    /* ----- Progression ----- */

    QProgressBar {{
        background-color: {palette['surface_alt']};
        border: none;
        border-radius: 5px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background-color: {palette['accent']};
        border-radius: 5px;
    }}

    QProgressBar#wait::chunk {{
        background-color: {palette['warning']};
    }}

    /* ----- Libellés ----- */

    QLabel {{
        background: transparent;
    }}

    QLabel#appTitle {{
        font-size: 17px;
        font-weight: 700;
    }}

    QLabel#macroName {{
        font-size: 13px;
        color: {palette['muted']};
    }}

    QLabel#sectionTitle {{
        font-size: 11px;
        font-weight: 600;
        color: {palette['muted']};
    }}

    QLabel#hint {{
        color: {palette['muted']};
        font-size: 12px;
    }}

    QLabel#currentAction {{
        font-size: 15px;
        font-weight: 600;
    }}

    QLabel#countdown {{
        font-size: 26px;
        font-weight: 700;
        color: {palette['warning']};
    }}

    QLabel#stepCounter {{
        color: {palette['muted']};
        font-size: 12px;
    }}

    QLabel#idleState {{
        color: {palette['muted']};
    }}

    /* ----- Canevas de blocs ----- */

    QScrollArea#canvas {{
        background-color: {palette['bg']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
    }}

    QWidget#canvasContent {{
        background-color: {palette['bg']};
    }}

    QLabel#endpoint {{
        background-color: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: 11px;
        padding: 3px 14px;
        color: {palette['muted']};
        font-size: 10px;
        font-weight: 700;
    }}

    QLabel#emptyFlow {{
        color: {palette['muted']};
        font-size: 12px;
        font-style: italic;
        padding: 10px;
    }}

    QFrame#block {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
    }}

    QFrame#block:hover {{
        border-color: {palette['muted']};
    }}

    QFrame#block[selected="true"] {{
        border: 2px solid {palette['accent']};
    }}

    QFrame#block[running="true"] {{
        border: 2px solid {palette['success']};
        background-color: {palette['running']};
    }}

    QWidget#blockHeader {{
        background: transparent;
    }}

    QLabel#blockTitle {{
        font-size: 14px;
        font-weight: 600;
        background: transparent;
    }}

    QLabel#blockSubtitle {{
        color: {palette['muted']};
        font-size: 12px;
        background: transparent;
    }}

    QPushButton#blockAction {{
        background-color: {palette['accent']};
        color: {palette['on_accent']};
        border: none;
        border-radius: 7px;
        padding: 6px 14px;
        font-weight: 600;
        text-align: center;
    }}

    QPushButton#blockAction:hover {{
        background-color: {palette['accent_hover']};
    }}

    QPushButton#blockRemove {{
        background-color: transparent;
        color: {palette['muted']};
        border: none;
        border-radius: 14px;
        font-size: 14px;
        text-align: center;
        padding: 0;
    }}

    QPushButton#blockRemove:hover {{
        background-color: {palette['danger']};
        color: #ffffff;
    }}

    QPushButton#node {{
        background-color: {palette['surface_alt']};
        color: {palette['muted']};
        border: 1px solid {palette['border']};
        border-radius: 12px;
        font-size: 15px;
        font-weight: 700;
        padding: 0;
        text-align: center;
    }}

    QPushButton#node:hover {{
        background-color: {palette['accent']};
        color: {palette['on_accent']};
        border-color: {palette['accent']};
    }}

    QFrame#branch {{
        background-color: {palette['surface_alt']};
        border: 1px solid {palette['border']};
        border-radius: 10px;
    }}

    QLabel#branchLabel {{
        font-size: 10px;
        font-weight: 700;
        color: {palette['success']};
        background: transparent;
        padding-bottom: 2px;
    }}

    QLabel#branchLabel[branch="else"] {{
        color: {palette['danger']};
    }}

    /* ----- Sélecteur de bloc ----- */

    QPushButton#picker {{
        background-color: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 10px;
        padding: 10px 12px;
        text-align: left;
    }}

    QPushButton#picker:hover {{
        border-color: {palette['accent']};
        background-color: {palette['hover']};
    }}

    QLabel#pickerTitle {{
        font-size: 13px;
        font-weight: 600;
        background: transparent;
    }}

    QLabel#pickerSummary {{
        color: {palette['muted']};
        font-size: 11px;
        background: transparent;
    }}

    /* ----- Barre d'état ----- */

    QStatusBar {{
        background-color: {palette['bg']};
        border-top: 1px solid {palette['border']};
        color: {palette['muted']};
    }}

    QStatusBar::item {{
        border: none;
    }}

    QToolTip {{
        background-color: {palette['surface_alt']};
        color: {palette['text']};
        border: 1px solid {palette['border']};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    """


def repolish_widget(widget):
    """Réapplique la feuille de style après un changement de nom ou de
    propriété (Qt ne le fait pas automatiquement)."""

    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def apply_theme(application, name=DEFAULT_PALETTE):
    """Applique une palette à toute l'application."""

    global _current

    _current = PALETTES.get(name, DARK)

    application.setStyleSheet(stylesheet(_current))

    _ICON_CACHE.clear()

    return _current


# ==============================================================
# PICTOGRAMMES DES ACTIONS
# ==============================================================

ACTION_COLORS = {
    "wait": "#f0a93b",
    "move": "#35c4d0",
    "click": "#4c8dff",
    "drag": "#7b8cff",
    "scroll": "#3bc9a3",
    "text": "#a97bff",
    "key": "#e06ec0",
    "loop": "#4cc77d",
    "condition": "#ff8a5c",
}

ICON_SIZE = 32

_ICON_CACHE = {}


def action_color(action_type):

    return ACTION_COLORS.get(action_type, _current["muted"])


def action_icon(action_type):
    """Pastille colorée illustrant un type d'action (QIcon, mise en cache)."""

    if action_type in _ICON_CACHE:
        return _ICON_CACHE[action_type]

    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)

    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    tint = QColor(action_color(action_type))

    # Fond teinté translucide
    background = QColor(tint)

    background.setAlpha(46)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(background)

    painter.drawRoundedRect(QRectF(0, 0, ICON_SIZE, ICON_SIZE), 9, 9)

    pen = QPen(tint)

    pen.setWidthF(2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    _draw_glyph(painter, action_type, tint)

    painter.end()

    icon = QIcon(pixmap)

    _ICON_CACHE[action_type] = icon

    return icon


def _draw_glyph(painter, action_type, tint):
    """Dessine le symbole propre à chaque type d'action."""

    if action_type == "wait":

        # Horloge : cercle et deux aiguilles
        painter.drawEllipse(QRectF(8, 8, 16, 16))

        painter.drawLine(QPointF(16, 16), QPointF(16, 11.5))
        painter.drawLine(QPointF(16, 16), QPointF(19.5, 18))

        return

    if action_type == "move":

        # Flèche diagonale
        painter.drawLine(QPointF(9, 23), QPointF(22, 10))

        painter.drawLine(QPointF(22, 10), QPointF(15.5, 10.5))
        painter.drawLine(QPointF(22, 10), QPointF(21.5, 16.5))

        return

    if action_type == "click":

        # Point de clic et onde
        painter.setBrush(tint)

        painter.drawEllipse(QRectF(13, 13, 6, 6))

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawArc(QRectF(8, 8, 16, 16), 30 * 16, 120 * 16)
        painter.drawArc(QRectF(8, 8, 16, 16), 210 * 16, 120 * 16)

        return

    if action_type == "drag":

        # Deux points reliés
        painter.drawLine(QPointF(11, 21), QPointF(21, 11))

        painter.setBrush(tint)

        painter.drawEllipse(QRectF(8, 18, 6, 6))
        painter.drawEllipse(QRectF(18, 8, 6, 6))

        painter.setBrush(Qt.BrushStyle.NoBrush)

        return

    if action_type == "scroll":

        # Corps de souris et molette
        painter.drawRoundedRect(QRectF(11, 7, 10, 18), 5, 5)

        painter.drawLine(QPointF(16, 11), QPointF(16, 15))

        return

    if action_type == "text":

        # Lettre « T » tracée au trait, sans dépendre d'une police
        painter.drawLine(QPointF(9, 10), QPointF(23, 10))
        painter.drawLine(QPointF(16, 10), QPointF(16, 23))

        return

    if action_type == "key":

        # Touche de clavier
        painter.drawRoundedRect(QRectF(7, 9, 18, 14), 4, 4)

        painter.drawLine(QPointF(12, 18), QPointF(20, 18))

        return

    if action_type == "condition":

        # Embranchement : un chemin qui se sépare en deux
        painter.drawLine(QPointF(16, 7), QPointF(16, 14))

        painter.drawLine(QPointF(16, 14), QPointF(10, 20))
        painter.drawLine(QPointF(16, 14), QPointF(22, 20))

        painter.setBrush(tint)

        painter.drawEllipse(QRectF(7.5, 20, 5, 5))
        painter.drawEllipse(QRectF(19.5, 20, 5, 5))

        painter.setBrush(Qt.BrushStyle.NoBrush)

        return

    if action_type == "loop":

        # Flèche circulaire
        painter.drawArc(QRectF(8, 8, 16, 16), 60 * 16, 280 * 16)

        head = QPainterPath()

        head.moveTo(20.5, 6.5)
        head.lineTo(24.5, 10.2)
        head.lineTo(19.2, 11.5)

        painter.drawPath(head)

        return

    # Type inconnu : simple point
    painter.setBrush(tint)

    painter.drawEllipse(QRectF(13, 13, 6, 6))

    painter.setBrush(Qt.BrushStyle.NoBrush)
