# FRED Studio

Application de bureau locale pour explorer, corriger et générer les données LorcanaJSON.

## Ouvrir l’application

Double-cliquer sur **FRED Studio.vbs** à la racine du projet : l’interface s’ouvre dans une fenêtre dédiée, sans console. **Lancer FRED Studio.cmd** est également disponible pour voir les messages de démarrage.

Le lanceur utilise `.venv-studio` lorsqu’il est présent. Cet environnement a été installé pour cette première version avec les dépendances du projet et la roue Windows Tesserocr fournie dans le dépôt.

L’interface utilise Microsoft Edge en mode application, ou Chrome s’il est disponible à sa place. À défaut, elle s’ouvre dans le navigateur par défaut. Il s’agit d’une V1 locale, pas encore d’un exécutable autonome avec installateur : Python et le dossier du projet restent nécessaires.

Le serveur écoute seulement sur `127.0.0.1`, sur un port libre. Une session déjà ouverte est réutilisée. Après fermeture de la fenêtre, le serveur s’arrête au bout d’environ trois minutes sans activité, une fois les traitements terminés.

## Fonctions

- Accueil avec les chiffres réels de la base et les images locales.
- Catalogue avec recherche par nom, univers ou identifiant ; filtres d’extension, d’encre et de rareté ; tri et vues grille/liste. `Ctrl+K` ouvre la recherche.
- Fiche de carte avec image, capacités, caractéristiques et JSON copiable.
- Atelier de corrections : remplacement de texte littéral dans les capacités, effets, texte d’ambiance, nom, sous-titre ou illustrateur. Prévisualisation avant enregistrement.
- Traitements : `check`, `download`, `update`, `parse`, `verify`, `updateExternalLinks`. Sélection d’identifiants pour `parse` et `verify`, option de cache OCR, journal en direct et code de sortie.
- Exports JSON/XML/ZIP existants : téléchargement ou ouverture du dossier Windows.
- Diagnostic de l’environnement Python et des modèles OCR locaux.

FR/EN/DE/IT sont sélectionnables. Une langue sans fichier `output/<langue>/allCards.json` affiche un catalogue vide.

## Corrections et sauvegardes

L’atelier ajoute une paire de remplacement compatible avec le moteur dans `OutputGeneration/data/outputDataCorrections/outputDataCorrections_<langue>.json`. Les règles déjà présentes, y compris celles des autres cartes, sont conservées. Le texte saisi est échappé pour ne pas être interprété comme une expression régulière.

Avant chaque écriture, une copie du fichier précédent est enregistrée sous `.fred-studio/backups/`. L’écriture est atomique. Si le fichier a changé depuis l’ouverture de la carte, l’enregistrement est refusé pour éviter d’écraser une modification concurrente. Rouvrir la carte permet de repartir de la version actuelle.

Enregistrer une règle ne modifie pas immédiatement les exports. Utiliser **Relancer l’analyse de cette carte**, puis vérifier le résultat. La prévisualisation porte sur les données déjà générées ; le texte OCR brut peut différer lors de la prochaine analyse.

Pour restaurer une sauvegarde, fermer les traitements puis recopier la sauvegarde concernée vers son fichier `outputDataCorrections_<langue>.json`. Cela restaure le fichier entier, pas uniquement une carte.

## Installation sur une autre machine

L’interface elle-même n’utilise que la bibliothèque standard de Python. Pour le moteur complet, depuis la racine du dépôt, avec Python 3.13 x64 (version de la roue Tesserocr fournie) :

```powershell
python -m venv .venv-studio
.\.venv-studio\Scripts\python.exe -m pip install -r requirements.txt .\tesserocr-2.8.0-cp313-cp313-win_amd64.whl
.\.venv-studio\Scripts\python.exe studio.py
```

Conserver la configuration du projet et les modèles Tesseract. Le jeton CardTrader est requis par le moteur pour l’actualisation des liens externes ; le studio ne l’affiche pas. Les opérations réseau et la génération utilisent les mêmes fichiers et les mêmes services que les commandes du projet.

La fermeture de la fenêtre laisse finir un traitement en cours. Les erreurs et différences détectées restent consultables dans le journal ; un code de sortie zéro indique la fin normale du programme, pas nécessairement l’absence de différences de vérification. Les journaux complets sont conservés dans `.fred-studio/runs/`, le dernier résultat dans `.fred-studio/last-run.json`.

## Développement et validation

```powershell
# Serveur sans fenêtre (développement)
.\.venv-studio\Scripts\python.exe studio.py --no-browser --port 8765

# Tests isolés : validation, conservation des règles, sauvegarde, accès HTTP, commandes
.\.venv-studio\Scripts\python.exe -m unittest discover -s studio/tests -v

# Parcours navigateur headless, avec Edge installé
.\.venv-studio\Scripts\python.exe -m pip install playwright
.\.venv-studio\Scripts\python.exe studio/tests/browser_smoke.py
```

Le test navigateur utilise les données locales, prévisualise une correction sans l’enregistrer, télécharge un export dans un espace temporaire et exécute une vérification de la carte anglaise 1. Il produit des captures dans `.fred-studio/qa/` et contrôle les largeurs 1500, 1100, 800 et 430 px. Les tests d’écriture utilisent uniquement un dossier temporaire.

Structure : `server.py` expose les données et orchestre le moteur ; `web/` contient l’interface ; `tests/` contient les vérifications. Aucun service distant, police externe ou outil de compilation n’est nécessaire pour l’interface.
