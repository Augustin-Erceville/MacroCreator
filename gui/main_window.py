"""Fenêtre principale de Macro Creator."""

import copy
import os
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import macro
from core.executor import MacroWorker
from core.hotkeys import STOP_KEY_NAME, GlobalHotkey
from gui import dialogs

APPLICATION_NAME = "Macro Creator"

# Délai par défaut avant le démarrage d'une macro (secondes)
DEFAULT_START_DELAY = 3


# ==============================================================
# ECRANS
# ==============================================================

def screen_areas(physical=True):
    """Zones d'affichage des écrans : (gauche, haut, droite, bas).

    Droite et bas sont exclus. Les valeurs peuvent être négatives : sous
    Windows, l'origine (0, 0) est le coin haut-gauche de l'écran principal,
    et un écran placé à sa gauche ou au-dessus occupe donc des coordonnées
    négatives.

    Qt raisonne en pixels logiques ; PyAutoGUI, comme les coordonnées
    enregistrées dans les macros, raisonne en pixels physiques. Avec
    `physical=True`, la géométrie est convertie selon la mise à l'échelle
    de chaque écran (125 %, 150 %...).
    """

    areas = []

    for screen in QGuiApplication.screens():

        geometry = screen.geometry()

        ratio = screen.devicePixelRatio() if physical else 1.0

        areas.append((
            round(geometry.left() * ratio),
            round(geometry.top() * ratio),
            round((geometry.left() + geometry.width()) * ratio),
            round((geometry.top() + geometry.height()) * ratio),
        ))

    return areas


def check_areas():
    """Zones acceptées pour la vérification des coordonnées.

    On retient les deux interprétations (logique et physique) : en cas de
    mise à l'échelle différente d'un écran à l'autre, la conversion n'est
    qu'approximative, et mieux vaut un avertissement trop permissif qu'une
    alerte injustifiée sur des coordonnées parfaitement valides.
    """

    areas = screen_areas(physical=True)

    for area in screen_areas(physical=False):

        if area not in areas:
            areas.append(area)

    return areas


