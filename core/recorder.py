"""Enregistrement en temps réel des actions souris et clavier.

Capture les événements du système avec pynput et les convertit en actions
de macro (clics, molette, texte, touches, attentes).
"""

import threading
import time

from PySide6.QtCore import QObject, Signal

from core import macro

try:
    from pynput import keyboard, mouse

    PYNPUT_AVAILABLE = True

except Exception:  # noqa: BLE001 - pynput absent ou sans backend
    keyboard = None
    mouse = None

    PYNPUT_AVAILABLE = False


# Touche qui met fin à l'enregistrement
STOP_KEY_NAME = "F9"

# En dessous de ce seuil, on n'insère pas d'action d'attente (secondes)
MIN_WAIT = 0.05

# Deux clics au même endroit dans cet intervalle = double clic
DOUBLE_CLICK_DELAY = 0.4

# Distance maximale entre deux clics pour les considérer au même endroit
DOUBLE_CLICK_RADIUS = 5

# Intervalle minimal entre deux mouvements enregistrés
MOVE_SAMPLING = 0.15

# Correspondance pynput -> pyautogui pour les touches spéciales
SPECIAL_KEYS = {
    "enter": "enter",
    "esc": "esc",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "page_up": "pageup",
    "page_down": "pagedown",
    "insert": "insert",
}

MODIFIER_KEYS = {
    "ctrl": "ctrl",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "shift": "shift",
    "shift_l": "shift",
    "shift_r": "shift",
    "alt": "alt",
    "alt_l": "alt",
    "alt_gr": "alt",
    "alt_r": "alt",
    "cmd": "win",
    "cmd_l": "win",
    "cmd_r": "win",
}

BUTTON_NAMES = {
    "left": "left",
    "right": "right",
    "middle": "middle",
}


