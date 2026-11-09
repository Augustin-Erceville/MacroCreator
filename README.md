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

### Le canevas de blocs

La macro s'affiche comme un enchaînement de blocs reliés verticalement.

- Le bouton **« + »** entre deux blocs insère une action **exactement à cet
  endroit** : il ouvre la palette des blocs disponibles.
- Un bloc de la colonne de gauche s'ajoute **après le bloc sélectionné**,
  ou à la fin si rien n'est sélectionné.
- **Ctrl+clic** sélectionne plusieurs blocs ; « Grouper en boucle »
  transforme une suite de blocs consécutifs en boucle, « Dégrouper » fait
  l'inverse.
- Les boucles et les conditions affichent leur contenu en retrait et
  peuvent être imbriquées sans limite de profondeur.

### Conditions

Un bloc **Condition** sépare le flux en deux branches : **Alors** si le
test est vrai, **Sinon** dans le cas contraire. Chaque branche se remplit
avec son propre bouton « + ». Quatre tests sont disponibles :

| Test | Description |
|---|---|
| Couleur d'un pixel | Compare la couleur en X/Y à une couleur de référence, avec tolérance. Le bouton « Lire la couleur » capture la couleur actuelle. |
| Image visible | Cherche une image à l'écran (correspondance exacte de pixels). |
| Titre de la fenêtre active | Contient, ou est exactement, un texte donné. |
| Probabilité | Vrai avec le pourcentage de chances indiqué. |

Chaque test peut être **inversé** d'une case à cocher. Un test qui échoue
pour une raison technique (image introuvable, capture impossible) est
considéré comme faux et n'interrompt pas la macro.

### Suivi de l'exécution

Pendant l'exécution, le bloc en cours est **encadré en vert** dans le
canevas, qui défile automatiquement jusqu'à lui. Le bandeau du bas affiche
l'action en cours, la progression (`action 7 / 18`) et, lorsqu'il s'agit
d'une attente, le **temps restant avant l'action suivante**, décompté dix
fois par seconde.

Quand la macro contient une condition, le compteur est précédé de « ≈ » :
la branche empruntée n'étant connue qu'à l'exécution, le total n'est
qu'une estimation.

### Thème

Le menu **Affichage** bascule entre thème sombre et thème clair ; le choix
est mémorisé.

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
| Condition | Sépare le flux en deux branches selon un test |

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

Une condition contient son test et ses deux branches :

```json
{
  "type": "condition",
  "test": {
    "kind": "pixel",
    "x": 960, "y": 540,
    "color": [237, 66, 69],
    "tolerance": 15,
    "negate": false
  },
  "then": [ { "type": "key", "key": "enter", "modifiers": [] } ],
  "else": []
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
core/conditions.py    évaluation des tests de condition
gui/main_window.py    fenêtre principale
gui/flow.py           canevas de blocs reliés
gui/theme.py          palettes, feuille de style et pictogrammes
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
- La recherche d'image des conditions exige une correspondance exacte de
  pixels : une capture redimensionnée ou un thème différent la fera
  échouer. Installer OpenCV (`pip install opencv-python`) permettrait une
  recherche tolérante.
- La progression affichée est approximative dès qu'une condition est
  présente, les deux branches n'ayant pas la même longueur.
