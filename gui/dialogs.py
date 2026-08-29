"""Boîtes de dialogue de création et de modification d'actions.

Chaque dialogue sert à la fois à l'ajout et à la modification : il suffit de
lui passer une action existante. `ActionDialog.run()` retourne l'action
créée, ou None si l'utilisateur annule.
"""

import pyautogui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core import macro
from core.recorder import STOP_KEY_NAME as RECORD_STOP_KEY
from core.recorder import Recorder

# Marge autorisée autour de l'écran pour les coordonnées
COORDINATE_LIMIT = 20000


# ==============================================================
# CAPTURE DE POSITION
# ==============================================================

class MousePositionDialog(QDialog):
    """Affiche la position de la souris en direct ; F8 la capture."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.selected_x = None
        self.selected_y = None

        self.setWindowTitle("Sélection de position souris")

        self.setFixedSize(450, 260)

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setup_ui()

        self.timer = QTimer(self)

        self.timer.timeout.connect(self.update_mouse_position)

        self.timer.start(30)

    def setup_ui(self):

        layout = QVBoxLayout(self)

        title = QLabel("Sélection de la position de la souris")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        layout.addWidget(title)

        instruction = QLabel(
            "Déplacez votre souris sur l'élément souhaité.\n"
            "Appuyez ensuite sur F8."
        )

        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(instruction)

        self.position_label = QLabel("X : 0     Y : 0")

        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.position_label.setStyleSheet(
            "font-size: 26px; font-weight: bold; padding: 15px;"
        )

        layout.addWidget(self.position_label)

        self.status_label = QLabel("En attente de F8...")

        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.status_label)

        cancel_button = QPushButton("Annuler")

        cancel_button.clicked.connect(self.reject)

        layout.addWidget(cancel_button)

    def update_mouse_position(self):

        try:
            x, y = pyautogui.position()

        except Exception:  # noqa: BLE001 - position momentanément illisible
            return

        self.position_label.setText(f"X : {x}     Y : {y}")

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_F8:

            x, y = pyautogui.position()

            self.selected_x = int(x)
            self.selected_y = int(y)

            self.status_label.setText(
                f"Position capturée : X {self.selected_x} | "
                f"Y {self.selected_y}"
            )

            self.status_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )

            self.timer.stop()

            QApplication.processEvents()

            self.accept()

            return

        if event.key() == Qt.Key.Key_Escape:

            self.reject()

            return

        super().keyPressEvent(event)

    def closeEvent(self, event):

        self.timer.stop()

        event.accept()


def capture_position(parent):
    """Ouvre la capture F8 et retourne (x, y) ou None."""

    dialog = MousePositionDialog(parent)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    if dialog.selected_x is None or dialog.selected_y is None:
        return None

    return dialog.selected_x, dialog.selected_y


class CoordinateGroup(QGroupBox):
    """Deux champs X / Y accompagnés du bouton de capture F8."""

    def __init__(self, title, parent_dialog, x=0, y=0):

        super().__init__(title)

        self._parent_dialog = parent_dialog

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.x_input = QSpinBox()
        self.y_input = QSpinBox()

        for widget, value in (
            (self.x_input, x),
            (self.y_input, y),
        ):
            widget.setRange(-COORDINATE_LIMIT, COORDINATE_LIMIT)
            widget.setValue(int(value))

        form.addRow("X :", self.x_input)
        form.addRow("Y :", self.y_input)

        layout.addLayout(form)

        capture_button = QPushButton(
            "📍 Placer la souris puis appuyer sur F8"
        )

        capture_button.clicked.connect(self._capture)

        layout.addWidget(capture_button)

    def _capture(self):

        position = capture_position(self._parent_dialog)

        if position is None:
            return

        self.x_input.setValue(position[0])
        self.y_input.setValue(position[1])

    @property
    def x(self):
        return int(self.x_input.value())

    @property
    def y(self):
        return int(self.y_input.value())


# ==============================================================
# BASE DES DIALOGUES D'ACTION
# ==============================================================

class ActionDialog(QDialog):
    """Squelette commun : contenu + boutons Annuler / Valider."""

    title = "Action"
    width = 450

    def __init__(self, parent=None, action=None):

        super().__init__(parent)

        self.action = action

        self.result_action = None

        self.setWindowTitle(self.title)

        self.setMinimumWidth(self.width)

        self.layout = QVBoxLayout(self)

        self.build(action)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("Valider" if action else "Ajouter")

        self.buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Annuler")

        self.buttons.accepted.connect(self._validate)
        self.buttons.rejected.connect(self.reject)

        self.layout.addWidget(self.buttons)

    # À redéfinir dans les sous-classes
    def build(self, action):
        raise NotImplementedError

    def make_action(self):
        raise NotImplementedError

    def _validate(self):

        try:
            action = self.make_action()

        except ValueError as error:

            QMessageBox.warning(self, self.title, str(error))

            return

        if action is None:
            return

        self.result_action = action

        self.accept()

    @classmethod
    def run(cls, parent, action=None):
        """Ouvre le dialogue et retourne l'action, ou None."""

        dialog = cls(parent, action)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        return dialog.result_action


