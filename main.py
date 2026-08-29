"""Point d'entrée de Macro Creator.

Lancement :

    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from core import macro
from gui.main_window import APPLICATION_NAME, MainWindow


def main():

    macro.ensure_data_dir()

    application = QApplication(sys.argv)

    application.setApplicationName(APPLICATION_NAME)

    window = MainWindow()

    window.show()

    return application.exec()


if __name__ == "__main__":

    sys.exit(main())
