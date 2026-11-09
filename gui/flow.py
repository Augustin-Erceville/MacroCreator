"""Canevas de blocs : représentation visuelle d'une macro.

Les actions sont affichées comme une suite de cartes reliées verticalement.
Entre deux cartes, un bouton « + » insère une action exactement à cet
endroit. Les blocs qui en contiennent d'autres (boucles et conditions)
affichent leur contenu en retrait ; une condition montre ses deux branches
« Alors » et « Sinon ».

Chaque bloc connaît son chemin dans l'arbre (voir `core.macro`), ce qui
permet à la fenêtre principale de retrouver l'action correspondante et au
moteur d'exécution de mettre en évidence le bloc en cours.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import macro
from gui import theme

# Retrait appliqué au contenu d'un bloc conteneur
NESTING_INDENT = 26

# Hauteur du segment reliant deux blocs
CONNECTOR_HEIGHT = 38

ICON_DISPLAY_SIZE = 30


# La reconstruction du style après un changement de propriété vit dans le
# module de thème, qui sert aussi à la fenêtre principale.
repolish = theme.repolish_widget


# ==============================================================
# CONNECTEUR ENTRE DEUX BLOCS
# ==============================================================

class Connector(QWidget):
    """Trait vertical muni d'un bouton « + » d'insertion."""

    def __init__(self, canvas, branch_path, index, parent=None):

        super().__init__(parent)

        self.canvas = canvas
        self.branch_path = list(branch_path)
        self.index = index

        self.setFixedHeight(CONNECTOR_HEIGHT)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        self.button = QPushButton("+")

        self.button.setObjectName("node")

        self.button.setFixedSize(QSize(24, 24))

        self.button.setToolTip("Insérer une action ici")

        self.button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.button.clicked.connect(self._insert)

        layout.addWidget(self.button)

        layout.addStretch()

    def _insert(self):

        self.canvas.insert_requested.emit(self.branch_path, self.index)

    def paintEvent(self, event):

        painter = QPainter(self)

        # Trait teinté de la couleur d'accent, comme un câble reliant les
        # blocs : assez visible pour suivre l'enchaînement, assez discret
        # pour ne pas saturer un long canevas.
        line_color = QColor(theme.color("accent"))

        line_color.setAlpha(120)

        pen = QPen(line_color)

        pen.setWidth(2)

        painter.setPen(pen)

        middle = self.width() // 2

        painter.drawLine(middle, 0, middle, self.height())

        painter.end()


class Endpoint(QWidget):
    """Marqueur de début ou de fin de la macro."""

    def __init__(self, text, parent=None):

        super().__init__(parent)

        self.setFixedHeight(30)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        label = QLabel(text)

        label.setObjectName("endpoint")

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)

        layout.addStretch()


# ==============================================================
# COLONNE D'ACTIONS
# ==============================================================

class FlowColumn(QWidget):
    """Suite verticale de blocs correspondant à une liste d'actions."""

    def __init__(self, canvas, actions, branch_path, parent=None):

        super().__init__(parent)

        self.canvas = canvas

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        if not actions:

            layout.addWidget(Connector(canvas, branch_path, 0))

            empty = QLabel("Aucune action — cliquez sur « + »")

            empty.setObjectName("emptyFlow")

            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout.addWidget(empty)

            return

        for index, action in enumerate(actions):

            layout.addWidget(Connector(canvas, branch_path, index))

            block = BlockWidget(
                canvas,
                action,
                branch_path + [index],
            )

            layout.addWidget(block)

        layout.addWidget(
            Connector(canvas, branch_path, len(actions))
        )


# ==============================================================
# BLOC D'ACTION
# ==============================================================

