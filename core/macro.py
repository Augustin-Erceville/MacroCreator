"""Modèle de macro : création, validation, description et persistance JSON.

Une macro est un dictionnaire :

    {
        "format": "macro-creator",
        "version": 1,
        "name": "Ma macro",
        "actions": [ ... ]
    }

Une action est un dictionnaire dont la clé "type" détermine les autres clés.
Les actions de type "loop" contiennent une liste "actions" imbriquée, ce qui
permet des boucles dans des boucles.
"""

import copy
import json
import os
import re

# ==============================================================
# CONSTANTES
# ==============================================================

FORMAT_NAME = "macro-creator"
FORMAT_VERSION = 1
FILE_EXTENSION = ".json"

# Dossier de stockage des macros (data/ à la racine du projet)
DATA_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    ),
    "data"
)

ACTION_TYPES = (
    "wait",
    "move",
    "click",
    "drag",
    "scroll",
    "text",
    "key",
    "loop",
)

MOUSE_BUTTONS = ("left", "right", "middle")

MODIFIERS = ("ctrl", "shift", "alt", "win")

MAX_REPETITIONS = 100000


class MacroError(Exception):
    """Erreur de lecture, d'écriture ou de validation d'une macro."""


# ==============================================================
# LISTE DES TOUCHES
# ==============================================================

def get_keys():
    """Retourne la liste (nom affiché, valeur pyautogui) des touches."""

    keys = [
        (letter.upper(), letter)
        for letter in "abcdefghijklmnopqrstuvwxyz"
    ]

    keys += [
        (digit, digit)
        for digit in "0123456789"
    ]

    keys += [
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
    ]

    keys += [
        (f"F{number}", f"f{number}")
        for number in range(1, 13)
    ]

    return keys


KEY_NAMES = {
    value: name
    for name, value in get_keys()
}

MODIFIER_NAMES = {
    "ctrl": "CTRL",
    "shift": "SHIFT",
    "alt": "ALT",
    "win": "WIN",
}

BUTTON_NAMES = {
    "left": "gauche",
    "right": "droit",
    "middle": "milieu",
}


# ==============================================================
# CREATION D'ACTIONS
# ==============================================================

def make_wait(duration, duration_max=None):
    """Attente fixe, ou aléatoire entre duration et duration_max."""

    action = {
        "type": "wait",
        "duration": float(duration),
    }

    if duration_max is not None:
        action["duration_max"] = float(duration_max)

    return action


def make_move(x, y, duration=0.5):
    return {
        "type": "move",
        "x": int(x),
        "y": int(y),
        "duration": float(duration),
    }


def make_click(x, y, button="left", clicks=1):
    return {
        "type": "click",
        "x": int(x),
        "y": int(y),
        "button": button,
        "clicks": int(clicks),
    }


def make_drag(x, y, x2, y2, button="left", duration=0.5):
    return {
        "type": "drag",
        "x": int(x),
        "y": int(y),
        "x2": int(x2),
        "y2": int(y2),
        "button": button,
        "duration": float(duration),
    }


def make_scroll(amount, x=None, y=None):
    """Molette : amount > 0 monte, amount < 0 descend."""

    action = {
        "type": "scroll",
        "amount": int(amount),
    }

    if x is not None and y is not None:
        action["x"] = int(x)
        action["y"] = int(y)

    return action


def make_text(text, interval=0.01):
    return {
        "type": "text",
        "text": text,
        "interval": float(interval),
    }


def make_key(key, modifiers=None):
    return {
        "type": "key",
        "key": key,
        "modifiers": list(modifiers or []),
    }


def make_loop(repetitions, actions=None):
    return {
        "type": "loop",
        "repetitions": int(repetitions),
        "actions": list(actions or []),
    }


def new_macro(name="Nouvelle macro"):
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "name": name,
        "actions": [],
    }


# ==============================================================
# NAVIGATION DANS L'ARBRE D'ACTIONS
# ==============================================================

def get_container(actions, path):
    """Retourne (liste_parente, index) pour un chemin d'action.

    Un chemin est une suite d'indices : [2] désigne la 3e action de la
    racine, [2, 0] la 1re action de la boucle située en 3e position.
    """

    if not path:
        raise MacroError("Chemin d'action vide.")

    container = actions

    for step in path[:-1]:

        parent = container[step]

        if parent.get("type") != "loop":
            raise MacroError("Chemin d'action invalide.")

        container = parent["actions"]

    index = path[-1]

    if index < 0 or index >= len(container):
        raise MacroError("Chemin d'action hors limites.")

    return container, index


