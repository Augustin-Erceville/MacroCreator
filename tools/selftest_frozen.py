"""Auto-test des briques sensibles, à lancer aussi bien depuis les sources
que depuis un exécutable PyInstaller.

Vérifie ce qui casse typiquement une fois l'application figée : chargement
des backends pynput, emplacement du dossier des macros, écriture sur disque
et détection des écrans.

Depuis les sources :

    python tools/selftest_frozen.py

Compilé (pour valider un build) :

    .venv\\Scripts\\pyinstaller.exe --onefile --console ^
        --hidden-import pynput.keyboard._win32 ^
        --hidden-import pynput.mouse._win32 tools/selftest_frozen.py
"""

import os
import sys

if not getattr(sys, "frozen", False):

    sys.path.insert(
        0,
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

from PySide6.QtWidgets import QApplication  # noqa: E402

from core import conditions, hotkeys, macro, recorder  # noqa: E402
from gui import theme  # noqa: E402
from gui.main_window import MainWindow, describe_screens  # noqa: E402

failures = []


def check(label, condition, detail=""):

    status = "OK " if condition else "ECHEC"

    print(f"[{status}] {label}{' : ' + detail if detail else ''}")

    if not condition:
        failures.append(label)


def main():

    print(f"gele par PyInstaller : {getattr(sys, 'frozen', False)}")
    print(f"executable           : {sys.executable}")

    application = QApplication(sys.argv)

    # --- dossier des macros ---
    data_dir = macro.ensure_data_dir()

    check(
        "dossier des macros accessible en ecriture",
        os.path.isdir(data_dir),
        data_dir,
    )

    check(
        "dossier des macros hors du repertoire temporaire",
        "_MEI" not in data_dir,
        "les macros survivent a la fermeture",
    )

    # --- aller-retour sur disque ---
    path = os.path.join(data_dir, "_autotest.json")

    actions = [
        macro.make_wait(0.1),
        macro.make_loop(2, [macro.make_click(-1500, 500)]),
        macro.make_key("s", ["ctrl"]),
    ]

    macro.save_macro(path, "Autotest", actions)

    name, reloaded = macro.load_macro(path)

    check(
        "enregistrement et rechargement d'une macro",
        name == "Autotest" and reloaded == actions,
    )

    os.remove(path)

    # --- backends pynput ---
    check(
        "backend clavier pynput (raccourci d'arret)",
        hotkeys.PYNPUT_AVAILABLE,
    )

    check(
        "backend souris pynput (enregistrement)",
        recorder.PYNPUT_AVAILABLE,
    )

    hotkey = hotkeys.GlobalHotkey()

    started = hotkey.start()

    check(
        f"ecoute globale de {hotkeys.STOP_KEY_NAME} effectivement demarree",
        started,
    )

    hotkey.stop()

    listener = recorder.Recorder()

    check("ecoute globale souris + clavier demarree", listener.start())

    listener._running = True
    listener.stop()

    # --- interface et ecrans ---
    window = MainWindow()

    window.actions = [
        macro.make_wait(0.1),
        macro.make_condition(
            macro.make_chance_test(50),
            [macro.make_click(1, 2)],
            [macro.make_key("esc")],
        ),
    ]

    window.refresh()

    check(
        "fenetre principale construite",
        bool(window.windowTitle()),
        window.windowTitle(),
    )

    check(
        "canevas : blocs et branches construits",
        len(window.canvas._blocks) == 4,
        f"{len(window.canvas._blocks)} blocs (4 attendus)",
    )

    check(
        "pictogrammes des blocs dessines",
        not theme.action_icon("condition").isNull(),
    )

    check(
        "evaluation des conditions (lecture de pixel)",
        bool(conditions.evaluate(macro.make_chance_test(100)))
        and not conditions.evaluate(macro.make_chance_test(0)),
    )

    try:
        pixel_ok = isinstance(
            conditions.evaluate(macro.make_pixel_test(5, 5, [0, 0, 0], 255)).value,
            bool,
        )
    except Exception:  # noqa: BLE001
        pixel_ok = False

    check(
        "capture d'ecran disponible (Pillow) pour les tests de pixel",
        pixel_ok,
    )

    check("detection des ecrans", "écran" in describe_screens())

    print(f"       {describe_screens()}")

    window.stop_hotkey.stop()

    print()

    if failures:

        print(f"{len(failures)} VERIFICATION(S) EN ECHEC : {failures}")

        return 1

    print("TOUTES LES VERIFICATIONS SONT PASSEES")

    return 0


if __name__ == "__main__":

    code = main()

    if getattr(sys, "frozen", False):
        input("\nAppuyez sur Entree pour fermer...")

    sys.exit(code)
