# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 26/10/2026 11:49 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 401 |
| Pages villes (France) | 182 dont 180 indexables et 2 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 80 |
| Pages régions | 13 |
| Pages ville + carburant | 125 |
| — dont Gazole | 53 |
| — dont SP95 | 2 |
| — dont SP98 | 27 |
| — dont E10 | 34 |
| — dont E85 | 9 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1706 |
| Stations analysées (jeu de données) | 9820 |
| Jours d'historique enregistrés | 27 (du 2026-09-30 au 2026-10-26) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11388 stations exploitables ; données du 26/10/2026 11:20 UTC.
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- **Source indisponible : 919 pages indexables de la veille réutilisées** : RuntimeError: RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>) ; cache indisponible (https://emilienzabu.github.io/CarburantRadar/donnees/italie-prezzi.json.gz : HTTP Error 404: Not Found)

## IndexNow (Bing, Yandex, Naver, Seznam)

- 1706 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Correctifs appliqués aux applications

- france : économie nette du trajet aller-retour : appliqué
- espagne : économie nette du trajet aller-retour : appliqué
- italie : économie nette du trajet aller-retour : appliqué

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 401 / 401 |
| Meta descriptions | 401 / 401 |
| H1 | 401 / 401 |
| Canonicals | 401 / 401 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 2
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4041 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 3

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 176 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 185 | 6 |
| Drancy | 100 | 144 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| Troyes | 40 | 5 | 3 |
| La Rochelle | 44 | 4 | 4 |
| Orléans | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 36 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 32 % (min 21 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 34 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