# ==============================================================
# ATTENTE
# ==============================================================

class WaitDialog(ActionDialog):

    title = "Temps d'attente"

    def build(self, action):

        form = QFormLayout()

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(0.01, 3600.0)
        self.duration_input.setDecimals(2)
        self.duration_input.setSingleStep(0.1)
        self.duration_input.setSuffix(" seconde(s)")
        self.duration_input.setValue(
            action["duration"] if action else 1.0
        )

        self.random_check = QCheckBox(
            "Durée aléatoire (utile pour paraître plus naturel)"
        )

        self.maximum_input = QDoubleSpinBox()
        self.maximum_input.setRange(0.01, 3600.0)
        self.maximum_input.setDecimals(2)
        self.maximum_input.setSingleStep(0.1)
        self.maximum_input.setSuffix(" seconde(s)")
        self.maximum_input.setValue(
            action.get("duration_max") or 2.0 if action else 2.0
        )

        has_random = bool(action and action.get("duration_max"))

        self.random_check.setChecked(has_random)
        self.maximum_input.setEnabled(has_random)

        self.random_check.toggled.connect(self.maximum_input.setEnabled)

        form.addRow("Durée minimale :", self.duration_input)

        self.layout.addLayout(form)

        self.layout.addWidget(self.random_check)

        maximum_form = QFormLayout()

        maximum_form.addRow("Durée maximale :", self.maximum_input)

        self.layout.addLayout(maximum_form)

    def make_action(self):

        duration = self.duration_input.value()

        if not self.random_check.isChecked():
            return macro.make_wait(duration)

        maximum = self.maximum_input.value()

        if maximum < duration:
            raise ValueError(
                "La durée maximale doit être supérieure à la durée "
                "minimale."
            )

        return macro.make_wait(duration, maximum)


# ==============================================================
# MOUVEMENT
# ==============================================================

class MoveDialog(ActionDialog):

    title = "Mouvement de souris"

    def build(self, action):

        self.coordinates = CoordinateGroup(
            "Position de la souris",
            self,
            action["x"] if action else 0,
            action["y"] if action else 0,
        )

        self.layout.addWidget(self.coordinates)

        form = QFormLayout()

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(0.0, 60.0)
        self.duration_input.setSingleStep(0.1)
        self.duration_input.setSuffix(" seconde(s)")
        self.duration_input.setValue(
            action["duration"] if action else 0.5
        )

        form.addRow("Durée du déplacement :", self.duration_input)

        self.layout.addLayout(form)

    def make_action(self):

        return macro.make_move(
            self.coordinates.x,
            self.coordinates.y,
            self.duration_input.value(),
        )


# ==============================================================
# CLIC
# ==============================================================

def _button_combo(selected="left"):

    combo = QComboBox()

    combo.addItem("Gauche", "left")
    combo.addItem("Droit", "right")
    combo.addItem("Milieu", "middle")

    index = combo.findData(selected)

    if index >= 0:
        combo.setCurrentIndex(index)

    return combo


