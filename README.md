# Macro Creator

Application de bureau (Windows) pour créer, enregistrer et exécuter des
macros clavier et souris.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

Deux possibilités.

### 1. L'exécutable (le plus simple)

Double-cliquez sur **`dist\Macro Creator.exe`**. Aucune installation, aucun
Python requis : tout est embarqué dans le fichier. La fenêtre s'ouvre en
2 à 3 secondes.

Vous pouvez déplacer cet exécutable où vous voulez (bureau, clé USB...) ;
il crée alors un dossier `data\` à côté de lui pour vos macros. S'il est
placé dans un dossier protégé en écriture, les macros vont dans
`Documents\Macro Creator\`.

### 2. Depuis les sources

```bash
python main.py
```

## Reconstruire l'exécutable

Après une modification du code, double-cliquez sur **`build.bat`** (ou
lancez-le en terminal). Le script installe PyInstaller si besoin, régénère
l'icône et reconstruit `dist\Macro Creator.exe` — comptez une à deux
minutes.

Pour vérifier qu'un build est sain, `tools\selftest_frozen.py` contrôle les
points qui cassent typiquement une fois l'application figée (backends
pynput, dossier des macros, détection des écrans) :

```bash
python tools/selftest_frozen.py
```

### À savoir sur l'exécutable

- Il pèse ~45 Mo : Python, Qt et les bibliothèques y sont inclus.
- Windows SmartScreen ou l'antivirus peuvent le signaler au premier
  lancement : il n'est pas signé numériquement, et il surveille le clavier
  et la souris — deux comportements que les antivirus regardent de près.
  « Informations complémentaires » puis « Exécuter quand même ».

## Raccourcis

| Touche | Rôle |
|---|---|
| **F12** | **Arrêt d'urgence** de la macro en cours (fonctionne même quand la fenêtre n'a pas le focus) |
| F8 | Capturer la position actuelle de la souris |
| F9 | Arrêter l'enregistrement des gestes |
| F5 | Exécuter la macro |
| Ctrl+N / Ctrl+O / Ctrl+S | Nouveau / Ouvrir / Enregistrer |
| Ctrl+R | Enregistrer ses gestes |

Second filet de sécurité : placer la souris dans le **coin haut-gauche de
l'écran** interrompt immédiatement l'exécution (sécurité PyAutoGUI).

## Utilisation

Deux façons de construire une macro :

1. **Enregistrement** — le bouton « Enregistrer mes gestes » capture les
   clics, la molette, la frappe au clavier et les délais réels, puis les
   convertit en actions modifiables.
2. **Action par action** — chaque bouton du panneau de gauche ouvre une
   boîte de dialogue.

Le point d'insertion suit la sélection :

- aucune sélection → l'action est ajoutée à la fin ;
- une action sélectionnée → l'action est insérée juste après ;
- une **boucle** sélectionnée → l'action est ajoutée **à l'intérieur** de la
  boucle.

Les boucles s'affichent sous forme d'arborescence et peuvent être
imbriquées. « Grouper en boucle » transforme une sélection d'actions
consécutives en boucle, « Dégrouper » fait l'inverse.

## Types d'actions

| Type | Description |
|---|---|
| Attente | Durée fixe ou aléatoire entre deux bornes |
| Mouvement souris | Déplacement vers X/Y avec une durée |
| Clic | Simple, double ou triple ; bouton gauche, droit ou milieu |
| Glisser-déposer | D'un point à un autre, bouton maintenu |
| Molette | Défilement haut/bas, avec position optionnelle |
| Texte | Saisie d'une chaîne, délai réglable entre les caractères |
| Touche | Touche unique avec modificateurs (CTRL, SHIFT, ALT, Windows) |
| Boucle | Répète un groupe d'actions, imbrication possible |

## Format de fichier

Les macros sont enregistrées en JSON dans `data/` :

```json
{
  "format": "macro-creator",
  "version": 1,
  "name": "Ma macro",
  "actions": [
    { "type": "wait", "duration": 1.0 },
    { "type": "click", "x": 100, "y": 200, "button": "left", "clicks": 1 }
  ]
}
```

Le fichier est validé au chargement : un JSON malformé ou une action
inconnue produit un message d'erreur au lieu d'un plantage.

## Structure du projet

```
main.py               point d'entrée
build.bat             construit l'exécutable
macro_creator.spec    recette PyInstaller
assets/icon.ico       icône de l'application
tools/                génération de l'icône, auto-test d'un build
core/macro.py         modèle, validation, description, lecture/écriture JSON
core/executor.py      exécution des actions dans un thread interruptible
core/recorder.py      enregistrement temps réel (pynput)
core/hotkeys.py       raccourci global d'arrêt d'urgence
gui/main_window.py    fenêtre principale
gui/dialogs.py        dialogues d'ajout et de modification d'actions
data/                 macros enregistrées
```

## Multi-écran

Les coordonnées sont exprimées dans l'espace virtuel de Windows : l'origine
(0, 0) est le coin haut-gauche de l'**écran principal**. Un écran situé à sa
gauche ou au-dessus occupe donc des coordonnées **négatives**, ce qui est
normal et pleinement supporté (champs X/Y de -20000 à 20000).

L'avertissement « coordonnées hors écran » ne se déclenche que si un point
ne tombe dans **aucun** des écrans détectés ; le menu « Aide › À propos »
affiche la disposition vue par l'application.

## Limites connues

- La saisie de texte simulée dépend de la disposition clavier active ; les
  caractères absents du clavier ne sont pas tapés.
- L'enregistrement des mouvements de souris est échantillonné (une position
  toutes les 150 ms) pour éviter de produire des milliers d'actions.
- Pas de reconnaissance d'image (« cliquer quand tel élément apparaît ») :
  cela demanderait OpenCV.
