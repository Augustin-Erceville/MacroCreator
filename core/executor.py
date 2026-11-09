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

from core import conditions, macro

# Sécurité : coin haut-gauche de l'écran = arrêt d'urgence PyAutoGUI.
pyautogui.FAILSAFE = True

# Pas de pause implicite : les temporisations sont gérées par la macro.
pyautogui.PAUSE = 0

# Granularité des attentes : compromis entre précision et réactivité
# de la demande d'arrêt.
SLEEP_STEP = 0.05

# Fréquence de rafraîchissement du décompte affiché pendant une attente.
COUNTDOWN_STEP = 0.05


class MacroWorker(QObject):
    """Exécute une liste d'actions ; interruptible à tout moment."""

    # Action sur le point d'être exécutée : (chemin dans l'arbre, action)
    action_started = Signal(list, dict)

    # Avancement : (étapes terminées, étapes totales)
    progress = Signal(int, int)

    # Décompte d'une attente : (secondes restantes, durée totale)
    wait_progress = Signal(float, float)

    # Message court d'état
    status = Signal(str)

    finished = Signal(bool, str)  # (succès, message)

    def __init__(self, actions):

        super().__init__()

        self.actions = actions

        self.total_steps = macro.count_steps(actions)

        self.completed_steps = 0

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

        self.progress.emit(0, self.total_steps)

        try:

            self.execute_actions(self.actions, [])

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

    def execute_actions(self, actions, path):

        for index, action in enumerate(actions):

            if self.stop_requested:
                return

            self.execute_action(action, path + [index])

    # ----------------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------------

    def execute_action(self, action, path):

        action_type = action["type"]

        handler = getattr(self, f"_run_{action_type}", None)

        if handler is None:

            raise ValueError(
                f"Type d'action inconnu : {action_type!r}"
            )

        # L'interface met en évidence l'action dans l'arbre et affiche son
        # libellé avant même qu'elle ne commence.
        self.action_started.emit(list(path), dict(action))

        handler(action, path)

        # Une boucle n'est pas une étape : seul son contenu en est une.
        if action_type != "loop":

            self.completed_steps += 1

            self.progress.emit(self.completed_steps, self.total_steps)

    def _run_wait(self, action, path):

        duration = action["duration"]

        maximum = action.get("duration_max")

        if maximum:
            duration = random.uniform(
                min(duration, maximum),
                max(duration, maximum),
            )

        self.status.emit(f"Attente de {duration:.2f}s")

        self.interruptible_sleep(duration, report=True)

    def _run_move(self, action, path):

        self.status.emit(
            f"Souris → X:{action['x']} Y:{action['y']}"
        )

        pyautogui.moveTo(
            action["x"],
            action["y"],
            duration=action["duration"],
        )

    def _run_click(self, action, path):

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

    def _run_drag(self, action, path):

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

    def _run_scroll(self, action, path):

        self.status.emit(
            f"Molette → {action['amount']} cran(s)"
        )

        if "x" in action and "y" in action:
            pyautogui.moveTo(action["x"], action["y"])

        # PyAutoGUI compte en « clics » de molette (120 unités sous Windows).
        pyautogui.scroll(action["amount"] * 100)

    def _run_text(self, action, path):

        self.status.emit("Saisie du texte")

        pyautogui.write(
            action["text"],
            interval=action.get("interval", 0.01),
        )

    def _run_key(self, action, path):

        self.status.emit(f"Touche → {action['key']}")

        modifiers = action.get("modifiers", [])

        for modifier in modifiers:
            pyautogui.keyDown(modifier)

        try:
            pyautogui.press(action["key"])

        finally:

            for modifier in reversed(modifiers):
                pyautogui.keyUp(modifier)

    def _run_condition(self, action, path):

        result = conditions.evaluate(action.get("test", {}))

        branch = "then" if result else "else"

        self.status.emit(
            f"Condition {'vraie' if result else 'fausse'} → "
            f"{macro.BRANCH_LABELS[branch]}"
            f"{' · ' + result.detail if result.detail else ''}"
        )

        self.execute_actions(action.get(branch, []), path + [branch])

    def _run_loop(self, action, path):

        repetitions = action["repetitions"]

        for iteration in range(repetitions):

            if self.stop_requested:
                return

            self.status.emit(
                f"Boucle : passage {iteration + 1}/{repetitions}"
            )

            self.execute_actions(action["actions"], path)

    # ----------------------------------------------------------
    # OUTILS
    # ----------------------------------------------------------

    def interruptible_sleep(self, duration, report=False):
        """Attend `duration` secondes en surveillant la demande d'arrêt.

        Avec `report`, le temps restant est émis régulièrement pour
        alimenter le décompte affiché par l'interface.
        """

        end_time = time.monotonic() + duration

        step = COUNTDOWN_STEP if report else SLEEP_STEP

        while True:

            remaining = end_time - time.monotonic()

            if remaining <= 0:

                if report:
                    self.wait_progress.emit(0.0, duration)

                return

            if report:
                self.wait_progress.emit(remaining, duration)

            if self._stop_event.wait(min(step, remaining)):
                return