class Recorder(QObject):
    """Enregistre les actions de l'utilisateur jusqu'à l'appui sur F9."""

    action_added = Signal(str)   # description de la dernière action
    stopped = Signal()

    def __init__(self, record_moves=False, parent=None):

        super().__init__(parent)

        self.record_moves = record_moves

        self.actions = []

        self._lock = threading.Lock()
        self._keyboard_listener = None
        self._mouse_listener = None
        self._running = False

        self._last_event_time = None
        self._last_move_time = 0.0
        self._text_buffer = []
        self._modifiers = set()
        self._last_click = None  # (x, y, button, time, index)

    # ----------------------------------------------------------
    # CONTROLE
    # ----------------------------------------------------------

    @property
    def available(self):
        return PYNPUT_AVAILABLE

    @property
    def running(self):
        return self._running

    def start(self):
        """Démarre l'écoute. Retourne True en cas de succès."""

        if not PYNPUT_AVAILABLE or self._running:
            return self._running

        self.actions = []

        self._last_event_time = None
        self._last_move_time = 0.0
        self._text_buffer = []
        self._modifiers = set()
        self._last_click = None

        try:

            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )

            self._mouse_listener = mouse.Listener(
                on_click=self._on_click,
                on_scroll=self._on_scroll,
                on_move=self._on_move if self.record_moves else None,
            )

            self._keyboard_listener.daemon = True
            self._mouse_listener.daemon = True

            self._keyboard_listener.start()
            self._mouse_listener.start()

        except Exception:  # noqa: BLE001 - écoute refusée par l'OS

            self._shutdown_listeners()

            return False

        self._running = True

        return True

    def stop(self):
        """Arrête l'écoute et finalise la liste d'actions."""

        if not self._running:
            return self.actions

        self._running = False

        self._shutdown_listeners()

        with self._lock:
            self._flush_text()

        self.stopped.emit()

        return self.actions

    def _shutdown_listeners(self):

        for listener in (self._keyboard_listener, self._mouse_listener):

            if listener is not None:

                try:
                    listener.stop()
                except Exception:  # noqa: BLE001
                    pass

        self._keyboard_listener = None
        self._mouse_listener = None

    # ----------------------------------------------------------
    # CONSTRUCTION DES ACTIONS
    # ----------------------------------------------------------

    def _append(self, action, with_delay=True):
        """Ajoute une action, précédée de l'attente réellement observée."""

        now = time.monotonic()

        if with_delay and self._last_event_time is not None:

            delay = now - self._last_event_time

            if delay >= MIN_WAIT:

                wait = macro.make_wait(round(delay, 2))

                self.actions.append(wait)

                self.action_added.emit(macro.describe_action(wait))

        self._last_event_time = now

        self.actions.append(action)

        self.action_added.emit(macro.describe_action(action))

    def _flush_text(self):
        """Transforme le tampon de frappe en une action « texte »."""

        if not self._text_buffer:
            return

        text = "".join(self._text_buffer)

        self._text_buffer = []

        self._append(macro.make_text(text))

    # ----------------------------------------------------------
    # CLAVIER
    # ----------------------------------------------------------

    def _on_key_press(self, key):

        name = self._key_name(key)

        # La touche d'arrêt n'est jamais enregistrée.
        if name == STOP_KEY_NAME.lower():

            self.stop()

            return False

        with self._lock:

            if name in MODIFIER_KEYS:

                self._modifiers.add(MODIFIER_KEYS[name])

                return

            character = getattr(key, "char", None)

            active = self._modifiers - {"shift"}

            # Frappe de texte ordinaire : on accumule.
            if character and not active and character.isprintable():

                if not self._text_buffer:
                    # Le délai est mesuré au début de la saisie.
                    self._start_text()

                self._text_buffer.append(character)

                return

            self._flush_text()

            pyautogui_key = self._to_pyautogui_key(key, name)

            if pyautogui_key is None:
                return

            self._append(
                macro.make_key(
                    pyautogui_key,
                    sorted(self._modifiers),
                )
            )

    def _on_key_release(self, key):

        name = self._key_name(key)

        with self._lock:

            if name in MODIFIER_KEYS:
                self._modifiers.discard(MODIFIER_KEYS[name])

    def _start_text(self):
        """Mémorise l'instant du début de saisie pour l'attente précédente."""

        now = time.monotonic()

        if self._last_event_time is not None:

            delay = now - self._last_event_time

            if delay >= MIN_WAIT:

                wait = macro.make_wait(round(delay, 2))

                self.actions.append(wait)

                self.action_added.emit(macro.describe_action(wait))

        self._last_event_time = now

    @staticmethod
    def _key_name(key):

        if hasattr(key, "name"):
            return key.name

        character = getattr(key, "char", None)

        return character or ""

    @staticmethod
    def _to_pyautogui_key(key, name):

        character = getattr(key, "char", None)

        if character and character.isprintable():
            return character.lower()

        if name in SPECIAL_KEYS:
            return SPECIAL_KEYS[name]

        if name and name.startswith("f") and name[1:].isdigit():
            return name

        return None

    # ----------------------------------------------------------
    # SOURIS
    # ----------------------------------------------------------

    def _on_click(self, x, y, button, pressed):

        if not pressed:
            return

        name = BUTTON_NAMES.get(button.name)

        if name is None:
            return

        with self._lock:

            self._flush_text()

            now = time.monotonic()

            previous = self._last_click

            # Fusion en double clic si le clic précédent est proche.
            if (
                previous is not None
                and previous[2] == name
                and now - previous[3] <= DOUBLE_CLICK_DELAY
                and abs(previous[0] - x) <= DOUBLE_CLICK_RADIUS
                and abs(previous[1] - y) <= DOUBLE_CLICK_RADIUS
                and previous[4] < len(self.actions)
                and self.actions[previous[4]].get("type") == "click"
            ):

                self.actions[previous[4]]["clicks"] += 1

                self._last_click = (x, y, name, now, previous[4])

                self.action_added.emit(
                    macro.describe_action(self.actions[previous[4]])
                )

                return

            self._append(macro.make_click(x, y, name, 1))

            self._last_click = (
                x,
                y,
                name,
                now,
                len(self.actions) - 1,
            )

    def _on_scroll(self, x, y, dx, dy):

        with self._lock:

            self._flush_text()

            self._append(macro.make_scroll(int(dy) or 1, x, y))

    def _on_move(self, x, y):

        now = time.monotonic()

        if now - self._last_move_time < MOVE_SAMPLING:
            return

        self._last_move_time = now

        with self._lock:

            self._flush_text()

            self._append(macro.make_move(x, y, 0.1))
