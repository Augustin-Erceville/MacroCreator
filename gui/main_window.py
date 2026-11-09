"""Fenêtre principale de Macro Creator.

L'éditeur présente la macro comme un enchaînement de blocs reliés
verticalement (voir `gui.flow`). Pendant l'exécution, le bloc en cours est
mis en évidence et, s'il s'agit d'une attente, le temps restant avant
l'action suivante est décompté.
"""

import copy
import os
import threading

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import macro
from core.executor import MacroWorker
from core.hotkeys import STOP_KEY_NAME, GlobalHotkey
from gui import dialogs, theme
from gui.flow import FlowCanvas

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


def format_seconds(value):
    """Durée lisible : « 0,8 s », « 12,4 s », « 1 min 05 »."""

    if value >= 60:

        minutes = int(value // 60)

        seconds = value - minutes * 60

        return f"{minutes} min {seconds:04.1f}".replace(".", ",")

    return f"{value:.1f} s".replace(".", ",")


# ==============================================================
# FENETRE
# ==============================================================

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

        self.settings = QSettings("MacroCreator", "MacroCreator")

        self.theme_name = self.settings.value(
            "theme",
            theme.DEFAULT_PALETTE,
        )

        theme.apply_theme(
            QApplication.instance(),
            self.theme_name,
        )

        self.resize(1240, 860)

        self.setup_ui()
        self.setup_menu()
        self.connect_signals()
        self.setup_hotkey()

        self.refresh()

    # ==========================================================
    # INTERFACE
    # ==========================================================

    def setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        main_layout.setContentsMargins(14, 12, 14, 12)

        main_layout.setSpacing(12)

        main_layout.addWidget(self._build_header())

        content_layout = QHBoxLayout()

        content_layout.setSpacing(12)

        content_layout.addWidget(self._build_palette(), 0)
        content_layout.addWidget(self._build_canvas_panel(), 1)

        main_layout.addLayout(content_layout, 1)

        main_layout.addWidget(self._build_execution_card())

        self.statusBar().showMessage("Prêt")

    def _build_header(self):

        header = QFrame()

        header.setObjectName("header")

        layout = QHBoxLayout(header)

        layout.setContentsMargins(16, 10, 12, 10)

        layout.setSpacing(12)

        title = QLabel(APPLICATION_NAME)

        title.setObjectName("appTitle")

        layout.addWidget(title)

        self.macro_label = QLabel()

        self.macro_label.setObjectName("macroName")

        layout.addWidget(self.macro_label)

        layout.addStretch()

        self.btn_new = QPushButton("Nouveau")
        self.btn_load = QPushButton("Ouvrir")
        self.btn_save = QPushButton("Enregistrer")

        for button in (self.btn_new, self.btn_load, self.btn_save):

            button.setObjectName("compact")

            layout.addWidget(button)

        return header

    def _build_palette(self):

        panel = QFrame()

        panel.setObjectName("card")

        panel.setFixedWidth(248)

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(12, 12, 12, 12)

        layout.setSpacing(8)

        self.btn_record = QPushButton("● Enregistrer mes gestes")

        self.btn_record.setObjectName("record")

        layout.addWidget(self.btn_record)

        label = QLabel("BLOCS")

        label.setObjectName("sectionTitle")

        layout.addWidget(label)

        self.action_buttons = {}

        for action_type in macro.ACTION_TYPES:

            button = QPushButton(
                f"  {macro.ACTION_LABELS.get(action_type, action_type)}"
            )

            button.setIcon(theme.action_icon(action_type))

            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.setToolTip(macro.ACTION_SUMMARIES.get(action_type, ""))

            layout.addWidget(button)

            self.action_buttons[action_type] = button

        layout.addSpacing(6)

        self.insertion_label = QLabel()

        self.insertion_label.setObjectName("hint")

        self.insertion_label.setWordWrap(True)

        layout.addWidget(self.insertion_label)

        layout.addStretch()

        return panel

    def _build_canvas_panel(self):

        panel = QWidget()

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(8)

        self.canvas = FlowCanvas()

        layout.addWidget(self.canvas, 1)

        toolbar = QHBoxLayout()

        toolbar.setSpacing(6)

        self.btn_up = QPushButton("↑ Monter")
        self.btn_down = QPushButton("↓ Descendre")
        self.btn_edit = QPushButton("Modifier")
        self.btn_delete = QPushButton("Supprimer")
        self.btn_copy = QPushButton("Copier")
        self.btn_paste = QPushButton("Coller")
        self.btn_group = QPushButton("Grouper en boucle")
        self.btn_ungroup = QPushButton("Dégrouper")

        for button in (
            self.btn_up,
            self.btn_down,
            self.btn_edit,
            self.btn_delete,
            self.btn_copy,
            self.btn_paste,
            self.btn_group,
            self.btn_ungroup,
        ):

            button.setObjectName("compact")

            toolbar.addWidget(button)

        layout.addLayout(toolbar)

        return panel

    def _build_execution_card(self):

        card = QFrame()

        card.setObjectName("card")

        layout = QHBoxLayout(card)

        layout.setContentsMargins(16, 12, 16, 12)

        layout.setSpacing(20)

        # --- Action en cours ---

        state = QVBoxLayout()

        state.setSpacing(4)

        state_title = QLabel("ACTION EN COURS")

        state_title.setObjectName("sectionTitle")

        state.addWidget(state_title)

        current_row = QHBoxLayout()

        current_row.setSpacing(10)

        self.current_icon = QLabel()

        self.current_icon.setFixedSize(26, 26)

        current_row.addWidget(self.current_icon)

        self.current_label = QLabel("Prêt")

        self.current_label.setObjectName("currentAction")

        current_row.addWidget(self.current_label, 1)

        state.addLayout(current_row)

        self.overall_progress = QProgressBar()

        self.overall_progress.setTextVisible(False)

        self.overall_progress.setFixedHeight(8)

        state.addWidget(self.overall_progress)

        self.step_label = QLabel()

        self.step_label.setObjectName("stepCounter")

        state.addWidget(self.step_label)

        layout.addLayout(state, 1)

        # --- Décompte de l'attente ---

        self.countdown_panel = QWidget()

        countdown_layout = QVBoxLayout(self.countdown_panel)

        countdown_layout.setContentsMargins(0, 0, 0, 0)

        countdown_layout.setSpacing(4)

        countdown_title = QLabel("PROCHAINE ACTION DANS")

        countdown_title.setObjectName("sectionTitle")

        countdown_layout.addWidget(countdown_title)

        self.countdown_label = QLabel("—")

        self.countdown_label.setObjectName("countdown")

        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        countdown_layout.addWidget(self.countdown_label)

        self.wait_progress = QProgressBar()

        self.wait_progress.setObjectName("wait")

        self.wait_progress.setTextVisible(False)

        self.wait_progress.setFixedHeight(8)

        self.wait_progress.setFixedWidth(190)

        countdown_layout.addWidget(self.wait_progress)

        layout.addWidget(self.countdown_panel)

        # --- Commandes ---

        controls = QVBoxLayout()

        controls.setSpacing(6)

        delay_row = QHBoxLayout()

        delay_row.setSpacing(6)

        delay_row.addStretch()

        delay_label = QLabel("Démarrer dans")

        delay_label.setObjectName("hint")

        delay_row.addWidget(delay_label)

        self.delay_input = QSpinBox()

        self.delay_input.setRange(0, 60)
        self.delay_input.setValue(DEFAULT_START_DELAY)
        self.delay_input.setSuffix(" s")
        self.delay_input.setFixedWidth(78)

        delay_row.addWidget(self.delay_input)

        controls.addLayout(delay_row)

        self.btn_execute = QPushButton("▶  Exécuter")

        self.btn_execute.setObjectName("primary")

        self.btn_execute.setMinimumWidth(170)

        self.btn_execute.setCursor(Qt.CursorShape.PointingHandCursor)

        controls.addWidget(self.btn_execute)

        layout.addLayout(controls)

        return card

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

        self.act_add = QAction("Ajouter un bloc...", self)
        self.act_add.setShortcut(QKeySequence("Ctrl+B"))

        self.act_copy = QAction("Copier le bloc", self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)

        self.act_paste = QAction("Coller le bloc", self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)

        self.act_delete = QAction("Supprimer le bloc", self)
        self.act_delete.setShortcut(QKeySequence.StandardKey.Delete)

        for action in (
            self.act_add,
            self.act_copy,
            self.act_paste,
            self.act_delete,
        ):
            edit_menu.addAction(action)

        view_menu = self.menuBar().addMenu("&Affichage")

        self.theme_group = QActionGroup(self)

        self.theme_actions = {}

        for name, label in (("dark", "Thème sombre"), ("light", "Thème clair")):

            action = QAction(label, self)

            action.setCheckable(True)

            action.setChecked(name == self.theme_name)

            action.triggered.connect(
                lambda _checked=False, value=name: self.apply_theme(value)
            )

            self.theme_group.addAction(action)

            view_menu.addAction(action)

            self.theme_actions[name] = action

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
        self.btn_ungroup.clicked.connect(self.ungroup_block)

        self.btn_new.clicked.connect(self.new_macro)
        self.btn_save.clicked.connect(self.save_macro)
        self.btn_load.clicked.connect(self.load_macro)
        self.btn_execute.clicked.connect(self.toggle_execution)

        self.canvas.insert_requested.connect(self.insert_at)
        self.canvas.edit_requested.connect(self.edit_path)
        self.canvas.delete_requested.connect(self.delete_path)
        self.canvas.selection_changed.connect(self.update_insertion_hint)

        self.act_new.triggered.connect(self.new_macro)
        self.act_open.triggered.connect(self.load_macro)
        self.act_save.triggered.connect(self.save_macro)
        self.act_save_as.triggered.connect(self.save_macro_as)
        self.act_rename.triggered.connect(self.rename_macro)
        self.act_quit.triggered.connect(self.close)

        self.act_add.triggered.connect(self.add_block_from_picker)
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

    def apply_theme(self, name):

        self.theme_name = name

        self.settings.setValue("theme", name)

        theme.apply_theme(QApplication.instance(), name)

        action = self.theme_actions.get(name)

        if action is not None:
            action.setChecked(True)

        # Les pictogrammes sont redessinés avec la nouvelle palette.
        for action_type, button in self.action_buttons.items():
            button.setIcon(theme.action_icon(action_type))

        self.canvas.rebuild()

    # ==========================================================
    # CANEVAS
    # ==========================================================

    def refresh(self, select_path=None):
        """Reconstruit le canevas à partir du modèle."""

        self.canvas.set_actions(self.actions)

        if select_path is not None:
            self.canvas.select_path(select_path)

        self.update_insertion_hint()

        self.update_title()

        # Le nombre d'actions à exécuter suit les modifications du modèle.
        if not self.is_running:
            self.set_idle_state()

    def selected_path(self):

        return self.canvas.selected_path()

    def selected_paths(self):

        return self.canvas.selected_paths()

    def update_insertion_hint(self):

        path = self.selected_path()

        if path is None:

            self.insertion_label.setText(
                "Aucun bloc sélectionné : un nouveau bloc est ajouté à la "
                "fin. Utilisez « + » pour insérer à un endroit précis."
            )

            return

        action = macro.get_action(self.actions, path)

        label = macro.ACTION_LABELS.get(action.get("type"), "bloc")

        self.insertion_label.setText(
            f"« {label} » sélectionné : un nouveau bloc sera inséré juste "
            "après. Pour remplir une boucle ou une branche, utilisez le "
            "« + » qu'elle contient."
        )

    # ==========================================================
    # AJOUT ET INSERTION
    # ==========================================================

    def block_execution_guard(self):
        """Empêche toute modification pendant l'exécution."""

        if self.is_running:

            self.warn_running()

            return True

        return False

    def insert_actions(self, new_actions):
        """Insère des blocs après la sélection, ou à la fin de la macro."""

        if not new_actions or self.block_execution_guard():
            return

        path = self.selected_path()

        if path is None:

            self.actions.extend(new_actions)

            target = [len(self.actions) - 1]

        else:

            container, index = macro.get_container(self.actions, path)

            for offset, action in enumerate(new_actions, start=1):
                container.insert(index + offset, action)

            target = path[:-1] + [index + len(new_actions)]

        self.mark_modified()

        self.refresh(target)

    def insert_at(self, branch_path, index, new_actions=None):
        """Insère à une position précise (bouton « + » du canevas)."""

        if self.block_execution_guard():
            return

        if new_actions is None:

            action_type = dialogs.BlockPicker.run(self)

            if action_type is None:
                return

            action = dialogs.ACTION_DIALOGS[action_type].run(self)

            if action is None:
                return

            new_actions = [action]

        try:
            container = macro.get_branch(self.actions, list(branch_path))

        except macro.MacroError as error:

            QMessageBox.warning(self, "Insertion", str(error))

            return

        for offset, action in enumerate(new_actions):
            container.insert(index + offset, action)

        self.mark_modified()

        self.refresh(list(branch_path) + [index + len(new_actions) - 1])

        self.statusBar().showMessage("Bloc inséré.", 3000)

    def add_block_from_picker(self):

        if self.block_execution_guard():
            return

        action_type = dialogs.BlockPicker.run(self)

        if action_type is None:
            return

        self.add_action(action_type)

    def add_action(self, action_type):

        if self.block_execution_guard():
            return

        dialog_class = dialogs.ACTION_DIALOGS[action_type]

        action = dialog_class.run(self)

        if action is None:
            return

        self.insert_actions([action])

        self.statusBar().showMessage("Bloc ajouté.", 3000)

    def record_macro(self):

        if self.block_execution_guard():
            return

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

    def edit_path(self, path):

        if self.block_execution_guard():
            return

        try:
            container, index = macro.get_container(self.actions, list(path))

        except macro.MacroError:
            return

        action = container[index]

        dialog_class = dialogs.ACTION_DIALOGS.get(action["type"])

        if dialog_class is None:
            return

        updated = dialog_class.run(self, action)

        if updated is None:
            return

        container[index] = updated

        self.mark_modified()

        self.refresh(list(path))

    def edit_selected_action(self):

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Modification")

            return

        self.edit_path(path)

    def delete_path(self, path):

        if self.block_execution_guard():
            return

        self.delete_paths([list(path)])

    def delete_selected_action(self):

        paths = self.selected_paths()

        if not paths:

            self.warn_no_selection("Suppression")

            return

        self.delete_paths(paths)

    def delete_paths(self, paths):

        if self.block_execution_guard():
            return

        contained = any(
            macro.get_action(self.actions, path).get("type")
            in macro.CONTAINER_TYPES
            for path in paths
        )

        message = f"Voulez-vous vraiment supprimer {len(paths)} bloc(s) ?"

        if contained:
            message += "\nLe contenu des blocs supprimés sera perdu."

        answer = QMessageBox.question(
            self,
            "Supprimer",
            message,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        # Suppression de la fin vers le début : les index restent valides.
        for path in sorted(
            paths,
            key=lambda item: (
                len(item),
                [token for token in item if isinstance(token, int)],
            ),
            reverse=True,
        ):

            try:
                container, index = macro.get_container(self.actions, path)

            except macro.MacroError:
                # Bloc déjà supprimé avec son conteneur.
                continue

            del container[index]

        self.canvas.clear_selection()

        self.mark_modified()

        self.refresh()

    def move_action_up(self):

        self._move_action(-1)

    def move_action_down(self):

        self._move_action(1)

    def _move_action(self, offset):

        if self.block_execution_guard():
            return

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Déplacement")

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

        self.canvas.clear_selection()

        self.refresh(path[:-1] + [target])

    def copy_selected_action(self):

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Copier")

            return

        self.copied_action = copy.deepcopy(
            macro.get_action(self.actions, path)
        )

        self.statusBar().showMessage("Bloc copié.", 3000)

    def paste_action(self):

        if self.copied_action is None:

            QMessageBox.information(
                self,
                "Coller",
                "Aucun bloc n'a été copié.",
            )

            return

        self.insert_actions([copy.deepcopy(self.copied_action)])

        self.statusBar().showMessage("Bloc collé.", 3000)

    # ==========================================================
    # BOUCLES ET CONDITIONS
    # ==========================================================

    def group_into_loop(self):

        if self.block_execution_guard():
            return

        paths = self.selected_paths()

        if not paths:

            QMessageBox.information(
                self,
                "Boucle",
                "Sélectionnez les blocs à répéter "
                "(Ctrl+clic pour en choisir plusieurs).",
            )

            return

        parent = paths[0][:-1]

        if any(path[:-1] != parent for path in paths):

            QMessageBox.warning(
                self,
                "Boucle",
                "Les blocs sélectionnés doivent se trouver au même niveau.",
            )

            return

        indexes = [path[-1] for path in paths]

        if indexes != list(range(indexes[0], indexes[-1] + 1)):

            QMessageBox.warning(
                self,
                "Boucle",
                "Les blocs sélectionnés doivent se suivre.",
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

        self.canvas.clear_selection()

        self.mark_modified()

        self.refresh(parent + [indexes[0]])

    def ungroup_block(self):
        """Remplace une boucle ou une condition par son contenu."""

        if self.block_execution_guard():
            return

        path = self.selected_path()

        if path is None:

            self.warn_no_selection("Dégrouper")

            return

        container, index = macro.get_container(self.actions, path)

        action = container[index]

        action_type = action.get("type")

        if action_type not in macro.CONTAINER_TYPES:

            QMessageBox.information(
                self,
                "Dégrouper",
                "Sélectionnez une boucle ou une condition.",
            )

            return

        if action_type == "loop":

            inner = copy.deepcopy(action.get("actions", []))

            note = (
                "Boucle dégroupée : les répétitions sont perdues, les "
                "blocs sont conservés."
            )

        else:

            branch = self.ask_branch_to_keep(action)

            if branch is None:
                return

            inner = copy.deepcopy(action.get(branch, []))

            note = (
                f"Condition dégroupée : seule la branche "
                f"« {macro.BRANCH_LABELS[branch]} » est conservée."
            )

        container[index:index + 1] = inner

        self.canvas.clear_selection()

        self.mark_modified()

        self.refresh()

        self.statusBar().showMessage(note, 6000)

    def ask_branch_to_keep(self, action):
        """Demande quelle branche conserver en dégroupant une condition."""

        then_count = len(action.get("then", []))

        else_count = len(action.get("else", []))

        box = QMessageBox(self)

        box.setWindowTitle("Dégrouper la condition")

        box.setText(
            "Dégrouper une condition ne garde qu'une seule branche.\n"
            "Laquelle voulez-vous conserver ?"
        )

        then_button = box.addButton(
            f"Alors ({then_count} bloc(s))",
            QMessageBox.ButtonRole.AcceptRole,
        )

        else_button = box.addButton(
            f"Sinon ({else_count} bloc(s))",
            QMessageBox.ButtonRole.AcceptRole,
        )

        box.addButton(QMessageBox.StandardButton.Cancel)

        box.exec()

        clicked = box.clickedButton()

        if clicked is then_button:
            return "then"

        if clicked is else_button:
            return "else"

        return None

    def warn_no_selection(self, title):

        QMessageBox.information(
            self,
            title,
            "Sélectionnez d'abord un bloc dans le canevas.",
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

        count = macro.count_actions(self.actions)

        self.macro_label.setText(
            f"{self.macro_name}{marker}  ·  {count} bloc(s)  ·  {location}"
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

        if self.block_execution_guard():
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

        self.canvas.clear_selection()

        self.refresh()

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

        if self.block_execution_guard():
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

        self.canvas.clear_selection()

        self.refresh()

        self.statusBar().showMessage(
            f"Macro chargée : {macro.count_actions(actions)} bloc(s).",
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
                "La macro ne contient aucun bloc.",
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

        self.btn_execute.setText("■  Arrêter")

        self.btn_execute.setObjectName("danger")

        theme.repolish_widget(self.btn_execute)

        self.set_editing_enabled(False)

        self.overall_progress.setValue(0)

        self.countdown_value = self.delay_input.value()

        if self.countdown_value > 0:

            self.countdown_timer = QTimer(self)

            self.countdown_timer.timeout.connect(self._tick_countdown)

            self._show_start_countdown()

            self.countdown_timer.start(1000)

            return

        self._start_worker()

    def check_screen_coordinates(self):
        """Prévient si des blocs visent un point hors de tout écran.

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
            "Ces blocs visent un point situé en dehors de tous les "
            f"écrans :\n\n{preview}\n\nExécuter quand même ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        return answer == QMessageBox.StandardButton.Yes

    # --- Compte à rebours avant démarrage ---

    def _show_start_countdown(self):

        self.current_label.setText("Démarrage imminent")

        self.current_icon.clear()

        self.countdown_panel.setVisible(True)

        self.countdown_label.setText(f"{self.countdown_value} s")

        self.wait_progress.setRange(0, 100)

        self.wait_progress.setValue(100)

        self.step_label.setText("Placez-vous sur la bonne fenêtre")

    def _tick_countdown(self):

        self.countdown_value -= 1

        if self.countdown_value > 0:

            self._show_start_countdown()

            return

        self._stop_countdown()

        self._start_worker()

    def _stop_countdown(self):

        if self.countdown_timer is not None:

            self.countdown_timer.stop()

            self.countdown_timer = None

    # --- Worker ---

    def _start_worker(self):

        # Le worker est créé dans le thread graphique : « self.worker » est
        # donc toujours disponible pour une demande d'arrêt immédiate.
        self.worker = MacroWorker(copy.deepcopy(self.actions))

        self.worker.action_started.connect(self.on_action_started)
        self.worker.progress.connect(self.on_progress)
        self.worker.wait_progress.connect(self.on_wait_progress)
        self.worker.status.connect(self.on_status)
        self.worker.finished.connect(self.execution_finished)

        self.estimated = macro.has_conditions(self.actions)

        self.current_label.setText("Exécution...")

        self.countdown_panel.setVisible(False)

        self.worker_thread = threading.Thread(
            target=self.worker.run,
            daemon=True,
        )

        self.worker_thread.start()

    def on_action_started(self, path, action):
        """Met en évidence le bloc courant et affiche son libellé."""

        self.canvas.set_running_path(path)

        action_type = action.get("type")

        self.current_icon.setPixmap(
            theme.action_icon(action_type).pixmap(26, 26)
        )

        self.current_label.setText(macro.action_body(action))

        # Le décompte n'a de sens que pour une attente ; il sera réaffiché
        # par wait_progress dès la première mesure.
        if action_type != "wait":
            self.countdown_panel.setVisible(False)

    def on_progress(self, done, total):

        self.overall_progress.setRange(0, max(total, 1))

        self.overall_progress.setValue(min(done, total))

        prefix = "≈ " if getattr(self, "estimated", False) else ""

        self.step_label.setText(f"{prefix}action {done} / {total}")

    def on_wait_progress(self, remaining, total):
        """Décompte avant l'action suivante, pendant une attente."""

        if remaining <= 0:

            self.countdown_panel.setVisible(False)

            return

        self.countdown_panel.setVisible(True)

        self.countdown_label.setText(format_seconds(remaining))

        self.wait_progress.setRange(0, 1000)

        self.wait_progress.setValue(
            int(1000 * remaining / total) if total > 0 else 0
        )

    def on_status(self, message):

        self.statusBar().showMessage(message)

    def execution_finished(self, success, message):

        self.is_running = False

        self.worker = None
        self.worker_thread = None

        self.btn_execute.setText("▶  Exécuter")

        self.btn_execute.setObjectName("primary")

        theme.repolish_widget(self.btn_execute)

        self.set_editing_enabled(True)

        self.canvas.clear_running()

        self.set_idle_state()

        if success:
            self.statusBar().showMessage(message, 5000)

        else:
            QMessageBox.warning(self, "Exécution", message)

    def set_idle_state(self):

        self.current_icon.clear()

        self.current_label.setText("Prêt")

        self.countdown_panel.setVisible(False)

        self.overall_progress.setValue(0)

        self.step_label.setText(
            f"{macro.count_steps(self.actions)} action(s) à exécuter"
        )

    def stop_macro(self):

        if not self.is_running:
            return

        if self.countdown_timer is not None:

            self._stop_countdown()

            self.is_running = False

            self.btn_execute.setText("▶  Exécuter")

            self.btn_execute.setObjectName("primary")

            theme.repolish_widget(self.btn_execute)

            self.set_editing_enabled(True)

            self.set_idle_state()

            self.statusBar().showMessage("Démarrage annulé.", 3000)

            return

        if self.worker is not None:

            self.worker.stop()

            self.current_label.setText("Arrêt demandé...")

    def set_editing_enabled(self, enabled):
        """Verrouille l'édition pendant l'exécution.

        Le canevas reste actif : c'est lui qui montre le bloc en cours.
        Les modifications sont bloquées en amont par les boutons désactivés
        et par `block_execution_guard`.
        """

        self.btn_record.setEnabled(enabled)

        self.delay_input.setEnabled(enabled)

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
            "Arrêtez la macro en cours avant de modifier la macro "
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

            if self.worker is not None:
                self.worker.stop()

            self.is_running = False

            if self.worker_thread is not None:
                self.worker_thread.join(timeout=2.0)

        if not self.confirm_discard():

            event.ignore()

            return

        self.stop_hotkey.stop()

        event.accept()
