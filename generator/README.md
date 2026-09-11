# Générateur de pages villes

Ce dossier génère automatiquement toutes les pages "prix carburant à [ville]"
à partir d'un seul template (`template.html`) et d'un fichier de données (`villes.json`).

## Ajouter une nouvelle ville (aucune compétence technique requise)

1. Ouvre `generator/villes.json` sur GitHub (bouton crayon ✏️ pour éditer)
2. Dans le tableau `"villes"`, ajoute une nouvelle entrée avant le `]` final, sur ce modèle :

```json
,{"pays":"france","slug":"lyon","nom":"Lyon","lat":45.7640,"lon":4.8357}
```

- `pays` : `france`, `espagne` ou `italie`
- `slug` : le nom dans l'URL, en minuscules, sans accent ni espace (ex: `aix-en-provence`)
- `nom` : le nom affiché sur la page (avec accents si besoin)
- `lat` / `lon` : les coordonnées GPS de la ville (cherche "coordonnées GPS [ville]" sur Google)

Tu peux aussi ajouter, en option, `"intro"` et `"why"` (deux phrases personnalisées sur la ville) —
si tu ne les mets pas, un texte générique adapté à la langue du pays sera utilisé automatiquement.

3. Valide (commit) directement sur GitHub

**C'est tout.** Une GitHub Action se déclenche automatiquement, régénère la page et le
plan du site (`sitemap.xml`), et pousse le résultat sur le repo — sans rien faire de plus.

## Modifier le texte pour TOUTES les villes d'un pays

Les textes communs (titre, badges, bénéfices, boutons...) sont dans la section `"pays"`
du même fichier `villes.json`, une fois par pays (`france`, `espagne`, `italie`).
Modifier une ligne là-bas met à jour toutes les pages du pays concerné au prochain passage
de la GitHub Action.

## Modifier la mise en page / le design

C'est dans `generator/template.html`. Un seul fichier pour toutes les villes et tous les pays —
toute modification s'applique partout à la prochaine génération.

## Tester en local avant de pousser (optionnel)

```
python3 generator/generate.py
```
