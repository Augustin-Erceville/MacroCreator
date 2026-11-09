"""Évaluation des tests de condition.

Chaque test renvoie un booléen. Les erreurs d'environnement (image
illisible, capture d'écran indisponible) ne doivent pas interrompre la
macro : elles sont converties en « faux » et signalées par un message.
"""

import random

import pyautogui

from core import macro


class TestResult:
    """Résultat d'un test, avec de quoi l'expliquer à l'utilisateur."""

    def __init__(self, value, detail=""):

        self.value = bool(value)
        self.detail = detail

    def __bool__(self):
        return self.value


def evaluate(test):
    """Évalue un test de condition et retourne un TestResult."""

    kind = test.get("kind")

    evaluator = _EVALUATORS.get(kind)

    if evaluator is None:
        return TestResult(False, f"test inconnu ({kind})")

    try:
        result = evaluator(test)

    except Exception as error:  # noqa: BLE001 - un test raté ne casse rien
        return TestResult(False, f"test impossible : {error}")

    if test.get("negate"):
        return TestResult(not result.value, result.detail)

    return result


# ==============================================================
# TESTS
# ==============================================================

def _test_pixel(test):

    expected = tuple(test["color"])

    tolerance = test.get("tolerance", 0)

    found = pyautogui.pixel(test["x"], test["y"])

    found = (found[0], found[1], found[2])

    matches = all(
        abs(found[channel] - expected[channel]) <= tolerance
        for channel in range(3)
    )

    return TestResult(
        matches,
        f"pixel lu {macro.rgb_to_hex(found)}, "
        f"attendu {macro.rgb_to_hex(expected)}",
    )


def _test_image(test):

    location = pyautogui.locateOnScreen(test["path"])

    if location is None:
        return TestResult(False, "image absente de l'écran")

    return TestResult(
        True,
        f"image trouvée en X:{int(location.left)} Y:{int(location.top)}",
    )


def _test_window(test):

    title = pyautogui.getActiveWindowTitle() or ""

    expected = test.get("text", "")

    if test.get("mode") == "equals":
        matches = title == expected

    else:
        matches = expected.lower() in title.lower()

    return TestResult(matches, f"fenêtre active « {title} »")


def _test_chance(test):

    percent = test.get("percent", 50)

    draw = random.uniform(0, 100)

    return TestResult(draw < percent, f"tirage {draw:.1f} / {percent} %")


_EVALUATORS = {
    "pixel": _test_pixel,
    "image": _test_image,
    "window": _test_window,
    "chance": _test_chance,
}