class BlockWidget(QFrame):
    """Carte représentant une action, et son contenu éventuel."""

    def __init__(self, canvas, action, path, parent=None):

        super().__init__(parent)

        self.canvas = canvas
        self.action = action
        self.path = list(path)

        self.setObjectName("block")

        self.setProperty("selected", False)
        self.setProperty("running", False)

        canvas.register_block(self.path, self)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        action_type = action.get("type")

        if action_type == "loop":
            layout.addWidget(self._build_loop_body())

        elif action_type == "condition":
            layout.addWidget(self._build_condition_body())

    # ----------------------------------------------------------

    def _build_header(self):

        header = QWidget()

        header.setObjectName("blockHeader")

        layout = QHBoxLayout(header)

        layout.setContentsMargins(12, 10, 10, 10)

        layout.setSpacing(12)

        action_type = self.action.get("type")

        icon = QLabel()

        icon.setPixmap(
            theme.action_icon(action_type).pixmap(
                ICON_DISPLAY_SIZE, ICON_DISPLAY_SIZE
            )
        )

        icon.setFixedSize(ICON_DISPLAY_SIZE, ICON_DISPLAY_SIZE)

        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        texts = QVBoxLayout()

        texts.setContentsMargins(0, 0, 0, 0)

        texts.setSpacing(2)

        title = QLabel(
            macro.ACTION_LABELS.get(action_type, "Action")
        )

        title.setObjectName("blockTitle")

        subtitle = QLabel(macro.action_body(self.action))

        subtitle.setObjectName("blockSubtitle")

        subtitle.setWordWrap(True)

        texts.addWidget(title)
        texts.addWidget(subtitle)

        layout.addLayout(texts, 1)

        edit = QPushButton("Modifier")

        edit.setObjectName("blockAction")

        edit.setCursor(Qt.CursorShape.PointingHandCursor)

        edit.clicked.connect(
            lambda: self.canvas.edit_requested.emit(self.path)
        )

        layout.addWidget(edit, 0, Qt.AlignmentFlag.AlignTop)

        remove = QPushButton("✕")

        remove.setObjectName("blockRemove")

        remove.setFixedSize(QSize(28, 28))

        remove.setToolTip("Supprimer ce bloc")

        remove.setCursor(Qt.CursorShape.PointingHandCursor)

        remove.clicked.connect(
            lambda: self.canvas.delete_requested.emit(self.path)
        )

        layout.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)

        return header

    def _build_loop_body(self):

        body = QWidget()

        layout = QVBoxLayout(body)

        layout.setContentsMargins(NESTING_INDENT, 0, 12, 10)

        layout.setSpacing(0)

        layout.addWidget(
            FlowColumn(
                self.canvas,
                self.action.get("actions", []),
                self.path,
            )
        )

        return body

    def _build_condition_body(self):

        body = QWidget()

        layout = QVBoxLayout(body)

        layout.setContentsMargins(NESTING_INDENT, 0, 12, 10)

        layout.setSpacing(8)

        for branch in macro.BRANCHES:

            section = QFrame()

            section.setObjectName("branch")

            section.setProperty("branch", branch)

            section_layout = QVBoxLayout(section)

            section_layout.setContentsMargins(10, 8, 10, 10)

            section_layout.setSpacing(0)

            label = QLabel(macro.BRANCH_LABELS[branch].upper())

            label.setObjectName("branchLabel")

            label.setProperty("branch", branch)

            section_layout.addWidget(label)

            section_layout.addWidget(
                FlowColumn(
                    self.canvas,
                    self.action.get(branch, []),
                    self.path + [branch],
                )
            )

            layout.addWidget(section)

        return body

    # ----------------------------------------------------------

    def set_selected(self, selected):

        self.setProperty("selected", bool(selected))

        repolish(self)

    def set_running(self, running):

        self.setProperty("running", bool(running))

        repolish(self)

    def mousePressEvent(self, event):

        extend = bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        )

        self.canvas.select_path(self.path, extend=extend)

        event.accept()

    def mouseDoubleClickEvent(self, event):

        self.canvas.edit_requested.emit(self.path)

        event.accept()


# ==============================================================
# CANEVAS
# ==============================================================

