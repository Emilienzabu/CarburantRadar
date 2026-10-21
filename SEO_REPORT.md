# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 21/10/2026 11:59 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 419 |
| Pages villes (France) | 182 dont 181 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 142 |
| — dont Gazole | 59 |
| — dont SP95 | 2 |
| — dont SP98 | 29 |
| — dont E10 | 44 |
| — dont E85 | 8 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1708 |
| Stations analysées (jeu de données) | 9812 |
| Jours d'historique enregistrés | 22 (du 2026-09-30 au 2026-10-21) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11374 stations exploitables ; données du 21/10/2026 10:23 UTC.
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- **Source indisponible : 919 pages indexables de la veille réutilisées** : RuntimeError: RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>) ; cache indisponible (https://emilienzabu.github.io/CarburantRadar/donnees/italie-prezzi.json.gz : HTTP Error 404: Not Found)

## IndexNow (Bing, Yandex, Naver, Seznam)

- 1708 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 419 / 419 |
| Meta descriptions | 419 / 419 |
| H1 | 419 / 419 |
| Canonicals | 419 / 419 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4209 ; moyenne par page : 10.0
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 74 | 6 |
| Asnières-sur-Seine | 100 | 175 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 184 | 6 |
| Drancy | 100 | 143 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Orléans | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 38 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 30 % (min 19 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 43 % (min 36 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