def describe_screens(screens=None):
    """Phrase décrivant la disposition des écrans."""

    screens = screen_areas() if screens is None else screens

    if not screens:
        return "Aucun écran détecté."

    if len(screens) == 1:

        left, top, right, bottom = screens[0]

        return (
            f"Écran unique : {right - left} × {bottom - top} pixels, "
            f"origine X:{left} Y:{top}."
        )

    details = ", ".join(
        f"{right - left}×{bottom - top} en X:{left} Y:{top}"
        for left, top, right, bottom in screens
    )

    return f"{len(screens)} écrans détectés : {details}."


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        # --- État de la macro ---
        self.actions = []
        self.macro_name = "Nouvelle macro"
        self.current_path = None
        self.modified = False

        # --- Presse-papier interne ---
        self.copied_action = None

        # --- Exécution ---
        self.worker = None
        self.worker_thread = None
        self.is_running = False
        self.countdown_timer = None
        self.countdown_value = 0

        self.resize(1150, 780)

        self.setup_ui()
        self.setup_menu()
        self.connect_signals()
        self.setup_hotkey()

        self.refresh_tree()
        self.update_title()

    # ==========================================================
    # INTERFACE
    # ==========================================================

    def setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        title = QLabel("MACRO CREATOR")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet(
            "font-size: 24px; font-weight: bold; padding: 10px;"
        )

        main_layout.addWidget(title)

        content_layout = QHBoxLayout()

        content_layout.addWidget(self._build_actions_panel(), 1)
        content_layout.addWidget(self._build_macro_panel(), 3)

        main_layout.addLayout(content_layout)

        main_layout.addLayout(self._build_bottom_bar())

        self.statusBar().showMessage("Prêt")

    def _build_actions_panel(self):

        group = QGroupBox("Ajouter une action")

        layout = QVBoxLayout(group)

        self.btn_record = QPushButton("● Enregistrer mes gestes")

        self.btn_record.setStyleSheet("font-weight: bold; padding: 6px;")

        layout.addWidget(self.btn_record)

        separator = QLabel("— ou action par action —")

        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        separator.setStyleSheet("color: gray; padding: 6px;")

        layout.addWidget(separator)

        self.action_buttons = {}

        for action_type, label in (
            ("wait", "⏱ Temps d'attente"),
            ("move", "🖱 Mouvement souris"),
            ("click", "🖱 Clic souris"),
            ("drag", "🖱 Glisser-déposer"),
            ("scroll", "🖱 Molette"),
            ("text", "⌨ Inscription de texte"),
            ("key", "⌨ Appui de touche"),
            ("loop", "🔁 Boucle (vide)"),
        ):

            button = QPushButton(label)

            layout.addWidget(button)

            self.action_buttons[action_type] = button

        self.insertion_label = QLabel()

        self.insertion_label.setWordWrap(True)

        self.insertion_label.setStyleSheet("color: gray; padding: 8px;")

        layout.addWidget(self.insertion_label)

        layout.addStretch()

        return group

    def _build_macro_panel(self):

        group = QGroupBox("Actions de la macro")

        layout = QVBoxLayout(group)

        self.macro_tree = QTreeWidget()

        self.macro_tree.setHeaderHidden(True)

        self.macro_tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )

        self.macro_tree.setIndentation(22)

        layout.addWidget(self.macro_tree)

        first_row = QHBoxLayout()

        self.btn_up = QPushButton("↑ Monter")
        self.btn_down = QPushButton("↓ Descendre")
        self.btn_edit = QPushButton("Modifier")
        self.btn_delete = QPushButton("Supprimer")

        for widget in (
            self.btn_up,
            self.btn_down,
            self.btn_edit,
            self.btn_delete,
        ):
            first_row.addWidget(widget)

        layout.addLayout(first_row)

        second_row = QHBoxLayout()

        self.btn_copy = QPushButton("Copier")
        self.btn_paste = QPushButton("Coller")
        self.btn_group = QPushButton("🔁 Grouper en boucle")
        self.btn_ungroup = QPushButton("Dégrouper la boucle")

        for widget in (
            self.btn_copy,
            self.btn_paste,
            self.btn_group,
            self.btn_ungroup,
        ):
            second_row.addWidget(widget)

        layout.addLayout(second_row)

        return group

    def _build_bottom_bar(self):

        layout = QHBoxLayout()

        self.btn_new = QPushButton("Nouveau")
        self.btn_save = QPushButton("Enregistrer")
        self.btn_load = QPushButton("Charger")

        for widget in (self.btn_new, self.btn_save, self.btn_load):
            layout.addWidget(widget)

        layout.addSpacing(20)

        layout.addWidget(QLabel("Démarrer dans :"))

        self.delay_input = QSpinBox()
        self.delay_input.setRange(0, 60)
        self.delay_input.setValue(DEFAULT_START_DELAY)
        self.delay_input.setSuffix(" s")

        layout.addWidget(self.delay_input)

        layout.addStretch()

        self.execution_label = QLabel("Prêt")

        self.execution_label.setStyleSheet("padding: 0 12px;")

        layout.addWidget(self.execution_label)

        self.btn_execute = QPushButton("▶ Exécuter")

        self.btn_execute.setStyleSheet("font-weight: bold; padding: 6px;")

        layout.addWidget(self.btn_execute)

        return layout

    def setup_menu(self):

        file_menu = self.menuBar().addMenu("&Fichier")

        self.act_new = QAction("&Nouveau", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)

        self.act_open = QAction("&Ouvrir...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)

        self.act_save = QAction("&Enregistrer", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)

        self.act_save_as = QAction("Enregistrer &sous...", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)

        self.act_rename = QAction("Renommer la macro...", self)

        self.act_quit = QAction("&Quitter", self)
        self.act_quit.setShortcut(QKeySequence.StandardKey.Quit)

        for action in (
            self.act_new,
            self.act_open,
            self.act_save,
            self.act_save_as,
        ):
            file_menu.addAction(action)

        file_menu.addSeparator()
        file_menu.addAction(self.act_rename)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        edit_menu = self.menuBar().addMenu("&Édition")

        self.act_copy = QAction("Copier l'action", self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)

        self.act_paste = QAction("Coller l'action", self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)

        self.act_delete = QAction("Supprimer l'action", self)
        self.act_delete.setShortcut(QKeySequence.StandardKey.Delete)

        for action in (self.act_copy, self.act_paste, self.act_delete):
            edit_menu.addAction(action)

        run_menu = self.menuBar().addMenu("E&xécution")

        self.act_run = QAction("Exécuter la macro", self)
        self.act_run.setShortcut(QKeySequence("F5"))

        self.act_stop = QAction(f"Arrêter ({STOP_KEY_NAME})", self)

        self.act_record = QAction("Enregistrer mes gestes", self)
        self.act_record.setShortcut(QKeySequence("Ctrl+R"))

        for action in (self.act_run, self.act_stop, self.act_record):
            run_menu.addAction(action)

        help_menu = self.menuBar().addMenu("&Aide")

        self.act_about = QAction("À propos", self)

        help_menu.addAction(self.act_about)

    def connect_signals(self):

        self.btn_record.clicked.connect(self.record_macro)

        for action_type, button in self.action_buttons.items():
            button.clicked.connect(
                lambda _checked=False, kind=action_type:
                self.add_action(kind)
            )

        self.btn_up.clicked.connect(self.move_action_up)
        self.btn_down.clicked.connect(self.move_action_down)
        self.btn_edit.clicked.connect(self.edit_selected_action)
        self.btn_delete.clicked.connect(self.delete_selected_action)
        self.btn_copy.clicked.connect(self.copy_selected_action)
        self.btn_paste.clicked.connect(self.paste_action)
        self.btn_group.clicked.connect(self.group_into_loop)
        self.btn_ungroup.clicked.connect(self.ungroup_loop)

        self.btn_new.clicked.connect(self.new_macro)
        self.btn_save.clicked.connect(self.save_macro)
        self.btn_load.clicked.connect(self.load_macro)
        self.btn_execute.clicked.connect(self.toggle_execution)

        self.macro_tree.itemDoubleClicked.connect(
            lambda *_: self.edit_selected_action()
        )

        self.macro_tree.itemSelectionChanged.connect(
            self.update_insertion_hint
        )

        self.act_new.triggered.connect(self.new_macro)
        self.act_open.triggered.connect(self.load_macro)
        self.act_save.triggered.connect(self.save_macro)
        self.act_save_as.triggered.connect(self.save_macro_as)
        self.act_rename.triggered.connect(self.rename_macro)
        self.act_quit.triggered.connect(self.close)

        self.act_copy.triggered.connect(self.copy_selected_action)
        self.act_paste.triggered.connect(self.paste_action)
        self.act_delete.triggered.connect(self.delete_selected_action)

        self.act_run.triggered.connect(self.execute_macro)
        self.act_stop.triggered.connect(self.stop_macro)
        self.act_record.triggered.connect(self.record_macro)

        self.act_about.triggered.connect(self.show_about)

    def setup_hotkey(self):
        """Raccourci global d'arrêt d'urgence."""

        self.stop_hotkey = GlobalHotkey(STOP_KEY_NAME, self)

        self.stop_hotkey.triggered.connect(self.on_stop_hotkey)

        if self.stop_hotkey.start():

            self.statusBar().showMessage(
                f"Prêt — {STOP_KEY_NAME} arrête une macro en cours."
            )

        else:

            self.statusBar().showMessage(
                "Prêt — raccourci d'arrêt indisponible : utilisez le coin "
                "haut-gauche de l'écran pour un arrêt d'urgence."
            )

    def on_stop_hotkey(self):

        if self.is_running:
            self.stop_macro()

    # ==========================================================
    # ARBRE DES ACTIONS
    # ==========================================================

    def refresh_tree(self, select_path=None):

        self.macro_tree.clear()

        self._fill_tree(self.macro_tree.invisibleRootItem(), self.actions, [])

        if select_path is not None:
            self.select_path(select_path)

        self.update_insertion_hint()

        self.update_title()

    def _fill_tree(self, parent_item, actions, path):

        for index, action in enumerate(actions):

            item_path = path + [index]

            item = QTreeWidgetItem(
                parent_item,
                [macro.describe_action(action, index + 1)],
            )

            item.setData(0, Qt.ItemDataRole.UserRole, item_path)

            if action.get("type") == "loop":

                self._fill_tree(item, action.get("actions", []), item_path)

                item.setExpanded(True)

    def item_for_path(self, path):

        item = self.macro_tree.invisibleRootItem()

        for step in path:

            if step >= item.childCount():
                return None

            item = item.child(step)

        return None if item is self.macro_tree.invisibleRootItem() else item

    def select_path(self, path):

        item = self.item_for_path(path)

        if item is None:

            if path and path[-1] > 0:
                item = self.item_for_path(path[:-1] + [path[-1] - 1])

            if item is None and len(path) > 1:
                item = self.item_for_path(path[:-1])

        if item is None:
            return

        self.macro_tree.setCurrentItem(item)

    def selected_path(self):
        """Chemin de l'action sélectionnée, ou None."""

        item = self.macro_tree.currentItem()

        if item is None or not item.isSelected():
            return None

        path = item.data(0, Qt.ItemDataRole.UserRole)

        return list(path) if path is not None else None

    def selected_paths(self):

        paths = []

        for item in self.macro_tree.selectedItems():

            path = item.data(0, Qt.ItemDataRole.UserRole)

            if path is not None:
                paths.append(list(path))

        return sorted(paths)

    def update_insertion_hint(self):

        path = self.selected_path()

        if path is None:

            self.insertion_label.setText(
                "Les nouvelles actions sont ajoutées à la fin de la macro."
            )

            return

        action = macro.get_action(self.actions, path)

        if action.get("type") == "loop":

            self.insertion_label.setText(
                "Boucle sélectionnée : les nouvelles actions seront "
                "ajoutées à l'intérieur de la boucle."
            )

            return

        self.insertion_label.setText(
            "Les nouvelles actions seront insérées juste après l'action "
            "sélectionnée."
        )

    # ==========================================================
    # AJOUT ET INSERTION
    # ==========================================================

    def insert_actions(self, new_actions):
        """Insère des actions au point courant et met à jour l'arbre."""

        if not new_actions:
            return

        path = self.selected_path()

        if path is None:

            self.actions.extend(new_actions)

            target = [len(self.actions) - 1]

        else:

            action = macro.get_action(self.actions, path)

            if action.get("type") == "loop":

                # Ajout à l'intérieur de la boucle sélectionnée
                action["actions"].extend(new_actions)

                target = path + [len(action["actions"]) - 1]

            else:

                container, index = macro.get_container(self.actions, path)

                for offset, item in enumerate(new_actions, start=1):
                    container.insert(index + offset, item)

                target = path[:-1] + [index + len(new_actions)]

        self.mark_modified()

        self.refresh_tree(target)

    def add_action(self, action_type):

        dialog_class = dialogs.ACTION_DIALOGS[action_type]

        action = dialog_class.run(self)

        if action is None:
            return

        self.insert_actions([action])

        self.statusBar().showMessage("Action ajoutée.", 3000)

    def record_macro(self):

        recorded = dialogs.RecorderDialog.run(self)

        if not recorded:
            return

        self.insert_actions(recorded)

        self.statusBar().showMessage(
            f"{len(recorded)} action(s) enregistrée(s).", 5000
        )

    # ==========================================================
    # MODIFICATION
    # ==========================================================

    def edit_selected_action(self):

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Modification")

            return

        container, index = macro.get_container(self.actions, path)

        action = container[index]

        dialog_class = dialogs.ACTION_DIALOGS.get(action["type"])

        if dialog_class is None:
            return

        updated = dialog_class.run(self, action)

        if updated is None:
            return

        container[index] = updated

        self.mark_modified()

        self.refresh_tree(path)

    def delete_selected_action(self):

        paths = self.selected_paths()

        if not paths:

            self.warn_no_selection("Suppression")

            return

        answer = QMessageBox.question(
            self,
            "Supprimer",
            f"Voulez-vous vraiment supprimer {len(paths)} action(s) ?\n"
            "Le contenu des boucles supprimées sera perdu.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        # Suppression de la fin vers le début : les index restent valides.
        for path in sorted(paths, reverse=True):

            try:
                container, index = macro.get_container(self.actions, path)

            except macro.MacroError:
                # Action déjà supprimée avec sa boucle parente.
                continue

            del container[index]

        self.mark_modified()

        self.refresh_tree(paths[0])

    def move_action_up(self):

        self._move_action(-1)

    def move_action_down(self):

        self._move_action(1)

    def _move_action(self, offset):

        path = self.selected_path()

        if path is None:
            return

        container, index = macro.get_container(self.actions, path)

        target = index + offset

        if target < 0 or target >= len(container):
            return

        container[index], container[target] = (
            container[target],
            container[index],
        )

        self.mark_modified()

        self.refresh_tree(path[:-1] + [target])

    def copy_selected_action(self):

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Copier")

            return

        self.copied_action = copy.deepcopy(
            macro.get_action(self.actions, path)
        )

        self.statusBar().showMessage("Action copiée.", 3000)

    def paste_action(self):

        if self.copied_action is None:

            QMessageBox.information(
                self,
                "Coller",
                "Aucune action n'a été copiée.",
            )

            return

        self.insert_actions([copy.deepcopy(self.copied_action)])

        self.statusBar().showMessage("Action collée.", 3000)

    # ==========================================================
    # BOUCLES
    # ==========================================================

    def group_into_loop(self):

        paths = self.selected_paths()

        if not paths:

            QMessageBox.information(
                self,
                "Boucle",
                "Sélectionnez les actions à répéter "
                "(Ctrl ou Maj pour en choisir plusieurs).",
            )

            return

        parent = paths[0][:-1]

        if any(path[:-1] != parent for path in paths):

            QMessageBox.warning(
                self,
                "Boucle",
                "Les actions sélectionnées doivent se trouver au même "
                "niveau.",
            )

            return

        indexes = [path[-1] for path in paths]

        if indexes != list(range(indexes[0], indexes[-1] + 1)):

            QMessageBox.warning(
                self,
                "Boucle",
                "Les actions sélectionnées doivent être consécutives.",
            )

            return

        loop = dialogs.LoopDialog.run(self)

        if loop is None:
            return

        container, _ = macro.get_container(self.actions, paths[0])

        loop["actions"] = copy.deepcopy(
            container[indexes[0]:indexes[-1] + 1]
        )

        container[indexes[0]:indexes[-1] + 1] = [loop]

        self.mark_modified()

        self.refresh_tree(parent + [indexes[0]])

    def ungroup_loop(self):

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Dégrouper")

            return

        container, index = macro.get_container(self.actions, path)

        action = container[index]

        if action.get("type") != "loop":

            QMessageBox.information(
                self,
                "Dégrouper",
                "Sélectionnez une boucle.",
            )

            return

        inner = action.get("actions", [])

        container[index:index + 1] = copy.deepcopy(inner)

        self.mark_modified()

        self.refresh_tree(path)

        self.statusBar().showMessage(
            "Boucle dégroupée : les répétitions sont perdues, les actions "
            "sont conservées.",
            5000,
        )

    def warn_no_selection(self, title):

        QMessageBox.information(
            self,
            title,
            "Sélectionnez une action dans la liste.",
        )

    # ==========================================================
    # FICHIERS
    # ==========================================================

    def mark_modified(self):

        self.modified = True

        self.update_title()

    def update_title(self):

        location = (
            os.path.basename(self.current_path)
            if self.current_path
            else "non enregistrée"
        )

        marker = " •" if self.modified else ""

        self.setWindowTitle(
            f"{APPLICATION_NAME} — {self.macro_name} "
            f"({location}){marker}"
        )

    def confirm_discard(self):
        """Retourne True si l'on peut abandonner les modifications."""

        if not self.modified:
            return True

        answer = QMessageBox.question(
            self,
            "Modifications non enregistrées",
            f"La macro « {self.macro_name} » a été modifiée.\n"
            "Voulez-vous l'enregistrer ?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )

        if answer == QMessageBox.StandardButton.Cancel:
            return False

        if answer == QMessageBox.StandardButton.Save:
            return self.save_macro()

        return True

    def new_macro(self):

        if self.is_running:

            self.warn_running()

            return

        if not self.confirm_discard():
            return

        name = dialogs.ask_macro_name(self, "Nouvelle macro")

        if name is None:
            return

        self.actions = []
        self.macro_name = name
        self.current_path = None
        self.modified = False

        self.refresh_tree()

        self.statusBar().showMessage("Nouvelle macro créée.", 3000)

    def rename_macro(self):

        name = dialogs.ask_macro_name(self, self.macro_name)

        if name is None:
            return

        self.macro_name = name

        self.mark_modified()

    def save_macro(self):
        """Enregistre la macro. Retourne True en cas de succès."""

        if self.current_path is None:
            return self.save_macro_as()

        return self._write(self.current_path)

    def save_macro_as(self):

        macro.ensure_data_dir()

        suggestion = os.path.join(
            macro.DATA_DIR,
            macro.safe_filename(self.macro_name),
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer la macro",
            suggestion,
            "Macros Macro Creator (*.json)",
        )

        if not path:
            return False

        if not path.lower().endswith(macro.FILE_EXTENSION):
            path += macro.FILE_EXTENSION

        return self._write(path)

    def _write(self, path):

        try:
            macro.save_macro(path, self.macro_name, self.actions)

        except macro.MacroError as error:

            QMessageBox.critical(self, "Enregistrement", str(error))

            return False

        self.current_path = path
        self.modified = False

        self.update_title()

        self.statusBar().showMessage(
            f"Macro enregistrée : {path}", 5000
        )

        return True

    def load_macro(self):

        if self.is_running:

            self.warn_running()

            return

        if not self.confirm_discard():
            return

        macro.ensure_data_dir()

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Charger une macro",
            macro.DATA_DIR,
            "Macros Macro Creator (*.json)",
        )

        if not path:
            return

        try:
            name, actions = macro.load_macro(path)

        except macro.MacroError as error:

            QMessageBox.critical(self, "Chargement", str(error))

            return

        self.macro_name = name
        self.actions = actions
        self.current_path = path
        self.modified = False

        self.refresh_tree()

        self.statusBar().showMessage(
            f"Macro chargée : {macro.count_actions(actions)} action(s).",
            5000,
        )

    # ==========================================================
    # EXECUTION
    # ==========================================================

    def toggle_execution(self):

        if self.is_running:

            self.stop_macro()

            return

        self.execute_macro()

    def execute_macro(self):

        if self.is_running:
            return

        if not self.actions:

            QMessageBox.information(
                self,
                "Exécution",
                "La macro ne contient aucune action.",
            )

            return

        try:
            macro.validate_actions(self.actions)

        except macro.MacroError as error:

            QMessageBox.critical(self, "Exécution", str(error))

            return

        if not self.check_screen_coordinates():
            return

        self.is_running = True

        self.btn_execute.setText("■ Arrêter")

        self.set_editing_enabled(False)

        self.countdown_value = self.delay_input.value()

        if self.countdown_value > 0:

            self.countdown_timer = QTimer(self)

            self.countdown_timer.timeout.connect(self._tick_countdown)

            self._show_countdown()

            self.countdown_timer.start(1000)

            return

        self._start_worker()

    def check_screen_coordinates(self):
        """Prévient si des actions visent un point hors de tout écran.

        En multi-écran, les coordonnées négatives sont normales : l'origine
        est le coin haut-gauche de l'écran principal, et un écran situé à
        gauche ou au-dessus se trouve donc en négatif. On vérifie donc
        l'appartenance à l'un quelconque des écrans, pas à un rectangle
        unique.
        """

        problems = macro.check_coordinates(self.actions, check_areas())

        if not problems:
            return True

        preview = "\n".join(problems[:5])

        if len(problems) > 5:
            preview += f"\n... et {len(problems) - 5} autre(s)."

        answer = QMessageBox.warning(
            self,
            "Coordonnées hors écran",
            f"{describe_screens()}\n\n"
            "Ces actions visent un point situé en dehors de tous les "
            f"écrans :\n\n{preview}\n\nExécuter quand même ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        return answer == QMessageBox.StandardButton.Yes

    def _show_countdown(self):

        self.execution_label.setText(
            f"Démarrage dans {self.countdown_value}s..."
        )

    def _tick_countdown(self):

        self.countdown_value -= 1

        if self.countdown_value > 0:

            self._show_countdown()

            return

        self._stop_countdown()

        self._start_worker()

    def _stop_countdown(self):

        if self.countdown_timer is not None:

            self.countdown_timer.stop()

            self.countdown_timer = None

    def _start_worker(self):

        # Le worker est créé dans le thread graphique : « self.worker » est
        # donc toujours disponible pour une demande d'arrêt immédiate.
        self.worker = MacroWorker(copy.deepcopy(self.actions))

        self.worker.status.connect(self.update_execution_status)
        self.worker.finished.connect(self.execution_finished)

        self.execution_label.setText("Exécution...")

        self.worker_thread = threading.Thread(
            target=self.worker.run,
            daemon=True,
        )

        self.worker_thread.start()

    def update_execution_status(self, message):

        self.execution_label.setText(message)

    def execution_finished(self, success, message):

        self.is_running = False

        self.worker = None
        self.worker_thread = None

        self.btn_execute.setText("▶ Exécuter")

        self.set_editing_enabled(True)

        self.execution_label.setText("Prêt")

        if success:
            self.statusBar().showMessage(message, 5000)

        else:
            QMessageBox.warning(self, "Exécution", message)

    def stop_macro(self):

        if not self.is_running:
            return

        if self.countdown_timer is not None:

            self._stop_countdown()

            self.is_running = False

            self.btn_execute.setText("▶ Exécuter")

            self.set_editing_enabled(True)

            self.execution_label.setText("Prêt")

            self.statusBar().showMessage("Démarrage annulé.", 3000)

            return

        if self.worker is not None:

            self.worker.stop()

            self.execution_label.setText("Arrêt demandé...")

    def set_editing_enabled(self, enabled):
        """Verrouille l'édition pendant l'exécution."""

        self.macro_tree.setEnabled(enabled)

        self.btn_record.setEnabled(enabled)

        for button in self.action_buttons.values():
            button.setEnabled(enabled)

        for button in (
            self.btn_up,
            self.btn_down,
            self.btn_edit,
            self.btn_delete,
            self.btn_copy,
            self.btn_paste,
            self.btn_group,
            self.btn_ungroup,
            self.btn_new,
            self.btn_save,
            self.btn_load,
        ):
            button.setEnabled(enabled)

    def warn_running(self):

        QMessageBox.information(
            self,
            "Exécution en cours",
            "Arrêtez la macro en cours avant de continuer "
            f"({STOP_KEY_NAME}).",
        )

    # ==========================================================
    # DIVERS
    # ==========================================================

    def show_about(self):

        QMessageBox.about(
            self,
            f"À propos de {APPLICATION_NAME}",
            f"<b>{APPLICATION_NAME}</b><br><br>"
            "Création, enregistrement et exécution de macros clavier "
            "et souris.<br><br>"
            f"Arrêt d'urgence : <b>{STOP_KEY_NAME}</b>, ou placez la souris "
            "dans le coin haut-gauche de l'écran.<br>"
            "Capture de position : <b>F8</b>.<br>"
            "Arrêt de l'enregistrement : <b>F9</b>.<br><br>"
            f"{describe_screens()}<br><br>"
            f"Les macros sont enregistrées dans :<br>{macro.DATA_DIR}"
        )

    def closeEvent(self, event):

        if self.is_running:

            self.stop_macro()

            if self.worker_thread is not None:
                self.worker_thread.join(timeout=2.0)

        if not self.confirm_discard():

            event.ignore()

            return

        self.stop_hotkey.stop()

        event.accept()
