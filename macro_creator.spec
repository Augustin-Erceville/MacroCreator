# -*- mode: python ; coding: utf-8 -*-
"""Recette de construction de l'exécutable Macro Creator.

Utilisation (via build.bat, ou directement) :

    .venv\\Scripts\\pyinstaller.exe macro_creator.spec --noconfirm
"""

NAME = "Macro Creator"

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Backends pynput chargés dynamiquement : PyInstaller ne peut pas
        # les repérer tout seul.
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Modules Qt volumineux et inutilisés : sans cela l'exécutable
        # dépasse inutilement les 150 Mo.
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtOpenGL",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSerialPort",
        "PySide6.QtSensors",
        "PySide6.QtWebSockets",
        "PySide6.QtWebChannel",
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
    ],
    noarchive=False,
    optimize=0,
)

archive = PYZ(analysis.pure)

executable = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Application graphique : pas de fenêtre de console noire au lancement.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)
