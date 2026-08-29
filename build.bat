@echo off
REM Construit "Macro Creator.exe" dans le dossier dist\.
REM Double-cliquez sur ce fichier, ou lancez-le depuis un terminal.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Environnement virtuel introuvable.
    echo   Creez-le d'abord :
    echo.
    echo       python -m venv .venv
    echo       .venv\Scripts\activate
    echo       pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo === Verification des dependances de construction ===
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pyinstaller
if errorlevel 1 goto erreur

echo.
echo === Generation de l'icone ===
".venv\Scripts\python.exe" "tools\make_icon.py"
if errorlevel 1 goto erreur

echo.
echo === Construction de l'executable (quelques minutes) ===
".venv\Scripts\python.exe" -m PyInstaller macro_creator.spec --noconfirm --clean
if errorlevel 1 goto erreur

echo.
echo === Termine ===
echo   L'executable se trouve ici : dist\Macro Creator.exe
echo   Les macros seront enregistrees dans dist\data\.
echo.
pause
exit /b 0

:erreur
echo.
echo   La construction a echoue. Lisez les messages ci-dessus.
echo.
pause
exit /b 1
