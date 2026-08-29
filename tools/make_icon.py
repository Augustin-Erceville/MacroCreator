"""Génère assets/icon.ico, l'icône de l'exécutable.

Lancement :

    python tools/make_icon.py

Le fichier .ico est assemblé à la main : Qt sait écrire du PNG, et le format
ICO n'est qu'un en-tête suivi des images PNG telles quelles.
"""

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication

SIZES = (256, 128, 64, 48, 32, 16)

BACKGROUND_TOP = QColor("#2f6df6")
BACKGROUND_BOTTOM = QColor("#1b3fa8")
FOREGROUND = QColor("#ffffff")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET = os.path.join(ROOT, "assets", "icon.ico")


def draw_icon(size):
    """Dessine l'icône : curseur de souris sur fond bleu, avec un « play »."""

    image = QImage(size, size, QImage.Format.Format_ARGB32)

    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    unit = size / 100.0

    # --- fond arrondi ---
    gradient = QLinearGradient(0, 0, 0, size)

    gradient.setColorAt(0.0, BACKGROUND_TOP)
    gradient.setColorAt(1.0, BACKGROUND_BOTTOM)

    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)

    painter.drawRoundedRect(
        QRectF(0, 0, size, size),
        22 * unit,
        22 * unit,
    )

    # --- curseur de souris ---
    cursor = QPolygonF([
        QPointF(30 * unit, 20 * unit),
        QPointF(30 * unit, 66 * unit),
        QPointF(42 * unit, 55 * unit),
        QPointF(50 * unit, 74 * unit),
        QPointF(59 * unit, 70 * unit),
        QPointF(51 * unit, 52 * unit),
        QPointF(66 * unit, 50 * unit),
    ])

    path = QPainterPath()

    path.addPolygon(cursor)

    path.closeSubpath()

    painter.setBrush(FOREGROUND)

    painter.drawPath(path)

    # --- triangle « lecture » en bas à droite ---
    if size >= 32:

        painter.setBrush(FOREGROUND)

        play = QPolygonF([
            QPointF(62 * unit, 60 * unit),
            QPointF(85 * unit, 73 * unit),
            QPointF(62 * unit, 86 * unit),
        ])

        painter.drawPolygon(play)

    painter.end()

    return image


def to_png_bytes(image):

    # La QByteArray doit rester référencée pendant toute la vie du QBuffer :
    # une valeur temporaire serait libérée côté Python et ferait planter Qt.
    storage = QByteArray()

    buffer = QBuffer(storage)

    buffer.open(QBuffer.OpenModeFlag.WriteOnly)

    image.save(buffer, "PNG")

    buffer.close()

    return bytes(storage)


def build_ico(images, path):
    """Assemble les PNG dans un conteneur ICO."""

    os.makedirs(os.path.dirname(path), exist_ok=True)

    header = struct.pack("<HHH", 0, 1, len(images))

    offset = len(header) + 16 * len(images)

    entries = []
    payloads = []

    for size, data in images:

        entries.append(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,          # palette
                0,          # réservé
                1,          # plans
                32,         # bits par pixel
                len(data),
                offset,
            )
        )

        payloads.append(data)

        offset += len(data)

    with open(path, "wb") as stream:

        stream.write(header)

        for entry in entries:
            stream.write(entry)

        for payload in payloads:
            stream.write(payload)

    return path


def main():

    application = QApplication(sys.argv)  # noqa: F841 - requis par QImage

    images = [
        (size, to_png_bytes(draw_icon(size)))
        for size in SIZES
    ]

    build_ico(images, TARGET)

    print(f"Icône générée : {TARGET}")

    for size, data in images:
        print(f"  {size}×{size} : {len(data)} octets")

    return 0


if __name__ == "__main__":

    sys.exit(main())
