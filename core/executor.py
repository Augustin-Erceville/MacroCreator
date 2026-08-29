"""Moteur d'exécution des macros.

Le worker tourne dans un thread séparé ; il communique avec l'interface
uniquement par signaux Qt (connexion automatique en file d'attente, donc
sûre vis-à-vis du thread graphique).
"""

import random
import threading
import time

import pyautogui
from PySide6.QtCore import QObject, Signal

# Sécurité : coin haut-gauche de l'écran = arrêt d'urgence PyAutoGUI.
pyautogui.FAILSAFE = True

# Pas de pause implicite : les temporisations sont gérées par la macro.
pyautogui.PAUSE = 0

# Granularité des attentes : compromis entre précision et réactivité
# de la demande d'arrêt.
SLEEP_STEP = 0.05


class MacroWorker(QObject):
    """Exécute une liste d'actions ; interruptible à tout moment."""

    status = Signal(str)
    finished = Signal(bool, str)  # (succès, message)

    def __init__(self, actions):

        super().__init__()

        self.actions = actions
        self._stop_event = threading.Event()

    # ----------------------------------------------------------
    # CONTROLE
    # ----------------------------------------------------------

    def stop(self):
        """Demande l'arrêt ; appelable depuis n'importe quel thread."""

        self._stop_event.set()

    @property
    def stop_requested(self):
        return self._stop_event.is_set()

    # ----------------------------------------------------------
    # BOUCLE PRINCIPALE
    # ----------------------------------------------------------

    def run(self):

        try:

            self.execute_actions(self.actions)

        except pyautogui.FailSafeException:

            self.finished.emit(
                False,
                "Arrêt d'urgence : la souris a été placée dans un coin "
                "de l'écran."
            )

            return

        except Exception as error:  # noqa: BLE001 - remonté à l'interface

            self.finished.emit(
                False,
                f"Erreur pendant l'exécution : {error}"
            )

            return

        if self.stop_requested:

            self.finished.emit(True, "Macro interrompue.")

            return

        self.finished.emit(True, "Macro terminée.")

    def execute_actions(self, actions):

        for action in actions:

            if self.stop_requested:
                return

            self.execute_action(action)

    # ----------------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------------

    def execute_action(self, action):

        action_type = action["type"]

        handler = getattr(self, f"_run_{action_type}", None)

        if handler is None:

            raise ValueError(
                f"Type d'action inconnu : {action_type!r}"
            )

        handler(action)

    def _run_wait(self, action):

        duration = action["duration"]

        maximum = action.get("duration_max")

        if maximum:
            duration = random.uniform(
                min(duration, maximum),
                max(duration, maximum),
            )

        self.status.emit(f"Attente de {duration:.2f}s...")

        self.interruptible_sleep(duration)

    def _run_move(self, action):

        self.status.emit(
            f"Souris → X:{action['x']} Y:{action['y']}"
        )

        pyautogui.moveTo(
            action["x"],
            action["y"],
            duration=action["duration"],
        )

    def _run_click(self, action):

        self.status.emit(
            f"Clic → X:{action['x']} Y:{action['y']}"
        )

        pyautogui.click(
            x=action["x"],
            y=action["y"],
            clicks=action["clicks"],
            button=action["button"],
            interval=0.1,
        )

    def _run_drag(self, action):

        self.status.emit(
            f"Glisser → X:{action['x2']} Y:{action['y2']}"
        )

        pyautogui.moveTo(action["x"], action["y"])

        pyautogui.dragTo(
            action["x2"],
            action["y2"],
            duration=action["duration"],
            button=action["button"],
        )

    def _run_scroll(self, action):

        self.status.emit(
            f"Molette → {action['amount']} cran(s)"
        )

        if "x" in action and "y" in action:
            pyautogui.moveTo(action["x"], action["y"])

        # PyAutoGUI compte en « clics » de molette (120 unités sous Windows).
        pyautogui.scroll(action["amount"] * 100)

    def _run_text(self, action):

        self.status.emit("Saisie du texte...")

        pyautogui.write(
            action["text"],
            interval=action.get("interval", 0.01),
        )

    def _run_key(self, action):

        self.status.emit(f"Touche → {action['key']}")

        modifiers = action.get("modifiers", [])

        for modifier in modifiers:
            pyautogui.keyDown(modifier)

        try:
            pyautogui.press(action["key"])

        finally:

            for modifier in reversed(modifiers):
                pyautogui.keyUp(modifier)

    def _run_loop(self, action):

        repetitions = action["repetitions"]

        for iteration in range(repetitions):

            if self.stop_requested:
                return

            self.status.emit(
                f"Boucle : {iteration + 1}/{repetitions}"
            )

            self.execute_actions(action["actions"])

    # ----------------------------------------------------------
    # OUTILS
    # ----------------------------------------------------------

    def interruptible_sleep(self, duration):
        """Attend `duration` secondes en surveillant la demande d'arrêt."""

        end_time = time.monotonic() + duration

        while True:

            remaining = end_time - time.monotonic()

            if remaining <= 0:
                return

            if self._stop_event.wait(min(SLEEP_STEP, remaining)):
                return
