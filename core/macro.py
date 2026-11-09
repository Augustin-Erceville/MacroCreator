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
import sys

# ==============================================================
# CONSTANTES
# ==============================================================

FORMAT_NAME = "macro-creator"
FORMAT_VERSION = 1
FILE_EXTENSION = ".json"


def base_dir():
    """Dossier de référence de l'application.

    En exécutable PyInstaller, `__file__` pointe vers le dossier temporaire
    d'extraction, effacé à la fermeture : on se base alors sur l'emplacement
    de l'exécutable lui-même.
    """

    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Dossier de stockage des macros (à côté de l'exécutable ou du projet)
DATA_DIR = os.path.join(base_dir(), "data")

# Emplacement de repli si le dossier de l'application n'est pas accessible
# en écriture (exécutable placé dans « Program Files », par exemple).
FALLBACK_DATA_DIR = os.path.join(
    os.path.expanduser("~"),
    "Documents",
    "Macro Creator",
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
    "condition",
)

# Types d'actions qui contiennent d'autres actions
CONTAINER_TYPES = ("loop", "condition")

# Branches d'une condition
BRANCHES = ("then", "else")

# Natures de test disponibles pour une condition
TEST_KINDS = ("pixel", "image", "window", "chance")

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

# Pictogramme et nom court de chaque type d'action
ACTION_ICONS = {
    "wait": "⏱",
    "move": "🖱",
    "click": "🖱",
    "drag": "🖱",
    "scroll": "🖱",
    "text": "⌨",
    "key": "⌨",
    "loop": "🔁",
    "condition": "🔀",
}

ACTION_LABELS = {
    "wait": "Attente",
    "move": "Mouvement",
    "click": "Clic",
    "drag": "Glisser",
    "scroll": "Molette",
    "text": "Texte",
    "key": "Touche",
    "loop": "Boucle",
    "condition": "Condition",
}

# Phrase affichée sous le titre de chaque bloc de la palette
ACTION_SUMMARIES = {
    "wait": "Marquer une pause, fixe ou aléatoire",
    "move": "Déplacer le curseur vers un point",
    "click": "Cliquer à une position donnée",
    "drag": "Maintenir et déplacer d'un point à un autre",
    "scroll": "Faire défiler avec la molette",
    "text": "Taper du texte au clavier",
    "key": "Appuyer sur une touche ou un raccourci",
    "loop": "Répéter un groupe d'actions",
    "condition": "Exécuter selon qu'un test est vrai ou faux",
}

BRANCH_LABELS = {
    "then": "Alors",
    "else": "Sinon",
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


# --- Tests de condition ---------------------------------------

def make_pixel_test(x, y, color, tolerance=10, negate=False):
    """Vrai si le pixel en (x, y) a la couleur indiquée, à tolérance près."""

    return {
        "kind": "pixel",
        "x": int(x),
        "y": int(y),
        "color": [int(channel) for channel in color],
        "tolerance": int(tolerance),
        "negate": bool(negate),
    }


def make_image_test(path, negate=False):
    """Vrai si l'image du fichier est visible quelque part à l'écran."""

    return {
        "kind": "image",
        "path": str(path),
        "negate": bool(negate),
    }


def make_window_test(text, mode="contains", negate=False):
    """Vrai selon le titre de la fenêtre active."""

    return {
        "kind": "window",
        "text": str(text),
        "mode": mode,
        "negate": bool(negate),
    }


def make_chance_test(percent, negate=False):
    """Vrai avec la probabilité indiquée."""

    return {
        "kind": "chance",
        "percent": int(percent),
        "negate": bool(negate),
    }


def make_condition(test=None, then_actions=None, else_actions=None):

    return {
        "type": "condition",
        "test": test or make_chance_test(50),
        "then": list(then_actions or []),
        "else": list(else_actions or []),
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

def children(action, branch=None):
    """Liste d'actions contenue dans un bloc, ou None s'il n'en contient pas.

    Une boucle n'a qu'un contenu ; une condition en a deux, désignés par
    `branch` (« then » ou « else »).
    """

    action_type = action.get("type")

    if action_type == "loop":
        return action.setdefault("actions", [])

    if action_type == "condition":

        if branch not in BRANCHES:
            branch = "then"

        return action.setdefault(branch, [])

    return None


def get_branch(actions, path):
    """Retourne la liste d'actions désignée par un chemin de branche.

    Le chemin se termine alors par un nom de branche ou désigne une boucle :
    [2] pour le contenu de la boucle n° 3, [2, "else"] pour le « sinon » de
    la condition n° 3. Un chemin vide désigne la racine.
    """

    if not path:
        return actions

    branch = None

    if isinstance(path[-1], str):
        branch = path[-1]
        path = path[:-1]

    container, index = get_container(actions, path)

    inner = children(container[index], branch)

    if inner is None:
        raise MacroError("Cette action ne contient pas d'autres actions.")

    return inner


def get_container(actions, path):
    """Retourne (liste_parente, index) pour un chemin d'action.

    Un chemin est une suite d'indices, éventuellement entrecoupée de noms
    de branche : [2] désigne la 3e action de la racine, [2, 0] la 1re
    action de la boucle située en 3e position, et [2, "else", 0] la 1re
    action du « sinon » de la condition située en 3e position.
    """

    if not path:
        raise MacroError("Chemin d'action vide.")

    if isinstance(path[-1], str):
        raise MacroError("Un chemin d'action ne peut pas finir par une branche.")

    container = actions

    position = 0

    while position < len(path):

        token = path[position]

        if isinstance(token, str):
            raise MacroError("Chemin d'action invalide.")

        if token < 0 or token >= len(container):
            raise MacroError("Chemin d'action hors limites.")

        # Dernier élément : on a trouvé la liste parente et l'index.
        if position == len(path) - 1:
            return container, token

        parent = container[token]

        branch = None

        if isinstance(path[position + 1], str):

            branch = path[position + 1]

            position += 1

        inner = children(parent, branch)

        if inner is None:
            raise MacroError("Chemin d'action invalide.")

        container = inner

        position += 1

    raise MacroError("Chemin d'action invalide.")


def get_action(actions, path):
    container, index = get_container(actions, path)

    return container[index]


def count_actions(actions):
    """Nombre total d'actions, blocs imbriqués compris."""

    total = 0

    for action in actions:

        total += 1

        if action.get("type") == "loop":
            total += count_actions(action.get("actions", []))

        elif action.get("type") == "condition":

            total += count_actions(action.get("then", []))
            total += count_actions(action.get("else", []))

    return total


def count_steps(actions):
    """Estimation du nombre d'actions réellement exécutées.

    Une boucle ne compte pas pour elle-même : seuls comptent les passages
    de son contenu. Pour une condition, la branche empruntée n'est connue
    qu'à l'exécution : on retient la plus longue, l'estimation sert
    uniquement à la barre de progression.
    """

    total = 0

    for action in actions:

        action_type = action.get("type")

        if action_type == "loop":

            total += (
                action.get("repetitions", 1)
                * count_steps(action.get("actions", []))
            )

        elif action_type == "condition":

            total += 1 + max(
                count_steps(action.get("then", [])),
                count_steps(action.get("else", [])),
            )

        else:
            total += 1

    return total


def has_conditions(actions):
    """Indique si la macro comporte une condition (progression estimée)."""

    for action in actions:

        action_type = action.get("type")

        if action_type == "condition":
            return True

        if action_type == "loop":

            if has_conditions(action.get("actions", [])):
                return True

    return False


# ==============================================================
# DESCRIPTION
# ==============================================================

def describe_action(action, number=None, icon=True):
    """Texte affiché dans la liste pour une action.

    `icon=False` omet le pictogramme : l'interface affiche alors sa propre
    pastille de couleur à la place.
    """

    parts = []

    if number is not None:
        parts.append(f"{number}.")

    if icon:
        parts.append(ACTION_ICONS.get(action.get("type"), "•"))

    parts.append(action_body(action))

    return " ".join(parts)


def action_body(action):
    """Description d'une action, sans numéro ni pictogramme."""

    action_type = action.get("type")

    if action_type == "wait":

        if action.get("duration_max"):

            return (
                f"Attendre entre {action['duration']:.2f}s et "
                f"{action['duration_max']:.2f}s (aléatoire)"
            )

        return f"Attendre {action['duration']:.2f}s"

    if action_type == "move":

        return (
            f"Déplacer souris → X:{action['x']} | Y:{action['y']} | "
            f"Durée:{action['duration']:.2f}s"
        )

    if action_type == "click":

        click_types = {1: "Simple", 2: "Double", 3: "Triple"}

        clicks = action["clicks"]

        click_label = click_types.get(clicks, f"{clicks} clics")

        return (
            f"Clic {BUTTON_NAMES.get(action['button'], action['button'])} "
            f"→ {click_label} à X:{action['x']} Y:{action['y']}"
        )

    if action_type == "drag":

        return (
            f"Glisser {BUTTON_NAMES.get(action['button'], action['button'])} "
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
            f"Molette vers le {direction} "
            f"({abs(action['amount'])} cran(s)){position}"
        )

    if action_type == "text":

        text = action["text"].replace("\n", "\\n")

        if len(text) > 60:
            text = text[:57] + "..."

        return f'Écrire : "{text}"'

    if action_type == "key":

        parts = [
            MODIFIER_NAMES.get(modifier, modifier.upper())
            for modifier in action.get("modifiers", [])
        ]

        parts.append(
            KEY_NAMES.get(action["key"], action["key"]).upper()
        )

        return f"Appuyer : {' + '.join(parts)}"

    if action_type == "loop":

        inner = len(action.get("actions", []))

        return (
            f"Boucle × {action['repetitions']} ({inner} action(s))"
        )

    if action_type == "condition":

        return f"Si {describe_test(action.get('test', {}))}"

    return "Action inconnue"


def describe_test(test):
    """Phrase décrivant le test d'une condition."""

    kind = test.get("kind")

    negate = test.get("negate", False)

    if kind == "pixel":

        color = tuple(test.get("color", (0, 0, 0)))

        verb = "n'est pas" if negate else "est"

        return (
            f"la couleur du pixel X:{test['x']} Y:{test['y']} {verb} "
            f"{rgb_to_hex(color)} (± {test.get('tolerance', 0)})"
        )

    if kind == "image":

        verb = "n'est pas visible" if negate else "est visible"

        name = os.path.basename(test.get("path", "")) or "image"

        return f"l'image « {name} » {verb} à l'écran"

    if kind == "window":

        mode = test.get("mode", "contains")

        if mode == "equals":
            comparison = "n'est pas exactement" if negate else "est exactement"

        else:
            comparison = "ne contient pas" if negate else "contient"

        return (
            f"le titre de la fenêtre active {comparison} "
            f"« {test.get('text', '')} »"
        )

    if kind == "chance":

        percent = test.get("percent", 50)

        if negate:
            percent = 100 - percent

        return f"le hasard tombe sur {percent} %"

    return "test inconnu"


def rgb_to_hex(color):

    red, green, blue = (int(channel) for channel in color)

    return f"#{red:02x}{green:02x}{blue:02x}"


def hex_to_rgb(value):

    value = value.strip().lstrip("#")

    if len(value) != 6:
        raise MacroError(f"Couleur invalide : {value!r}")

    try:
        return [int(value[index:index + 2], 16) for index in (0, 2, 4)]

    except ValueError as error:
        raise MacroError(f"Couleur invalide : {value!r}") from error


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

        elif action_type == "condition":

            validate_test(action.get("test"))

            for branch in BRANCHES:
                validate_actions(action.get(branch, []), _depth + 1)

    return True


def validate_test(test):
    """Vérifie le test d'une condition. Lève MacroError."""

    if not isinstance(test, dict):
        raise MacroError("Condition sans test valide.")

    kind = test.get("kind")

    if kind not in TEST_KINDS:
        raise MacroError(f"Type de test inconnu : {kind!r}")

    if kind == "pixel":

        _require(test, ["x", "y", "tolerance"], int)

        color = test.get("color")

        if (
            not isinstance(color, (list, tuple))
            or len(color) != 3
            or not all(
                isinstance(channel, int) and 0 <= channel <= 255
                for channel in color
            )
        ):
            raise MacroError("Couleur de test invalide.")

        if not 0 <= test["tolerance"] <= 255:
            raise MacroError("Tolérance hors limites (0 à 255).")

    elif kind == "image":

        _require(test, ["path"], str)

        if not test["path"]:
            raise MacroError("Aucune image sélectionnée pour le test.")

    elif kind == "window":

        _require(test, ["text"], str)

        if test.get("mode") not in ("contains", "equals"):
            raise MacroError("Mode de comparaison de titre inconnu.")

    elif kind == "chance":

        _require(test, ["percent"], int)

        if not 0 <= test["percent"] <= 100:
            raise MacroError("Probabilité hors limites (0 à 100 %).")

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

        if action.get("type") == "condition":

            test = action.get("test", {})

            if test.get("kind") == "pixel" and not point_on_any_screen(
                test.get("x", 0), test.get("y", 0), screens
            ):
                problems.append(describe_action(action, index))

            for branch in BRANCHES:

                problems += check_coordinates(
                    action.get(branch, []),
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
    """Crée le dossier des macros et vérifie qu'il est accessible en écriture.

    Bascule sur « Documents/Macro Creator » si ce n'est pas le cas.
    """

    global DATA_DIR

    for candidate in (DATA_DIR, FALLBACK_DATA_DIR):

        try:

            os.makedirs(candidate, exist_ok=True)

            probe = os.path.join(candidate, ".ecriture")

            with open(probe, "w", encoding="utf-8"):
                pass

            os.remove(probe)

        except OSError:
            continue

        DATA_DIR = candidate

        return DATA_DIR

    # Dernier recours : on garde le dossier prévu, l'erreur éventuelle sera
    # signalée à l'enregistrement.
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