class ClickDialog(ActionDialog):

    title = "Clic souris"

    def build(self, action):

        self.coordinates = CoordinateGroup(
            "Position du clic",
            self,
            action["x"] if action else 0,
            action["y"] if action else 0,
        )

        self.layout.addWidget(self.coordinates)

        form = QFormLayout()

        self.button_input = _button_combo(
            action["button"] if action else "left"
        )

        self.clicks_input = QComboBox()
        self.clicks_input.addItem("Simple clic", 1)
        self.clicks_input.addItem("Double clic", 2)
        self.clicks_input.addItem("Triple clic", 3)

        if action:

            index = self.clicks_input.findData(action["clicks"])

            if index >= 0:
                self.clicks_input.setCurrentIndex(index)

        form.addRow("Bouton :", self.button_input)
        form.addRow("Type :", self.clicks_input)

        self.layout.addLayout(form)

    def make_action(self):

        return macro.make_click(
            self.coordinates.x,
            self.coordinates.y,
            self.button_input.currentData(),
            self.clicks_input.currentData(),
        )


# ==============================================================
# GLISSER-DEPOSER
# ==============================================================

class DragDialog(ActionDialog):

    title = "Glisser-déposer"

    def build(self, action):

        self.start = CoordinateGroup(
            "Point de départ",
            self,
            action["x"] if action else 0,
            action["y"] if action else 0,
        )

        self.end = CoordinateGroup(
            "Point d'arrivée",
            self,
            action["x2"] if action else 0,
            action["y2"] if action else 0,
        )

        self.layout.addWidget(self.start)
        self.layout.addWidget(self.end)

        form = QFormLayout()

        self.button_input = _button_combo(
            action["button"] if action else "left"
        )

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(0.0, 60.0)
        self.duration_input.setSingleStep(0.1)
        self.duration_input.setSuffix(" seconde(s)")
        self.duration_input.setValue(
            action["duration"] if action else 0.5
        )

        form.addRow("Bouton :", self.button_input)
        form.addRow("Durée du glissement :", self.duration_input)

        self.layout.addLayout(form)

    def make_action(self):

        return macro.make_drag(
            self.start.x,
            self.start.y,
            self.end.x,
            self.end.y,
            self.button_input.currentData(),
            self.duration_input.value(),
        )


# ==============================================================
# MOLETTE
# ==============================================================

class ScrollDialog(ActionDialog):

    title = "Molette de souris"

    def build(self, action):

        form = QFormLayout()

        self.direction_input = QComboBox()
        self.direction_input.addItem("Vers le haut", 1)
        self.direction_input.addItem("Vers le bas", -1)

        if action and action["amount"] < 0:
            self.direction_input.setCurrentIndex(1)

        self.amount_input = QSpinBox()
        self.amount_input.setRange(1, 100)
        self.amount_input.setValue(
            abs(action["amount"]) if action else 3
        )

        form.addRow("Direction :", self.direction_input)
        form.addRow("Nombre de crans :", self.amount_input)

        self.layout.addLayout(form)

        self.position_check = QCheckBox(
            "Positionner la souris avant de faire défiler"
        )

        has_position = bool(action and "x" in action)

        self.position_check.setChecked(has_position)

        self.layout.addWidget(self.position_check)

        self.coordinates = CoordinateGroup(
            "Position de la souris",
            self,
            action.get("x", 0) if action else 0,
            action.get("y", 0) if action else 0,
        )

        self.coordinates.setEnabled(has_position)

        self.position_check.toggled.connect(self.coordinates.setEnabled)

        self.layout.addWidget(self.coordinates)

    def make_action(self):

        amount = (
            self.amount_input.value()
            * self.direction_input.currentData()
        )

        if not self.position_check.isChecked():
            return macro.make_scroll(amount)

        return macro.make_scroll(
            amount,
            self.coordinates.x,
            self.coordinates.y,
        )


# ==============================================================
# TEXTE
# ==============================================================

