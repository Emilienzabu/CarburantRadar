# Générateur de pages SEO

Un seul point d'entrée : `python3 generate.py` (à la racine du dépôt). Il produit, de façon déterministe
(mêmes données ⇒ mêmes pages, aucun texte aléatoire) :

| Pages | URL | Contenu |
|---|---|---|
| Villes France (103, URLs inchangées) | `/france/prix-carburant/{ville}/` | prix min/moyen/max par carburant, stations les moins chères, comparaisons, économie sur un plein, villes voisines, FAQ, date des données |
| Ville + carburant | `/france/prix-carburant/{ville}/{gazole,sp95,sp98,e10,e85,gpl}/` | seulement pour les communes ayant ≥ 8 stations avec un prix pour ce carburant |
| Départements | `/france/{departement}/` | stats du département, stations les moins chères, communes, villes couvertes |
| Régions | `/france/{region}/` | stats, départements, villes |
| Hubs | `/france/prix-carburant/`, `/espagne/precio-carburante/`, `/italie/prezzo-carburante/` | listes de villes (maillage depuis l'accueil) |
| Espagne / Italie (206 villes) | inchangées | ancien template (`template.html`), octet pour octet |

Sortie annexe : `sitemap_1.xml` (uniquement les pages indexables), `robots.txt` (ligne Sitemap), `SEO_REPORT.md`,
`generator/generated_pages.json` (liste des pages écrites, sert à supprimer celles qui ne sont plus générées).

## Données (aucune donnée inventée)

- Prix et stations : flux officiel « Prix des carburants en France — flux instantané v2 » (data.economie.gouv.fr),
  téléchargé au moment de la génération. Si le téléchargement échoue, **rien n'est modifié** (code retour 2).
- Département et région : champs du jeu de données lui-même. Villes voisines : distance entre les coordonnées de `villes.json`.
- Portée des chiffres d'une ville : la commune si elle compte ≥ 3 stations dans le flux, sinon un rayon de 12 km
  (le même que le bloc « en direct »). La page indique toujours laquelle des deux s'applique.
- Aucune évolution/tendance de prix : le dépôt ne contient pas d'historique exploitable.
- Le flux ne donne ni nom ni enseigne : les stations sont identifiées par leur adresse.

## Qualité (contenu léger)

Score de richesse par ville (stations, carburants, département, voisines, comparaison). Une page sous les seuils
(< 3 stations, < 2 carburants ou score < 45 — voir `stats_fr.py`) reste accessible mais est en `noindex` et hors sitemap.
Départements/régions : ≥ 15 stations et au moins une ville indexable.

## Commandes

```
python3 generate.py                    # génère tout (télécharge les prix)
python3 generate.py --data export.json # export local du flux (tests hors ligne)
python3 generator/validate.py          # audit : liens, canonical, sitemap, JSON-LD, orphelines (code 1 si erreur)
python3 generator/tests/make_fixture.py /tmp/f.json   # jeu FACTICE pour tester (ne jamais publier)
```

`SEO_REPORT.md` est régénéré à chaque run (volumétrie, unicité, doublons, maillage, erreurs).

## Ajouter une ville

Ajouter une entrée dans `villes.json` (`pays`, `slug`, `nom`, `lat`, `lon`, et en option `intro` / `why`), commit :
l'Action régénère tout. Les textes communs par pays sont dans la section `"pays"` du même fichier.

## GitHub Actions

`.github/workflows/generate-city-pages.yml` : au push sur `generator/**`, chaque jour à 05:30 UTC, ou à la demande
(`Run workflow`). Elle génère, valide (échec si erreur), puis commit les pages.
