import sys
import time
import threading
import copy
import pyautogui

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QInputDialog,
    QDoubleSpinBox,
    QDialog,
    QSpinBox,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject


# ==============================================================
# WORKER D'EXECUTION
# ==============================================================

class MacroWorker(QObject):

    finished = Signal()
    status = Signal(str)

    def __init__(self, actions):

        super().__init__()

        self.actions = actions
        self.stop_requested = False

    def stop(self):

        self.stop_requested = True

    def run(self):

        try:

            self.execute_actions(
                self.actions
            )

        except Exception as e:

            self.status.emit(
                f"Erreur : {e}"
            )

        finally:

            self.finished.emit()

    def execute_actions(self, actions):

        for action in actions:

            if self.stop_requested:
                return

            self.execute_action(
                action
            )

    def execute_action(self, action):

        action_type = action["type"]

        # ------------------------------------------------------
        # ATTENTE
        # ------------------------------------------------------

        if action_type == "wait":

            self.interruptible_sleep(
                action["duration"]
            )

        # ------------------------------------------------------
        # MOUVEMENT SOURIS
        # ------------------------------------------------------

        elif action_type == "move":

            self.status.emit(
                f"Souris → X:{action['x']} Y:{action['y']}"
            )

            pyautogui.moveTo(
                action["x"],
                action["y"],
                duration=action["duration"]
            )

        # ------------------------------------------------------
        # CLIC
        # ------------------------------------------------------

        elif action_type == "click":

            self.status.emit(
                f"Clic → X:{action['x']} Y:{action['y']}"
            )

            pyautogui.click(
                x=action["x"],
                y=action["y"],
                clicks=action["clicks"],
                button=action["button"],
                interval=0.1
            )

        # ------------------------------------------------------
        # TEXTE
        # ------------------------------------------------------

        elif action_type == "text":

            self.status.emit(
                "Saisie du texte..."
            )

            pyautogui.write(
                action["text"],
                interval=0.01
            )

        # ------------------------------------------------------
        # TOUCHE
        # ------------------------------------------------------

        elif action_type == "key":

            self.status.emit(
                f"Touche → {action['key']}"
            )

            self.press_key(
                action
            )

        # ------------------------------------------------------
        # BOUCLE
        # ------------------------------------------------------

        elif action_type == "loop":

            repetitions = action["repetitions"]

            for i in range(repetitions):

                if self.stop_requested:
                    return

                self.status.emit(
                    f"Boucle : {i + 1}/{repetitions}"
                )

                self.execute_actions(
                    action["actions"]
                )

    def press_key(self, action):

        key = action["key"]

        modifiers = action.get(
            "modifiers",
            []
        )

        for modifier in modifiers:

            pyautogui.keyDown(
                modifier
            )

        try:

            pyautogui.press(
                key
            )

        finally:

            for modifier in reversed(
                modifiers
            ):

                pyautogui.keyUp(
                    modifier
                )

    def interruptible_sleep(self, duration):

        end_time = time.time() + duration

        while time.time() < end_time:

            if self.stop_requested:
                return

            remaining = (
                end_time - time.time()
            )

            time.sleep(
                min(
                    0.05,
                    remaining
                )
            )


# ==============================================================
# FENETRE DE CAPTURE DE POSITION
# ==============================================================

class MousePositionDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.selected_x = None
        self.selected_y = None

        self.setWindowTitle(
            "Sélection de position souris"
        )

        self.setFixedSize(
            450,
            260
        )

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setup_ui()

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.update_mouse_position
        )

        self.timer.start(30)

    def setup_ui(self):

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "Sélection de la position de la souris"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """)

        layout.addWidget(
            title
        )

        instruction = QLabel(
            "Déplacez votre souris sur l'élément souhaité.\n"
            "Appuyez ensuite sur F8."
        )

        instruction.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            instruction
        )

        self.position_label = QLabel(
            "X : 0     Y : 0"
        )

        self.position_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.position_label.setStyleSheet("""
            QLabel {
                font-size: 26px;
                font-weight: bold;
                padding: 15px;
            }
        """)

        layout.addWidget(
            self.position_label
        )

        self.status_label = QLabel(
            "En attente de F8..."
        )

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.status_label
        )

        cancel_button = QPushButton(
            "Annuler"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        layout.addWidget(
            cancel_button
        )

    def update_mouse_position(self):

        try:

            x, y = pyautogui.position()

            self.position_label.setText(
                f"X : {x}     Y : {y}"
            )

        except Exception:
            pass

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_F8:

            x, y = pyautogui.position()

            self.selected_x = int(x)
            self.selected_y = int(y)

            self.status_label.setText(
                f"Position capturée : "
                f"X {self.selected_x} | "
                f"Y {self.selected_y}"
            )

            self.status_label.setStyleSheet("""
                QLabel {
                    color: green;
                    font-weight: bold;
                }
            """)

            self.timer.stop()

            QApplication.processEvents()

            self.accept()

            return

        if event.key() == Qt.Key.Key_Escape:

            self.reject()

            return

        super().keyPressEvent(
            event
        )

    def closeEvent(self, event):

        self.timer.stop()

        event.accept()


# ==============================================================
# FENETRE PRINCIPALE
# ==============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Macro Creator"
        )

        self.resize(
            1100,
            750
        )

        # Liste des actions
        self.actions = []

        # Action copiée
        self.copied_action = None

        # Exécution
        self.worker = None
        self.worker_thread = None
        self.is_running = False

        self.setup_ui()
        self.connect_signals()

    # ==========================================================
    # INTERFACE
    # ==========================================================

    def setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(
            central_widget
        )

        main_layout = QVBoxLayout(
            central_widget
        )

        # ======================================================
        # TITRE
        # ======================================================

        title = QLabel(
            "MACRO CREATOR"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)

        main_layout.addWidget(
            title
        )

        # ======================================================
        # CONTENU
        # ======================================================

        content_layout = QHBoxLayout()

        # ======================================================
        # ACTIONS
        # ======================================================

        actions_group = QGroupBox(
            "Ajouter une action"
        )

        actions_layout = QVBoxLayout()

        self.btn_wait = QPushButton(
            "⏱ Temps d'attente"
        )

        self.btn_move = QPushButton(
            "🖱 Mouvement souris"
        )

        self.btn_click = QPushButton(
            "🖱 Clic souris"
        )

        self.btn_text = QPushButton(
            "⌨ Inscription de texte"
        )

        self.btn_key = QPushButton(
            "⌨ Appui de touche"
        )

        self.btn_loop = QPushButton(
            "🔁 Boucle"
        )

        actions_layout.addWidget(
            self.btn_wait
        )

        actions_layout.addWidget(
            self.btn_move
        )

        actions_layout.addWidget(
            self.btn_click
        )

        actions_layout.addWidget(
            self.btn_text
        )

        actions_layout.addWidget(
            self.btn_key
        )

        actions_layout.addWidget(
            self.btn_loop
        )

        actions_layout.addStretch()

        actions_group.setLayout(
            actions_layout
        )

        content_layout.addWidget(
            actions_group,
            1
        )

        # ======================================================
        # LISTE
        # ======================================================

        macro_group = QGroupBox(
            "Actions de la macro"
        )

        macro_layout = QVBoxLayout()

        self.macro_list = QListWidget()

        macro_layout.addWidget(
            self.macro_list
        )

        # ======================================================
        # GESTION DES ACTIONS
        # ======================================================

        management_layout = QHBoxLayout()

        self.btn_up = QPushButton(
            "↑ Monter"
        )

        self.btn_down = QPushButton(
            "↓ Descendre"
        )

        self.btn_edit = QPushButton(
            "Modifier"
        )

        self.btn_delete = QPushButton(
            "Supprimer"
        )

        self.btn_copy = QPushButton(
            "Copier"
        )

        self.btn_paste = QPushButton(
            "Coller"
        )

        management_layout.addWidget(
            self.btn_up
        )

        management_layout.addWidget(
            self.btn_down
        )

        management_layout.addWidget(
            self.btn_edit
        )

        management_layout.addWidget(
            self.btn_delete
        )

        management_layout.addWidget(
            self.btn_copy
        )

        management_layout.addWidget(
            self.btn_paste
        )

        macro_layout.addLayout(
            management_layout
        )

        macro_group.setLayout(
            macro_layout
        )

        content_layout.addWidget(
            macro_group,
            3
        )

        main_layout.addLayout(
            content_layout
        )

        # ======================================================
        # NOM
        # ======================================================

        name_layout = QHBoxLayout()

        name_layout.addWidget(
            QLabel(
                "Nom de la macro :"
            )
        )

        self.macro_name = QLineEdit(
            "Ma première macro"
        )

        name_layout.addWidget(
            self.macro_name
        )

        main_layout.addLayout(
            name_layout
        )

        # ======================================================
        # BAS
        # ======================================================

        bottom_layout = QHBoxLayout()

        self.btn_new = QPushButton(
            "Nouveau"
        )

        self.btn_save = QPushButton(
            "Enregistrer"
        )

        self.btn_load = QPushButton(
            "Charger"
        )

        self.btn_execute = QPushButton(
            "▶ Exécuter"
        )

        self.btn_status = QLabel(
            "Prêt"
        )

        bottom_layout.addWidget(
            self.btn_new
        )

        bottom_layout.addWidget(
            self.btn_save
        )

        bottom_layout.addWidget(
            self.btn_load
        )

        bottom_layout.addWidget(
            self.btn_status
        )

        bottom_layout.addStretch()

        bottom_layout.addWidget(
            self.btn_execute
        )

        main_layout.addLayout(
            bottom_layout
        )

    # ==========================================================
    # CONNEXIONS
    # ==========================================================

    def connect_signals(self):

        self.btn_wait.clicked.connect(
            self.add_wait_action
        )

        self.btn_move.clicked.connect(
            self.add_move_action
        )

        self.btn_click.clicked.connect(
            self.add_click_action
        )

        self.btn_text.clicked.connect(
            self.add_text_action
        )

        self.btn_key.clicked.connect(
            self.add_key_action
        )

        self.btn_loop.clicked.connect(
            self.add_loop_action
        )

        self.btn_up.clicked.connect(
            self.move_action_up
        )

        self.btn_down.clicked.connect(
            self.move_action_down
        )

        self.btn_edit.clicked.connect(
            self.edit_selected_action
        )

        self.btn_delete.clicked.connect(
            self.delete_selected_action
        )

        self.btn_copy.clicked.connect(
            self.copy_selected_action
        )

        self.btn_paste.clicked.connect(
            self.paste_action
        )

        self.btn_execute.clicked.connect(
            self.execute_macro
        )

    # ==========================================================
    # POSITION SOURIS
    # ==========================================================

    def select_mouse_position(self):

        dialog = MousePositionDialog(
            self
        )

        result = dialog.exec()

        if result != QDialog.DialogCode.Accepted:
            return None

        if (
            dialog.selected_x is None
            or
            dialog.selected_y is None
        ):
            return None

        return {
            "x": dialog.selected_x,
            "y": dialog.selected_y
        }

    # ==========================================================
    # ATTENTE
    # ==========================================================

    def add_wait_action(self):

        duration, ok = QInputDialog.getDouble(
            self,
            "Temps d'attente",
            "Durée de l'attente (secondes) :",
            1.0,
            0.01,
            3600.0,
            2
        )

        if not ok:
            return

        self.actions.append({
            "type": "wait",
            "duration": duration
        })

        self.refresh_action_list()

    # ==========================================================
    # MOUVEMENT SOURIS
    # ==========================================================

    def add_move_action(self):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Mouvement de souris"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        coordinates_group = QGroupBox(
            "Position de la souris"
        )

        coordinates_layout = QFormLayout()

        x_input = QSpinBox()

        x_input.setRange(
            -10000,
            10000
        )

        y_input = QSpinBox()

        y_input.setRange(
            -10000,
            10000
        )

        coordinates_layout.addRow(
            "X :",
            x_input
        )

        coordinates_layout.addRow(
            "Y :",
            y_input
        )

        coordinates_group.setLayout(
            coordinates_layout
        )

        layout.addWidget(
            coordinates_group
        )

        capture_button = QPushButton(
            "📍 Placer la souris puis appuyer sur F8"
        )

        layout.addWidget(
            capture_button
        )

        duration_input = QDoubleSpinBox()

        duration_input.setRange(
            0.0,
            60.0
        )

        duration_input.setSingleStep(
            0.1
        )

        duration_input.setValue(
            0.5
        )

        duration_input.setSuffix(
            " seconde(s)"
        )

        layout.addWidget(
            QLabel(
                "Durée du déplacement :"
            )
        )

        layout.addWidget(
            duration_input
        )

        def capture_position():

            result = self.select_mouse_position()

            if result is None:
                return

            x_input.setValue(
                result["x"]
            )

            y_input.setValue(
                result["y"]
            )

        capture_button.clicked.connect(
            capture_position
        )

        buttons = QHBoxLayout()

        cancel_button = QPushButton(
            "Annuler"
        )

        add_button = QPushButton(
            "Ajouter"
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            add_button
        )

        layout.addLayout(
            buttons
        )

        cancel_button.clicked.connect(
            dialog.reject
        )

        def add_action():

            self.actions.append({
                "type": "move",
                "x": int(
                    x_input.value()
                ),
                "y": int(
                    y_input.value()
                ),
                "duration": float(
                    duration_input.value()
                )
            })

            self.refresh_action_list()

            dialog.accept()

        add_button.clicked.connect(
            add_action
        )

        dialog.exec()

    # ==========================================================
    # CLIC SOURIS
    # ==========================================================

    def add_click_action(self):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Clic souris"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        coordinates_group = QGroupBox(
            "Position du clic"
        )

        coordinates_layout = QFormLayout()

        x_input = QSpinBox()

        x_input.setRange(
            -10000,
            10000
        )

        y_input = QSpinBox()

        y_input.setRange(
            -10000,
            10000
        )

        coordinates_layout.addRow(
            "X :",
            x_input
        )

        coordinates_layout.addRow(
            "Y :",
            y_input
        )

        coordinates_group.setLayout(
            coordinates_layout
        )

        layout.addWidget(
            coordinates_group
        )

        capture_button = QPushButton(
            "📍 Placer la souris puis appuyer sur F8"
        )

        layout.addWidget(
            capture_button
        )

        def capture_position():

            result = self.select_mouse_position()

            if result is None:
                return

            x_input.setValue(
                result["x"]
            )

            y_input.setValue(
                result["y"]
            )

        capture_button.clicked.connect(
            capture_position
        )

        form = QFormLayout()

        button_input = QComboBox()

        button_input.addItem(
            "Gauche",
            "left"
        )

        button_input.addItem(
            "Droit",
            "right"
        )

        button_input.addItem(
            "Milieu",
            "middle"
        )

        click_input = QComboBox()

        click_input.addItem(
            "Simple clic",
            1
        )

        click_input.addItem(
            "Double clic",
            2
        )

        form.addRow(
            "Bouton :",
            button_input
        )

        form.addRow(
            "Type :",
            click_input
        )

        layout.addLayout(
            form
        )

        buttons = QHBoxLayout()

        cancel_button = QPushButton(
            "Annuler"
        )

        add_button = QPushButton(
            "Ajouter"
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            add_button
        )

        layout.addLayout(
            buttons
        )

        cancel_button.clicked.connect(
            dialog.reject
        )

        def add_action():

            self.actions.append({
                "type": "click",
                "x": int(
                    x_input.value()
                ),
                "y": int(
                    y_input.value()
                ),
                "button": button_input.currentData(),
                "clicks": click_input.currentData()
            })

            self.refresh_action_list()

            dialog.accept()

        add_button.clicked.connect(
            add_action
        )

        dialog.exec()

    # ==========================================================
    # TEXTE
    # ==========================================================

    def add_text_action(self):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Inscription de texte"
        )

        dialog.resize(
            500,
            300
        )

        layout = QVBoxLayout(
            dialog
        )

        layout.addWidget(
            QLabel(
                "Texte à inscrire :"
            )
        )

        text_input = QTextEdit()

        text_input.setPlaceholderText(
            "Écrivez ici le texte..."
        )

        layout.addWidget(
            text_input
        )

        buttons = QHBoxLayout()

        cancel_button = QPushButton(
            "Annuler"
        )

        add_button = QPushButton(
            "Ajouter"
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            add_button
        )

        layout.addLayout(
            buttons
        )

        cancel_button.clicked.connect(
            dialog.reject
        )

        def add_action():

            text = text_input.toPlainText()

            if not text:

                QMessageBox.warning(
                    dialog,
                    "Texte vide",
                    "Veuillez saisir du texte."
                )

                return

            self.actions.append({
                "type": "text",
                "text": text
            })

            self.refresh_action_list()

            dialog.accept()

        add_button.clicked.connect(
            add_action
        )

        dialog.exec()

    # ==========================================================
    # TOUCHE
    # ==========================================================

    def add_key_action(self):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Appui de touche"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        form = QFormLayout()

        key_input = QComboBox()

        keys = self.get_keys()

        for name, value in keys:

            key_input.addItem(
                name,
                value
            )

        ctrl_input = QComboBox()

        ctrl_input.addItem(
            "Non",
            False
        )

        ctrl_input.addItem(
            "Oui",
            True
        )

        shift_input = QComboBox()

        shift_input.addItem(
            "Non",
            False
        )

        shift_input.addItem(
            "Oui",
            True
        )

        alt_input = QComboBox()

        alt_input.addItem(
            "Non",
            False
        )

        alt_input.addItem(
            "Oui",
            True
        )

        win_input = QComboBox()

        win_input.addItem(
            "Non",
            False
        )

        win_input.addItem(
            "Oui",
            True
        )

        form.addRow(
            "Touche :",
            key_input
        )

        form.addRow(
            "CTRL :",
            ctrl_input
        )

        form.addRow(
            "SHIFT :",
            shift_input
        )

        form.addRow(
            "ALT :",
            alt_input
        )

        form.addRow(
            "Windows :",
            win_input
        )

        layout.addLayout(
            form
        )

        example = QLabel(
            "Exemple : CTRL = Oui + C = CTRL + C"
        )

        example.setStyleSheet(
            "color: gray; padding: 8px;"
        )

        layout.addWidget(
            example
        )

        buttons = QHBoxLayout()

        cancel_button = QPushButton(
            "Annuler"
        )

        add_button = QPushButton(
            "Ajouter"
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            add_button
        )

        layout.addLayout(
            buttons
        )

        cancel_button.clicked.connect(
            dialog.reject
        )

        def add_action():

            modifiers = []

            if ctrl_input.currentData():
                modifiers.append(
                    "ctrl"
                )

            if shift_input.currentData():
                modifiers.append(
                    "shift"
                )

            if alt_input.currentData():
                modifiers.append(
                    "alt"
                )

            if win_input.currentData():
                modifiers.append(
                    "win"
                )

            self.actions.append({
                "type": "key",
                "key": key_input.currentData(),
                "modifiers": modifiers
            })

            self.refresh_action_list()

            dialog.accept()

        add_button.clicked.connect(
            add_action
        )

        dialog.exec()

    # ==========================================================
    # LISTE DES TOUCHES
    # ==========================================================

    def get_keys(self):

        return [
            ("A", "a"),
            ("B", "b"),
            ("C", "c"),
            ("D", "d"),
            ("E", "e"),
            ("F", "f"),
            ("G", "g"),
            ("H", "h"),
            ("I", "i"),
            ("J", "j"),
            ("K", "k"),
            ("L", "l"),
            ("M", "m"),
            ("N", "n"),
            ("O", "o"),
            ("P", "p"),
            ("Q", "q"),
            ("R", "r"),
            ("S", "s"),
            ("T", "t"),
            ("U", "u"),
            ("V", "v"),
            ("W", "w"),
            ("X", "x"),
            ("Y", "y"),
            ("Z", "z"),

            ("0", "0"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),

            ("Entrée", "enter"),
            ("Échap", "esc"),
            ("Tabulation", "tab"),
            ("Espace", "space"),
            ("Retour arrière", "backspace"),
            ("Suppr", "delete"),

            ("Flèche haut", "up"),
            ("Flèche bas", "down"),
            ("Flèche gauche", "left"),
            ("Flèche droite", "right"),

            ("Début", "home"),
            ("Fin", "end"),
            ("Page précédente", "pageup"),
            ("Page suivante", "pagedown"),

            ("Insert", "insert"),

            ("F1", "f1"),
            ("F2", "f2"),
            ("F3", "f3"),
            ("F4", "f4"),
            ("F5", "f5"),
            ("F6", "f6"),
            ("F7", "f7"),
            ("F8", "f8"),
            ("F9", "f9"),
            ("F10", "f10"),
            ("F11", "f11"),
            ("F12", "f12"),
        ]

    # ==========================================================
    # BOUCLE
    # ==========================================================

    def add_loop_action(self):

        if not self.actions:

            QMessageBox.information(
                self,
                "Boucle",
                "Ajoutez d'abord une action."
            )

            return

        repetitions, ok = QInputDialog.getInt(
            self,
            "Boucle",
            "Nombre de répétitions :",
            2,
            1,
            100000,
            1
        )

        if not ok:
            return

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Sélectionner les actions"
        )

        dialog.resize(
            600,
            500
        )

        layout = QVBoxLayout(
            dialog
        )

        layout.addWidget(
            QLabel(
                "Sélectionnez les actions à répéter."
            )
        )

        action_list = QListWidget()

        action_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )

        for index, action in enumerate(
            self.actions,
            start=1
        ):

            item = QListWidgetItem(
                self.get_action_description(
                    action,
                    index
                )
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                index - 1
            )

            action_list.addItem(
                item
            )

        layout.addWidget(
            action_list
        )

        buttons = QHBoxLayout()

        cancel_button = QPushButton(
            "Annuler"
        )

        add_button = QPushButton(
            "Créer la boucle"
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            add_button
        )

        layout.addLayout(
            buttons
        )

        cancel_button.clicked.connect(
            dialog.reject
        )

        def create_loop():

            selected = action_list.selectedItems()

            if not selected:

                QMessageBox.warning(
                    dialog,
                    "Aucune action",
                    "Sélectionnez au moins une action."
                )

                return

            indexes = sorted([
                item.data(
                    Qt.ItemDataRole.UserRole
                )
                for item in selected
            ])

            expected = list(
                range(
                    indexes[0],
                    indexes[-1] + 1
                )
            )

            if indexes != expected:

                QMessageBox.warning(
                    dialog,
                    "Sélection invalide",
                    "Les actions doivent être consécutives."
                )

                return

            loop_actions = copy.deepcopy([
                self.actions[i]
                for i in indexes
            ])

            loop_action = {
                "type": "loop",
                "repetitions": repetitions,
                "actions": loop_actions
            }

            self.actions[
                indexes[0]:indexes[-1] + 1
            ] = [
                loop_action
            ]

            self.refresh_action_list()

            dialog.accept()

        add_button.clicked.connect(
            create_loop
        )

        dialog.exec()

    # ==========================================================
    # MONTER
    # ==============================================================

    def move_action_up(self):

        index = self.macro_list.currentRow()

        if index <= 0:

            return

        self.actions[index - 1], self.actions[index] = (
            self.actions[index],
            self.actions[index - 1]
        )

        self.refresh_action_list()

        self.macro_list.setCurrentRow(
            index - 1
        )

    # ==========================================================
    # DESCENDRE
    # ==============================================================

    def move_action_down(self):

        index = self.macro_list.currentRow()

        if index < 0:
            return

        if index >= len(self.actions) - 1:
            return

        self.actions[index], self.actions[index + 1] = (
            self.actions[index + 1],
            self.actions[index]
        )

        self.refresh_action_list()

        self.macro_list.setCurrentRow(
            index + 1
        )

    # ==========================================================
    # SUPPRIMER
    # ==========================================================

    def delete_selected_action(self):

        index = self.macro_list.currentRow()

        if index < 0:

            QMessageBox.information(
                self,
                "Suppression",
                "Sélectionnez une action."
            )

            return

        action = self.actions[index]

        answer = QMessageBox.question(
            self,
            "Supprimer",
            "Voulez-vous vraiment supprimer cette action ?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        del self.actions[index]

        self.refresh_action_list()

        if self.actions:

            self.macro_list.setCurrentRow(
                min(
                    index,
                    len(self.actions) - 1
                )
            )

    # ==========================================================
    # COPIER
    # ==========================================================

    def copy_selected_action(self):

        index = self.macro_list.currentRow()

        if index < 0:

            QMessageBox.information(
                self,
                "Copier",
                "Sélectionnez une action."
            )

            return

        self.copied_action = copy.deepcopy(
            self.actions[index]
        )

        self.btn_status.setText(
            "Action copiée"
        )

    # ==========================================================
    # COLLER
    # ==========================================================

    def paste_action(self):

        if self.copied_action is None:

            QMessageBox.information(
                self,
                "Coller",
                "Aucune action n'a été copiée."
            )

            return

        new_action = copy.deepcopy(
            self.copied_action
        )

        index = self.macro_list.currentRow()

        if index < 0:

            # Aucune sélection :
            # ajout à la fin
            self.actions.append(
                new_action
            )

            new_index = len(
                self.actions
            ) - 1

        else:

            # Collage juste après
            # l'action sélectionnée
            new_index = index + 1

            self.actions.insert(
                new_index,
                new_action
            )

        self.refresh_action_list()

        self.macro_list.setCurrentRow(
            new_index
        )

        self.btn_status.setText(
            "Action collée"
        )

    # ==========================================================
    # MODIFIER UNE ACTION
    # ==========================================================

    def edit_selected_action(self):

        index = self.macro_list.currentRow()

        if index < 0:

            QMessageBox.information(
                self,
                "Modification",
                "Sélectionnez une action."
            )

            return

        action = self.actions[index]

        action_type = action["type"]

        # ------------------------------------------------------
        # ATTENTE
        # ------------------------------------------------------

        if action_type == "wait":

            value, ok = QInputDialog.getDouble(
                self,
                "Modifier l'attente",
                "Durée de l'attente (secondes) :",
                action["duration"],
                0.01,
                3600.0,
                2
            )

            if not ok:
                return

            action["duration"] = value

        # ------------------------------------------------------
        # MOUVEMENT
        # ------------------------------------------------------

        elif action_type == "move":

            result = self.edit_move_action(
                action
            )

            if result is None:
                return

            self.actions[index] = result

        # ------------------------------------------------------
        # CLIC
        # ------------------------------------------------------

        elif action_type == "click":

            result = self.edit_click_action(
                action
            )

            if result is None:
                return

            self.actions[index] = result

        # ------------------------------------------------------
        # TEXTE
        # ------------------------------------------------------

        elif action_type == "text":

            result = self.edit_text_action(
                action
            )

            if result is None:
                return

            self.actions[index] = result

        # ------------------------------------------------------
        # TOUCHE
        # ------------------------------------------------------

        elif action_type == "key":

            result = self.edit_key_action(
                action
            )

            if result is None:
                return

            self.actions[index] = result

        # ------------------------------------------------------
        # BOUCLE
        # ------------------------------------------------------

        elif action_type == "loop":

            repetitions, ok = QInputDialog.getInt(
                self,
                "Modifier la boucle",
                "Nombre de répétitions :",
                action["repetitions"],
                1,
                100000,
                1
            )

            if not ok:
                return

            action["repetitions"] = repetitions

        self.refresh_action_list()

        self.macro_list.setCurrentRow(
            index
        )

    # ==========================================================
    # MODIFIER MOUVEMENT
    # ==========================================================

    def edit_move_action(self, action):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Modifier le mouvement"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        form = QFormLayout()

        x_input = QSpinBox()

        x_input.setRange(
            -10000,
            10000
        )

        x_input.setValue(
            action["x"]
        )

        y_input = QSpinBox()

        y_input.setRange(
            -10000,
            10000
        )

        y_input.setValue(
            action["y"]
        )

        duration_input = QDoubleSpinBox()

        duration_input.setRange(
            0.0,
            60.0
        )

        duration_input.setSingleStep(
            0.1
        )

        duration_input.setValue(
            action["duration"]
        )

        form.addRow(
            "X :",
            x_input
        )

        form.addRow(
            "Y :",
            y_input
        )

        form.addRow(
            "Durée :",
            duration_input
        )

        layout.addLayout(
            form
        )

        capture_button = QPushButton(
            "📍 Capturer avec F8"
        )

        layout.addWidget(
            capture_button
        )

        def capture():

            result = self.select_mouse_position()

            if result is None:
                return

            x_input.setValue(
                result["x"]
            )

            y_input.setValue(
                result["y"]
            )

        capture_button.clicked.connect(
            capture
        )

        buttons = QHBoxLayout()

        cancel = QPushButton(
            "Annuler"
        )

        save = QPushButton(
            "Enregistrer"
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        layout.addLayout(
            buttons
        )

        cancel.clicked.connect(
            dialog.reject
        )

        result = []

        def save_action():

            result.append({
                "type": "move",
                "x": int(
                    x_input.value()
                ),
                "y": int(
                    y_input.value()
                ),
                "duration": float(
                    duration_input.value()
                )
            })

            dialog.accept()

        save.clicked.connect(
            save_action
        )

        dialog.exec()

        if not result:
            return None

        return result[0]

    # ==========================================================
    # MODIFIER CLIC
    # ==========================================================

    def edit_click_action(self, action):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Modifier le clic"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        form = QFormLayout()

        x_input = QSpinBox()

        x_input.setRange(
            -10000,
            10000
        )

        x_input.setValue(
            action["x"]
        )

        y_input = QSpinBox()

        y_input.setRange(
            -10000,
            10000
        )

        y_input.setValue(
            action["y"]
        )

        button_input = QComboBox()

        button_input.addItem(
            "Gauche",
            "left"
        )

        button_input.addItem(
            "Droit",
            "right"
        )

        button_input.addItem(
            "Milieu",
            "middle"
        )

        button_index = button_input.findData(
            action["button"]
        )

        if button_index >= 0:
            button_input.setCurrentIndex(
                button_index
            )

        click_input = QComboBox()

        click_input.addItem(
            "Simple clic",
            1
        )

        click_input.addItem(
            "Double clic",
            2
        )

        click_index = click_input.findData(
            action["clicks"]
        )

        if click_index >= 0:
            click_input.setCurrentIndex(
                click_index
            )

        form.addRow(
            "X :",
            x_input
        )

        form.addRow(
            "Y :",
            y_input
        )

        form.addRow(
            "Bouton :",
            button_input
        )

        form.addRow(
            "Type :",
            click_input
        )

        layout.addLayout(
            form
        )

        capture_button = QPushButton(
            "📍 Capturer avec F8"
        )

        layout.addWidget(
            capture_button
        )

        def capture():

            result = self.select_mouse_position()

            if result is None:
                return

            x_input.setValue(
                result["x"]
            )

            y_input.setValue(
                result["y"]
            )

        capture_button.clicked.connect(
            capture
        )

        buttons = QHBoxLayout()

        cancel = QPushButton(
            "Annuler"
        )

        save = QPushButton(
            "Enregistrer"
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        layout.addLayout(
            buttons
        )

        cancel.clicked.connect(
            dialog.reject
        )

        result = []

        def save_action():

            result.append({
                "type": "click",
                "x": int(
                    x_input.value()
                ),
                "y": int(
                    y_input.value()
                ),
                "button": button_input.currentData(),
                "clicks": click_input.currentData()
            })

            dialog.accept()

        save.clicked.connect(
            save_action
        )

        dialog.exec()

        if not result:
            return None

        return result[0]

    # ==========================================================
    # MODIFIER TEXTE
    # ==========================================================

    def edit_text_action(self, action):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Modifier le texte"
        )

        dialog.resize(
            500,
            300
        )

        layout = QVBoxLayout(
            dialog
        )

        layout.addWidget(
            QLabel(
                "Texte :"
            )
        )

        text_input = QTextEdit()

        text_input.setPlainText(
            action["text"]
        )

        layout.addWidget(
            text_input
        )

        buttons = QHBoxLayout()

        cancel = QPushButton(
            "Annuler"
        )

        save = QPushButton(
            "Enregistrer"
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        layout.addLayout(
            buttons
        )

        cancel.clicked.connect(
            dialog.reject
        )

        result = []

        def save_action():

            text = text_input.toPlainText()

            if not text:

                QMessageBox.warning(
                    dialog,
                    "Texte vide",
                    "Le texte ne peut pas être vide."
                )

                return

            result.append({
                "type": "text",
                "text": text
            })

            dialog.accept()

        save.clicked.connect(
            save_action
        )

        dialog.exec()

        if not result:
            return None

        return result[0]

    # ==========================================================
    # MODIFIER TOUCHE
    # ==========================================================

    def edit_key_action(self, action):

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Modifier la touche"
        )

        dialog.setFixedWidth(
            450
        )

        layout = QVBoxLayout(
            dialog
        )

        form = QFormLayout()

        key_input = QComboBox()

        for name, value in self.get_keys():

            key_input.addItem(
                name,
                value
            )

        index = key_input.findData(
            action["key"]
        )

        if index >= 0:

            key_input.setCurrentIndex(
                index
            )

        modifiers = action.get(
            "modifiers",
            []
        )

        ctrl_input = QComboBox()

        ctrl_input.addItem(
            "Non",
            False
        )

        ctrl_input.addItem(
            "Oui",
            True
        )

        ctrl_input.setCurrentIndex(
            1 if "ctrl" in modifiers else 0
        )

        shift_input = QComboBox()

        shift_input.addItem(
            "Non",
            False
        )

        shift_input.addItem(
            "Oui",
            True
        )

        shift_input.setCurrentIndex(
            1 if "shift" in modifiers else 0
        )

        alt_input = QComboBox()

        alt_input.addItem(
            "Non",
            False
        )

        alt_input.addItem(
            "Oui",
            True
        )

        alt_input.setCurrentIndex(
            1 if "alt" in modifiers else 0
        )

        win_input = QComboBox()

        win_input.addItem(
            "Non",
            False
        )

        win_input.addItem(
            "Oui",
            True
        )

        win_input.setCurrentIndex(
            1 if "win" in modifiers else 0
        )

        form.addRow(
            "Touche :",
            key_input
        )

        form.addRow(
            "CTRL :",
            ctrl_input
        )

        form.addRow(
            "SHIFT :",
            shift_input
        )

        form.addRow(
            "ALT :",
            alt_input
        )

        form.addRow(
            "Windows :",
            win_input
        )

        layout.addLayout(
            form
        )

        buttons = QHBoxLayout()

        cancel = QPushButton(
            "Annuler"
        )

        save = QPushButton(
            "Enregistrer"
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        layout.addLayout(
            buttons
        )

        cancel.clicked.connect(
            dialog.reject
        )

        result = []

        def save_action():

            modifiers = []

            if ctrl_input.currentData():
                modifiers.append(
                    "ctrl"
                )

            if shift_input.currentData():
                modifiers.append(
                    "shift"
                )

            if alt_input.currentData():
                modifiers.append(
                    "alt"
                )

            if win_input.currentData():
                modifiers.append(
                    "win"
                )

            result.append({
                "type": "key",
                "key": key_input.currentData(),
                "modifiers": modifiers
            })

            dialog.accept()

        save.clicked.connect(
            save_action
        )

        dialog.exec()

        if not result:
            return None

        return result[0]

    # ==========================================================
    # DESCRIPTION DES ACTIONS
    # ==========================================================

    def get_action_description(
        self,
        action,
        index=None
    ):

        prefix = ""

        if index is not None:

            prefix = f"{index}. "

        action_type = action["type"]

        if action_type == "wait":

            return (
                f"{prefix}⏱ Attendre "
                f"{action['duration']:.2f}s"
            )

        if action_type == "move":

            return (
                f"{prefix}🖱 Déplacer souris "
                f"→ X:{action['x']} | "
                f"Y:{action['y']} | "
                f"Durée:{action['duration']:.2f}s"
            )

        if action_type == "click":

            buttons = {
                "left": "gauche",
                "right": "droit",
                "middle": "milieu"
            }

            click_types = {
                1: "Simple",
                2: "Double"
            }

            return (
                f"{prefix}🖱 Clic "
                f"{buttons.get(action['button'])} "
                f"→ {click_types.get(action['clicks'])} "
                f"à X:{action['x']} Y:{action['y']}"
            )

        if action_type == "text":

            text = action["text"].replace(
                "\n",
                "\\n"
            )

            if len(text) > 60:

                text = text[:57] + "..."

            return (
                f'{prefix}⌨ Écrire : "{text}"'
            )

        if action_type == "key":

            modifier_names = {
                "ctrl": "CTRL",
                "shift": "SHIFT",
                "alt": "ALT",
                "win": "WIN"
            }

            key_names = {
                "enter": "ENTER",
                "esc": "ESC",
                "tab": "TAB",
                "space": "ESPACE",
                "backspace": "BACKSPACE",
                "delete": "DELETE",
                "up": "↑",
                "down": "↓",
                "left": "←",
                "right": "→",
                "home": "HOME",
                "end": "END",
                "pageup": "PAGE UP",
                "pagedown": "PAGE DOWN",
                "insert": "INSERT"
            }

            parts = []

            for modifier in action["modifiers"]:

                parts.append(
                    modifier_names.get(
                        modifier,
                        modifier.upper()
                    )
                )

            parts.append(
                key_names.get(
                    action["key"],
                    action["key"].upper()
                )
            )

            return (
                f"{prefix}⌨ Appuyer : "
                f"{' + '.join(parts)}"
            )

        if action_type == "loop":

            return (
                f"{prefix}🔁 Boucle "
                f"× {action['repetitions']} "
                f"({len(action['actions'])} action(s))"
            )

        return (
            f"{prefix}Action inconnue"
        )

    # ==========================================================
    # RAFRAICHIR LA LISTE
    # ==========================================================

    def refresh_action_list(self):

        self.macro_list.clear()

        for index, action in enumerate(
            self.actions,
            start=1
        ):

            self.macro_list.addItem(
                self.get_action_description(
                    action,
                    index
                )
            )

    # ==========================================================
    # EXECUTION
    # ==========================================================

    def execute_macro(self):

        if self.is_running:

            self.stop_macro()

            return

        if not self.actions:

            QMessageBox.information(
                self,
                "Exécution",
                "La macro ne contient aucune action."
            )

            return

        actions_copy = copy.deepcopy(
            self.actions
        )

        self.is_running = True

        self.btn_execute.setText(
            "■ Arrêter"
        )

        self.btn_status.setText(
            "Exécution..."
        )

        self.worker_thread = threading.Thread(
            target=self.run_worker,
            args=(actions_copy,),
            daemon=True
        )

        self.worker_thread.start()

    def run_worker(self, actions):

        self.worker = MacroWorker(
            actions
        )

        self.worker.status.connect(
            self.update_execution_status
        )

        self.worker.finished.connect(
            self.execution_finished
        )

        self.worker.run()

    def update_execution_status(self, message):

        self.btn_status.setText(
            message
        )

    def execution_finished(self):

        self.is_running = False

        self.btn_execute.setText(
            "▶ Exécuter"
        )

        self.btn_status.setText(
            "Prêt"
        )

        self.worker = None
        self.worker_thread = None

    def stop_macro(self):

        if self.worker is not None:

            self.worker.stop()

        self.btn_status.setText(
            "Arrêt demandé..."
        )


# ==============================================================
# PROGRAMME PRINCIPAL
# ==============================================================

def main():

    app = QApplication(
        sys.argv
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()