# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 15/10/2026 11:49 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 434 |
| Pages villes (France) | 182 dont 181 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 157 |
| — dont Gazole | 65 |
| — dont SP95 | 2 |
| — dont SP98 | 34 |
| — dont E10 | 48 |
| — dont E85 | 7 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1708 |
| Stations analysées (jeu de données) | 9818 |
| Jours d'historique enregistrés | 16 (du 2026-09-30 au 2026-10-15) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11492 stations exploitables ; données du 15/10/2026 10:08 UTC.
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- Source : CSV du MIMIT ; 21452 stations exploitables ; données du 14/10/2026 08:02 UTC.
- Pages villes : 811 dont 811 indexables (708 ajoutées automatiquement) ; pages provinces : 107.

## IndexNow (Bing, Yandex, Naver, Seznam)

- 1708 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 434 / 434 |
| Meta descriptions | 434 / 434 |
| H1 | 434 / 434 |
| Canonicals | 434 / 434 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4396 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 76 | 6 |
| Asnières-sur-Seine | 100 | 177 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 186 | 6 |
| Drancy | 100 | 144 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Orléans | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 39 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 29 % (min 18 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