def get_action(actions, path):
    container, index = get_container(actions, path)

    return container[index]


def count_actions(actions):
    """Nombre total d'actions, boucles imbriquées comprises."""

    total = 0

    for action in actions:

        total += 1

        if action.get("type") == "loop":
            total += count_actions(action.get("actions", []))

    return total


# ==============================================================
# DESCRIPTION
# ==============================================================

def describe_action(action, number=None):
    """Texte affiché dans la liste pour une action."""

    prefix = "" if number is None else f"{number}. "

    action_type = action.get("type")

    if action_type == "wait":

        if action.get("duration_max"):

            return (
                f"{prefix}⏱ Attendre entre "
                f"{action['duration']:.2f}s et "
                f"{action['duration_max']:.2f}s (aléatoire)"
            )

        return f"{prefix}⏱ Attendre {action['duration']:.2f}s"

    if action_type == "move":

        return (
            f"{prefix}🖱 Déplacer souris "
            f"→ X:{action['x']} | Y:{action['y']} | "
            f"Durée:{action['duration']:.2f}s"
        )

    if action_type == "click":

        click_types = {1: "Simple", 2: "Double", 3: "Triple"}

        clicks = action["clicks"]

        click_label = click_types.get(clicks, f"{clicks} clics")

        return (
            f"{prefix}🖱 Clic "
            f"{BUTTON_NAMES.get(action['button'], action['button'])} "
            f"→ {click_label} "
            f"à X:{action['x']} Y:{action['y']}"
        )

    if action_type == "drag":

        return (
            f"{prefix}🖱 Glisser "
            f"{BUTTON_NAMES.get(action['button'], action['button'])} "
            f"→ de X:{action['x']} Y:{action['y']} "
            f"à X:{action['x2']} Y:{action['y2']} "
            f"({action['duration']:.2f}s)"
        )

    if action_type == "scroll":

        direction = "haut" if action["amount"] > 0 else "bas"

        position = ""

        if "x" in action and "y" in action:
            position = f" à X:{action['x']} Y:{action['y']}"

        return (
            f"{prefix}🖱 Molette vers le {direction} "
            f"({abs(action['amount'])} cran(s)){position}"
        )

    if action_type == "text":

        text = action["text"].replace("\n", "\\n")

        if len(text) > 60:
            text = text[:57] + "..."

        return f'{prefix}⌨ Écrire : "{text}"'

    if action_type == "key":

        parts = [
            MODIFIER_NAMES.get(modifier, modifier.upper())
            for modifier in action.get("modifiers", [])
        ]

        parts.append(
            KEY_NAMES.get(action["key"], action["key"]).upper()
        )

        return f"{prefix}⌨ Appuyer : {' + '.join(parts)}"

    if action_type == "loop":

        inner = len(action.get("actions", []))

        return (
            f"{prefix}🔁 Boucle × {action['repetitions']} "
            f"({inner} action(s))"
        )

    return f"{prefix}Action inconnue"


# ==============================================================
# VALIDATION
# ==============================================================

def validate_actions(actions, _depth=0):
    """Vérifie la structure d'une liste d'actions. Lève MacroError."""

    if _depth > 20:
        raise MacroError("Boucles imbriquées trop profondes (max 20).")

    if not isinstance(actions, list):
        raise MacroError("La liste d'actions est invalide.")

    for action in actions:

        if not isinstance(action, dict):
            raise MacroError("Une action n'est pas un objet valide.")

        action_type = action.get("type")

        if action_type not in ACTION_TYPES:
            raise MacroError(f"Type d'action inconnu : {action_type!r}")

        if action_type == "wait":
            _require(action, ["duration"], (int, float))

            if action["duration"] < 0:
                raise MacroError("Durée d'attente négative.")

        elif action_type == "move":
            _require(action, ["x", "y"], int)
            _require(action, ["duration"], (int, float))

        elif action_type == "click":
            _require(action, ["x", "y", "clicks"], int)
            _require_button(action)

        elif action_type == "drag":
            _require(action, ["x", "y", "x2", "y2"], int)
            _require(action, ["duration"], (int, float))
            _require_button(action)

        elif action_type == "scroll":
            _require(action, ["amount"], int)

        elif action_type == "text":
            _require(action, ["text"], str)

        elif action_type == "key":
            _require(action, ["key"], str)

            modifiers = action.get("modifiers", [])

            if not isinstance(modifiers, list):
                raise MacroError("Modificateurs invalides.")

            for modifier in modifiers:

                if modifier not in MODIFIERS:
                    raise MacroError(
                        f"Modificateur inconnu : {modifier!r}"
                    )

        elif action_type == "loop":
            _require(action, ["repetitions"], int)

            if not 1 <= action["repetitions"] <= MAX_REPETITIONS:
                raise MacroError(
                    "Nombre de répétitions hors limites "
                    f"(1 à {MAX_REPETITIONS})."
                )

            validate_actions(action.get("actions", []), _depth + 1)

    return True