class FlowCanvas(QScrollArea):
    """Zone défilante contenant toute la macro sous forme de blocs."""

    # (chemin de la liste visée, index d'insertion)
    insert_requested = Signal(list, int)

    # chemin de l'action concernée
    edit_requested = Signal(list)
    delete_requested = Signal(list)

    selection_changed = Signal()

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName("canvas")

        self.setWidgetResizable(True)

        self.setFrameShape(QFrame.Shape.NoFrame)

        self.actions = []

        self._blocks = {}

        # Sélection multiple : Ctrl+clic ajoute un bloc à la sélection.
        self._selected = []

        self._anchor = None

        self._running_path = None

        self._container = QWidget()

        self._container.setObjectName("canvasContent")

        self.setWidget(self._container)

        self._layout = QVBoxLayout(self._container)

        self._layout.setContentsMargins(24, 18, 24, 24)

        self._layout.setSpacing(0)

        self.rebuild()

    # ----------------------------------------------------------
    # CONSTRUCTION
    # ----------------------------------------------------------

    def set_actions(self, actions):

        self.actions = actions

        self.rebuild()

    def register_block(self, path, block):

        self._blocks[tuple(path)] = block

    def rebuild(self, keep_scroll=True):
        """Reconstruit entièrement les blocs à partir du modèle."""

        scroll = self.verticalScrollBar().value() if keep_scroll else 0

        self._blocks = {}

        while self._layout.count():

            item = self._layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self._layout.addWidget(Endpoint("DÉBUT"))

        self._layout.addWidget(FlowColumn(self, self.actions, []))

        self._layout.addWidget(Endpoint("FIN"))

        self._layout.addStretch()

        # La sélection et la mise en évidence survivent à la reconstruction.
        self._selected = [
            path
            for path in self._selected
            if tuple(path) in self._blocks
        ]

        for path in self._selected:
            self._blocks[tuple(path)].set_selected(True)

        if self._anchor is not None and tuple(self._anchor) not in self._blocks:
            self._anchor = None

        if self._running_path is not None:

            block = self._blocks.get(tuple(self._running_path))

            if block is not None:
                block.set_running(True)

        self.verticalScrollBar().setValue(scroll)

        self.selection_changed.emit()

    # ----------------------------------------------------------
    # SELECTION
    # ----------------------------------------------------------

    def select_path(self, path, extend=False):
        """Sélectionne un bloc ; `extend` ajoute à la sélection existante."""

        if path is None:

            for selected in self._selected:

                block = self._blocks.get(tuple(selected))

                if block is not None:
                    block.set_selected(False)

            self._selected = []

            self._anchor = None

            self.selection_changed.emit()

            return

        path = list(path)

        if not extend:

            for selected in self._selected:

                block = self._blocks.get(tuple(selected))

                if block is not None:
                    block.set_selected(False)

            self._selected = []

        if path in self._selected:

            # Ctrl+clic sur un bloc déjà sélectionné : on le retire.
            self._selected.remove(path)

            block = self._blocks.get(tuple(path))

            if block is not None:
                block.set_selected(False)

            if self._anchor == path:
                self._anchor = self._selected[-1] if self._selected else None

        else:

            self._selected.append(path)

            self._anchor = path

            block = self._blocks.get(tuple(path))

            if block is not None:
                block.set_selected(True)

        self.selection_changed.emit()

    def selected_path(self):
        """Dernier bloc cliqué, ou None."""

        if self._anchor is None:
            return None

        if tuple(self._anchor) not in self._blocks:
            return None

        return list(self._anchor)

    def selected_paths(self):
        """Tous les blocs sélectionnés, dans l'ordre de l'arbre."""

        return sorted(
            (list(path) for path in self._selected),
            key=lambda path: [
                (1, token) if isinstance(token, str) else (0, token)
                for token in path
            ],
        )

    def clear_selection(self):

        self.select_path(None)

    def mousePressEvent(self, event):
        """Un clic dans le vide désélectionne."""

        self.clear_selection()

        super().mousePressEvent(event)

    # ----------------------------------------------------------
    # EXECUTION
    # ----------------------------------------------------------

    def set_running_path(self, path):
        """Met en évidence le bloc en cours d'exécution."""

        previous = self._blocks.get(tuple(self._running_path or ()))

        if previous is not None:
            previous.set_running(False)

        self._running_path = list(path) if path is not None else None

        if self._running_path is None:
            return

        block = self._blocks.get(tuple(self._running_path))

        if block is None:
            return

        block.set_running(True)

        self.ensureWidgetVisible(block, 0, 60)

    def clear_running(self):

        self.set_running_path(None)