class TextDialog(ActionDialog):

    title = "Inscription de texte"
    width = 520

    def build(self, action):

        self.layout.addWidget(QLabel("Texte à inscrire :"))

        self.text_input = QTextEdit()

        self.text_input.setPlaceholderText("Écrivez ici le texte...")

        if action:
            self.text_input.setPlainText(action["text"])

        self.text_input.setMinimumHeight(180)

        self.layout.addWidget(self.text_input)

        form = QFormLayout()

        self.interval_input = QDoubleSpinBox()
        self.interval_input.setRange(0.0, 2.0)
        self.interval_input.setDecimals(3)
        self.interval_input.setSingleStep(0.01)
        self.interval_input.setSuffix(" seconde(s)")
        self.interval_input.setValue(
            action.get("interval", 0.01) if action else 0.01
        )

        form.addRow("Délai entre les caractères :", self.interval_input)

        self.layout.addLayout(form)

        note = QLabel(
            "Note : la frappe simulée ne gère que les caractères présents "
            "sur la disposition clavier active."
        )

        note.setWordWrap(True)

        note.setStyleSheet("color: gray;")

        self.layout.addWidget(note)

    def make_action(self):

        text = self.text_input.toPlainText()

        if not text:
            raise ValueError("Veuillez saisir du texte.")

        return macro.make_text(text, self.interval_input.value())


# ==============================================================
# TOUCHE
# ==============================================================

class KeyDialog(ActionDialog):

    title = "Appui de touche"

    def build(self, action):

        form = QFormLayout()

        self.key_input = QComboBox()

        for name, value in macro.get_keys():
            self.key_input.addItem(name, value)

        if action:

            index = self.key_input.findData(action["key"])

            if index >= 0:
                self.key_input.setCurrentIndex(index)

        form.addRow("Touche :", self.key_input)

        self.layout.addLayout(form)

        modifiers_group = QGroupBox("Modificateurs")

        modifiers_layout = QHBoxLayout(modifiers_group)

        existing = set(action.get("modifiers", [])) if action else set()

        self.modifier_checks = {}

        for modifier, label in (
            ("ctrl", "CTRL"),
            ("shift", "SHIFT"),
            ("alt", "ALT"),
            ("win", "Windows"),
        ):

            check = QCheckBox(label)

            check.setChecked(modifier in existing)

            modifiers_layout.addWidget(check)

            self.modifier_checks[modifier] = check

        self.layout.addWidget(modifiers_group)

        example = QLabel("Exemple : CTRL coché + touche C = CTRL + C")

        example.setStyleSheet("color: gray; padding: 8px;")

        self.layout.addWidget(example)

    def make_action(self):

        modifiers = [
            modifier
            for modifier, check in self.modifier_checks.items()
            if check.isChecked()
        ]

        return macro.make_key(self.key_input.currentData(), modifiers)


# ==============================================================
# BOUCLE
# ==============================================================

class LoopDialog(ActionDialog):

    title = "Boucle"

    def build(self, action):

        form = QFormLayout()

        self.repetitions_input = QSpinBox()
        self.repetitions_input.setRange(1, macro.MAX_REPETITIONS)
        self.repetitions_input.setValue(
            action["repetitions"] if action else 2
        )

        form.addRow("Nombre de répétitions :", self.repetitions_input)

        self.layout.addLayout(form)

        hint = QLabel(
            "Une boucle vide peut être créée puis remplie : sélectionnez-la "
            "dans la liste, les actions ajoutées iront à l'intérieur."
        )

        hint.setWordWrap(True)

        hint.setStyleSheet("color: gray;")

        self.layout.addWidget(hint)

    def make_action(self):

        repetitions = self.repetitions_input.value()

        if self.action is not None:

            updated = dict(self.action)

            updated["repetitions"] = repetitions

            return updated

        return macro.make_loop(repetitions)


# ==============================================================
# ENREGISTREMENT
# ==============================================================