def _require(action, keys, types):

    for key in keys:

        if key not in action:
            raise MacroError(
                f"Clé « {key} » manquante pour une action "
                f"« {action.get('type')} »."
            )

        value = action[key]

        if isinstance(value, bool) or not isinstance(value, types):
            raise MacroError(
                f"Valeur invalide pour « {key} » : {value!r}"
            )


def _require_button(action):

    if action.get("button") not in MOUSE_BUTTONS:
        raise MacroError(
            f"Bouton de souris inconnu : {action.get('button')!r}"
        )


def check_coordinates(actions, screens):
    """Retourne la liste des descriptions d'actions situées hors écran.

    `screens` est la liste des zones d'affichage, chacune sous la forme
    (gauche, haut, droite, bas) avec droite et bas exclus. En multi-écran,
    l'origine (0, 0) est le coin de l'écran principal : un écran placé à
    gauche ou au-dessus a donc des coordonnées négatives, ce qui est
    parfaitement valide. Une action n'est signalée que si elle ne tombe
    dans aucun des écrans.
    """

    if not screens:
        return []

    problems = []

    for index, action in enumerate(actions, start=1):

        if action.get("type") == "loop":

            problems += check_coordinates(
                action.get("actions", []),
                screens,
            )

            continue

        points = []

        if "x" in action and "y" in action:
            points.append((action["x"], action["y"]))

        if "x2" in action and "y2" in action:
            points.append((action["x2"], action["y2"]))

        for x, y in points:

            if not point_on_any_screen(x, y, screens):

                problems.append(describe_action(action, index))

                break

    return problems


def point_on_any_screen(x, y, screens):

    for left, top, right, bottom in screens:

        if left <= x < right and top <= y < bottom:
            return True

    return False


# ==============================================================
# PERSISTANCE
# ==============================================================

def ensure_data_dir():

    os.makedirs(DATA_DIR, exist_ok=True)

    return DATA_DIR


def safe_filename(name):
    """Transforme un nom de macro en nom de fichier utilisable."""

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")

    return (cleaned or "macro") + FILE_EXTENSION


def save_macro(path, name, actions):
    """Écrit la macro sur disque (écriture atomique)."""

    validate_actions(actions)

    payload = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "name": name,
        "actions": copy.deepcopy(actions),
    }

    temporary = path + ".tmp"

    try:

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        with open(temporary, "w", encoding="utf-8") as stream:

            json.dump(payload, stream, ensure_ascii=False, indent=2)

        os.replace(temporary, path)

    except OSError as error:

        if os.path.exists(temporary):

            try:
                os.remove(temporary)
            except OSError:
                pass

        raise MacroError(f"Écriture impossible : {error}") from error

    return path


def load_macro(path):
    """Lit une macro et retourne (nom, actions). Lève MacroError."""

    try:

        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)

    except OSError as error:
        raise MacroError(f"Lecture impossible : {error}") from error

    except json.JSONDecodeError as error:
        raise MacroError(f"Fichier JSON illisible : {error}") from error

    if not isinstance(payload, dict):
        raise MacroError("Le fichier ne contient pas une macro valide.")

    if payload.get("format") != FORMAT_NAME:
        raise MacroError(
            "Ce fichier n'a pas été créé par Macro Creator."
        )

    if payload.get("version", 1) > FORMAT_VERSION:
        raise MacroError(
            "Ce fichier a été créé par une version plus récente "
            "de Macro Creator."
        )

    actions = payload.get("actions", [])

    validate_actions(actions)

    name = payload.get("name") or os.path.splitext(
        os.path.basename(path)
    )[0]

    return name, actions


def list_macros():
    """Liste les fichiers de macros présents dans data/."""

    ensure_data_dir()

    return sorted(
        os.path.join(DATA_DIR, entry)
        for entry in os.listdir(DATA_DIR)
        if entry.lower().endswith(FILE_EXTENSION)
    )
