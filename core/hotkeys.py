"""Raccourcis clavier globaux (actifs même quand la fenêtre n'a pas le focus).

Indispensable ici : pendant l'exécution d'une macro, PyAutoGUI contrôle la
souris et le clavier, il est donc impossible de cliquer sur « Arrêter ».
"""

from PySide6.QtCore import QObject, Signal

try:
    from pynput import keyboard

    PYNPUT_AVAILABLE = True

except Exception:  # noqa: BLE001 - pynput absent ou sans backend
    keyboard = None

    PYNPUT_AVAILABLE = False


# Touche d'arrêt d'urgence
STOP_KEY_NAME = "F12"


class GlobalHotkey(QObject):
    """Écoute une touche unique dans tout le système.

    Le signal est émis depuis le thread d'écoute ; comme cet objet vit dans
    le thread graphique, Qt met automatiquement l'appel en file d'attente.
    """

    triggered = Signal()

    def __init__(self, key_name=STOP_KEY_NAME, parent=None):

        super().__init__(parent)

        self.key_name = key_name
        self._listener = None

    @property
    def available(self):
        return PYNPUT_AVAILABLE

    def start(self):
        """Démarre l'écoute. Retourne True si le raccourci est actif."""

        if not PYNPUT_AVAILABLE or self._listener is not None:
            return self._listener is not None

        target = getattr(keyboard.Key, self.key_name.lower(), None)

        if target is None:
            return False

        def on_press(key):

            if key == target:
                self.triggered.emit()

        try:

            self._listener = keyboard.Listener(on_press=on_press)

            self._listener.daemon = True

            self._listener.start()

        except Exception:  # noqa: BLE001 - écoute clavier refusée par l'OS

            self._listener = None

            return False

        return True

    def stop(self):

        if self._listener is not None:

            self._listener.stop()

            self._listener = None