class RecorderDialog(QDialog):
    """Enregistre les gestes de l'utilisateur et les convertit en actions."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("Enregistrer une macro")

        self.resize(560, 420)

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.recorded_actions = []

        self.recorder = None

        layout = QVBoxLayout(self)

        title = QLabel("Enregistrement des actions")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        layout.addWidget(title)

        self.instruction = QLabel(
            "Cliquez sur « Démarrer », effectuez vos actions, puis appuyez "
            f"sur {RECORD_STOP_KEY} pour arrêter l'enregistrement.\n"
            "Les clics, la molette, la frappe et les délais réels sont "
            "capturés."
        )

        self.instruction.setWordWrap(True)

        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.instruction)

        self.moves_check = QCheckBox(
            "Enregistrer aussi les mouvements de souris "
            "(génère beaucoup d'actions)"
        )

        layout.addWidget(self.moves_check)

        self.event_list = QListWidget()

        layout.addWidget(self.event_list)

        self.status_label = QLabel("Prêt à enregistrer.")

        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()

        self.start_button = QPushButton("● Démarrer")
        self.stop_button = QPushButton("■ Arrêter")
        self.cancel_button = QPushButton("Annuler")
        self.accept_button = QPushButton("Ajouter à la macro")

        self.stop_button.setEnabled(False)
        self.accept_button.setEnabled(False)

        for widget in (
            self.start_button,
            self.stop_button,
            self.cancel_button,
            self.accept_button,
        ):
            buttons.addWidget(widget)

        layout.addLayout(buttons)

        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.cancel_button.clicked.connect(self.reject)
        self.accept_button.clicked.connect(self.accept)

    # ----------------------------------------------------------

    def start_recording(self):

        self.recorder = Recorder(
            record_moves=self.moves_check.isChecked(),
            parent=self,
        )

        if not self.recorder.available:

            QMessageBox.warning(
                self,
                "Enregistrement",
                "La bibliothèque pynput n'est pas disponible : "
                "l'enregistrement est impossible.\n\n"
                "Installez les dépendances avec :\n"
                "pip install -r requirements.txt"
            )

            return

        self.recorder.action_added.connect(self._on_action_added)
        self.recorder.stopped.connect(self._on_recorder_stopped)

        self.event_list.clear()

        if not self.recorder.start():

            QMessageBox.warning(
                self,
                "Enregistrement",
                "Le système a refusé l'écoute du clavier et de la souris."
            )

            return

        self.start_button.setEnabled(False)
        self.moves_check.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.accept_button.setEnabled(False)

        self.status_label.setText(
            f"Enregistrement en cours... ({RECORD_STOP_KEY} pour arrêter)"
        )

    def stop_recording(self):

        if self.recorder is not None and self.recorder.running:
            self.recorder.stop()

    def _on_action_added(self, description):

        self.event_list.addItem(description)

        self.event_list.scrollToBottom()

    def _on_recorder_stopped(self):

        self.recorded_actions = list(self.recorder.actions)

        self.start_button.setEnabled(True)
        self.moves_check.setEnabled(True)
        self.stop_button.setEnabled(False)

        self.accept_button.setEnabled(bool(self.recorded_actions))

        self.status_label.setText(
            f"Enregistrement terminé : "
            f"{len(self.recorded_actions)} action(s)."
        )

    def closeEvent(self, event):

        self.stop_recording()

        event.accept()

    @classmethod
    def run(cls, parent):
        """Retourne la liste d'actions enregistrées, ou None."""

        dialog = cls(parent)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        return dialog.recorded_actions or None


# ==============================================================
# DIALOGUES UTILITAIRES
# ==============================================================

def ask_macro_name(parent, current=""):
    """Demande un nom de macro. Retourne le nom ou None."""

    dialog = QDialog(parent)

    dialog.setWindowTitle("Nom de la macro")

    dialog.setMinimumWidth(400)

    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Nom de la macro :"))

    name_input = QLineEdit(current)

    layout.addWidget(name_input)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok
        | QDialogButtonBox.StandardButton.Cancel
    )

    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    name = name_input.text().strip()

    return name or None


# Association type d'action -> dialogue
ACTION_DIALOGS = {
    "wait": WaitDialog,
    "move": MoveDialog,
    "click": ClickDialog,
    "drag": DragDialog,
    "scroll": ScrollDialog,
    "text": TextDialog,
    "key": KeyDialog,
    "loop": LoopDialog,
}
